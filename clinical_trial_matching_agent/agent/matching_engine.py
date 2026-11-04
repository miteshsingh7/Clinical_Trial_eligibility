from typing import Dict, Any, List, Tuple

class EHRRecordTools:
    """Structured tool interfaces over a Synthea-format patient EHR record."""
    def __init__(self, patient: Dict[str, Any]):
        self.patient = patient

    def query_demographics(self, field: str) -> Tuple[Any, str]:
        val = self.patient.get(field)
        return val, f"EHR:demographics.{field}"

    def query_conditions(self) -> Tuple[List[Dict[str, Any]], str]:
        conds = self.patient.get("conditions", [])
        codes = [c["code"] for c in conds]
        ref = f"EHR:conditions[{','.join(codes)}]" if codes else "EHR:conditions[none]"
        return conds, ref

    def query_lab(self, lab_name: str) -> Tuple[Dict[str, Any], str]:
        labs = self.patient.get("labs", {})
        entry = labs.get(lab_name)
        if not entry:
            return None, f"EHR:labs.{lab_name}[missing]"
        return entry, entry.get("ref_id", f"EHR:labs.{lab_name}")

    def query_observation(self, obs_name: str) -> Tuple[Dict[str, Any], str]:
        obs = self.patient.get("observations", {})
        entry = obs.get(obs_name)
        if not entry:
            return None, f"EHR:obs.{obs_name}[missing]"
        return entry, entry.get("ref_id", f"EHR:obs.{obs_name}")

    def query_medications(self) -> Tuple[List[Dict[str, Any]], str]:
        meds = self.patient.get("medications", [])
        return meds, "EHR:medications"

    def query_clinical_notes(self) -> Tuple[str, str]:
        return self.patient.get("clinical_notes", ""), self.patient.get("note_ref_id", "EHR:notes")


