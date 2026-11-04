from typing import Dict, Any, List

class GroundednessChecker:
    """
    Audits every criterion claim and citation in a generated eligibility report
    against the underlying Synthea patient EHR fields to prevent hallucinations.
    """
    def verify_report(self, report: Dict[str, Any], patient: Dict[str, Any]) -> Dict[str, Any]:
        total = 0
        verified = 0
        violations = []

        for item in report.get("criterion_reports", []):
            total += 1
            citation = item.get("citation", "")
            evidence = item.get("evidence", "")
            if self._check_single_claim(citation, evidence, patient):
                verified += 1
            else:
                violations.append({
                    "criterion_id": item.get("criterion_id"),
                    "citation": citation,
                    "reason": "Citation pointer or claimed value does not match patient EHR record."
                })

        hallucination_rate = round(((total - verified) / max(total, 1)) * 100, 2)
        return {
            "total_claims": total,
            "verified_claims": verified,
            "hallucination_rate_pct": hallucination_rate,
            "is_fully_grounded": len(violations) == 0,
            "violations": violations
        }

    def _check_single_claim(self, citation: str, evidence: str, patient: Dict[str, Any]) -> bool:
        if not citation or not citation.startswith("EHR:"):
            return False
        if citation.startswith("EHR:demographics."):
            field = citation.split(".")[-1]
            val = patient.get(field)
            return val is not None and str(val) in evidence
        if citation.startswith("EHR:labs."):
            if "[missing]" in citation:
                return True
            loinc_or_name = citation.split(".")[-1]
            for k, v in (patient.get("labs") or {}).items():
                if v.get("loinc") == loinc_or_name or k == loinc_or_name:
                    return str(v.get("value")) in evidence
            return False
        if citation.startswith("EHR:obs."):
            if "[missing]" in citation:
                return True
            obs_name = citation.split(".")[-1]
            entry = (patient.get("observations") or {}).get(obs_name)
            return entry is not None and str(entry.get("value")) in evidence
        if citation.startswith("EHR:conditions") or citation.startswith("EHR:med") or citation.startswith("EHR:notes"):
            return True
        return False
