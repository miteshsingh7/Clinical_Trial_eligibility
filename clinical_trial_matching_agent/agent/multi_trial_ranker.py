from typing import List, Dict, Any
from agent.criteria_extractor import TrialCriteriaExtractor
from agent.matching_engine import EligibilityMatchingAgent

class MultiTrialRanker:
    """Ranks all recruiting trials for a single patient or across an entire cohort."""
    def __init__(self):
        self.extractor = TrialCriteriaExtractor()
        self.agent = EligibilityMatchingAgent()

    def rank_trials_for_patient(
        self,
        patient: Dict[str, Any],
        trials: List[Dict[str, Any]],
        overrides: Dict[str, str] = None
    ) -> List[Dict[str, Any]]:
        results = []
        for t in trials:
            criteria = self.extractor.extract_criteria(t)
            rep = self.agent.evaluate_patient_for_trial(patient, t, criteria, overrides=overrides)
            results.append(rep)
        priority = {"ELIGIBLE": 0, "PENDING_REVIEW": 1, "INELIGIBLE": 2}
        results.sort(key=lambda r: (priority.get(r["overall_decision"], 3), -r["match_score"]))
        return results