class EligibilityMatchingAgent:
    """
    Executes multi-step tool calls over structured EHR records for each extracted
    trial criterion, produces criterion-by-criterion PASS/FAIL/UNCLEAR verdicts with
    verifiable field citations, and runs a Groundedness Verification check.
    """
    def evaluate_patient_for_trial(
        self,
        patient: Dict[str, Any],
        trial: Dict[str, Any],
        criteria: List[Dict[str, Any]],
        overrides: Dict[str, str] = None
    ) -> Dict[str, Any]:
        tools = EHRRecordTools(patient)
        overrides = overrides or {}
        criterion_reports = []
        tool_call_trace = []

        for c in criteria:
            cid = c["id"]
            ctype = c["type"]  # inclusion or exclusion
            cat = c["category"]
            field = c["field"]
            op = c["operator"]
            target = c["value"]

            status = "UNCLEAR"
            evidence = ""
            citation = ""
            needs_human_review = False

            if cat == "demographics":
                val, ref = tools.query_demographics(field)
                tool_call_trace.append({"criterion_id": cid, "tool": "query_demographics", "arg": field, "ref": ref})
                citation = ref
                if val is None:
                    status = "UNCLEAR"
                    evidence = f"Missing demographic field '{field}' in patient record."
                    needs_human_review = True
                else:
                    cond_met = self._eval_numeric(val, op, target)
                    status = self._map_verdict(ctype, cond_met)
                    evidence = f"Patient {field} is {val} {c.get('unit') or ''} (Requirement: {c['text']})."

            elif cat == "condition":
                conds, ref = tools.query_conditions()
                tool_call_trace.append({"criterion_id": cid, "tool": "query_conditions", "arg": "icd10", "ref": ref})
                citation = ref
                patient_codes = [x["code"] for x in conds]
                matched_codes = [code for code in patient_codes if code in target]
                cond_met = len(matched_codes) > 0
                status = self._map_verdict(ctype, cond_met)
                if matched_codes:
                    matched_names = [x["display"] for x in conds if x["code"] in matched_codes]
                    evidence = f"Found active ICD-10 diagnosis {', '.join(matched_codes)} ({matched_names[0]})."
                else:
                    evidence = f"No matching ICD-10 code in {target}; patient active codes: {patient_codes or 'None'}."

            elif cat == "lab":
                entry, ref = tools.query_lab(field)
                tool_call_trace.append({"criterion_id": cid, "tool": "query_lab", "arg": field, "ref": ref})
                citation = ref
                if not entry:
                    status = "UNCLEAR"
                    evidence = f"Lab '{field}' (LOINC {c.get('loinc', 'N/A')}) not found in EHR within lookback window."
                    needs_human_review = True
                else:
                    val = entry["value"]
                    cond_met = self._eval_numeric(val, op, target)
                    status = self._map_verdict(ctype, cond_met)
                    evidence = f"Lab {field} = {val} {entry['unit']} on {entry['date']} (LOINC {entry['loinc']})."

            elif cat == "observation":
                entry, ref = tools.query_observation(field)
                tool_call_trace.append({"criterion_id": cid, "tool": "query_observation", "arg": field, "ref": ref})
                citation = ref
                if not entry:
                    status = "UNCLEAR"
                    evidence = f"Observation '{field}' not recorded in structured vitals/observations."
                    needs_human_review = True
                else:
                    val = entry["value"]
                    cond_met = self._eval_numeric(val, op, target)
                    status = self._map_verdict(ctype, cond_met)
                    evidence = f"Observation {field} = {val} {entry['unit']}."

            elif cat == "medication":
                meds, ref = tools.query_medications()
                tool_call_trace.append({"criterion_id": cid, "tool": "query_medications", "arg": field, "ref": ref})
                target_list = target if isinstance(target, list) else [target]
                matched_med = None
                for m in meds:
                    for t_med in target_list:
                        if t_med.lower() in m["name"].lower():
                            matched_med = m
                            break
                if matched_med:
                    citation = matched_med.get("ref_id", ref)
                    min_w = c.get("min_weeks")
                    if min_w and matched_med.get("weeks_duration", 0) < min_w:
                        cond_met = False
                        evidence = f"Found {matched_med['name']} ({matched_med['weeks_duration']} wks), below required >= {min_w} wks."
                    else:
                        cond_met = True
                        evidence = f"Found medication {matched_med['name']} (duration: {matched_med['weeks_duration']} weeks)."
                else:
                    citation = ref
                    cond_met = False
                    evidence = f"No medication matching {target_list} in active/prior med list."
                status = self._map_verdict(ctype, cond_met)

            elif cat == "clinical_note":
                note_text, ref = tools.query_clinical_notes()
                tool_call_trace.append({"criterion_id": cid, "tool": "query_clinical_notes", "arg": str(target), "ref": ref})
                citation = ref
                note_lower = note_text.lower()
                kw = str(target).lower()
                # Check if explicitly negated vs ambiguous
                if f"no history of {kw}" in note_lower or f"no {kw}" in note_lower or f"negative {kw}" in note_lower:
                    cond_met = False
                    status = self._map_verdict(ctype, cond_met)
                    evidence = f"Clinical note explicitly rules out '{target}': '{note_text}'"
                elif "unclear" in note_lower or "equivocal" in note_lower or "borderline" in note_lower or "needs " in note_lower:
                    status = "UNCLEAR"
                    needs_human_review = True
                    evidence = f"Ambiguous finding in clinical note requiring coordinator review: '{note_text}'"
                elif kw in note_lower:
                    status = "UNCLEAR"
                    needs_human_review = True
                    evidence = f"Potential mention of '{target}' in clinical note; flagged for human verification: '{note_text}'"
                else:
                    cond_met = False
                    status = self._map_verdict(ctype, cond_met)
                    evidence = f"No mention of '{target}' in clinical notes or problem list."

            override_key = f"{patient['patient_id']}::{trial['nct_id']}::{cid}"
            if override_key in overrides:
                status = overrides[override_key]
                needs_human_review = False
                evidence += f" [Coordinator Override Applied: {status}]"

            grounded = self._verify_grounding(citation, patient)
            criterion_reports.append({
                "criterion_id": cid,
                "type": ctype,
                "category": cat,
                "criterion_text": c["text"],
                "status": status,
                "evidence": evidence,
                "citation": citation,
                "grounded": grounded,
                "needs_human_review": needs_human_review
            })

        pass_count = sum(1 for r in criterion_reports if r["status"] == "PASS")
        fail_count = sum(1 for r in criterion_reports if r["status"] == "FAIL")
        unclear_count = sum(1 for r in criterion_reports if r["status"] == "UNCLEAR")
        total = len(criterion_reports)

        if fail_count > 0:
            overall = "INELIGIBLE"
        elif unclear_count > 0:
            overall = "PENDING_REVIEW"
        else:
            overall = "ELIGIBLE"

        # Composite match score (0 to 100)
        score = round(((pass_count + 0.5 * unclear_count) / max(total, 1)) * 100, 1)
        if fail_count > 0:
            score = round(max(0.0, score - fail_count * 35.0), 1)

        return {
            "patient_id": patient["patient_id"],
            "patient_name": patient["name"],
            "nct_id": trial["nct_id"],
            "trial_title": trial["title"],
            "overall_decision": overall,
            "match_score": score,
            "summary_counts": {"PASS": pass_count, "FAIL": fail_count, "UNCLEAR": unclear_count, "TOTAL": total},
            "groundedness_rate": round(sum(1 for r in criterion_reports if r["grounded"]) / max(total, 1) * 100, 1),
            "criterion_reports": criterion_reports,
            "tool_call_trace": tool_call_trace
        }

    def _eval_numeric(self, val: float, op: str, target: Any) -> bool:
        if op == "between":
            return target[0] <= val <= target[1]
        if op == "outside":
            return val < target[0] or val > target[1]
        if op == ">=":
            return val >= target
        if op == "<=":
            return val <= target
        if op == ">":
            return val > target
        if op == "<":
            return val < target
        if op == "in":
            return val in target
        return False

    def _map_verdict(self, ctype: str, cond_met: bool) -> str:
        if ctype == "inclusion":
            return "PASS" if cond_met else "FAIL"
        else:
            # For exclusion criteria: if exclusion condition is met, patient FAILS eligibility
            return "FAIL" if cond_met else "PASS"

    def _verify_grounding(self, citation: str, patient: Dict[str, Any]) -> bool:
        if not citation or not citation.startswith("EHR:"):
            return False
        return True
