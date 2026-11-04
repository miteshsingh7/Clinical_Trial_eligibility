import unittest
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agent.criteria_extractor import TrialCriteriaExtractor
from agent.matching_engine import EligibilityMatchingAgent
from agent.groundedness_checker import GroundednessChecker
from agent.multi_trial_ranker import MultiTrialRanker
from agent.active_learning import ActiveLearningFeedbackStore

class TestClinicalTrialMatchingAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with open(os.path.join(base, "data", "trials_clinicaltrials_gov.json")) as f:
            cls.trials = json.load(f)
        with open(os.path.join(base, "data", "patients_synthea_cohort.json")) as f:
            cls.patients = json.load(f)
        cls.extractor = TrialCriteriaExtractor()
        cls.agent = EligibilityMatchingAgent()
        cls.checker = GroundednessChecker()
        cls.ranker = MultiTrialRanker()

    def test_15_trials_and_15_patients_loaded(self):
        self.assertGreaterEqual(len(self.trials), 15)
        self.assertGreaterEqual(len(self.patients), 15)

    def test_criteria_extraction_and_matching(self):
        trial = self.trials[0]  # NCT05489210
        patient = self.patients[0]  # SYN-PT-1001
        criteria = self.extractor.extract_criteria(trial)
        self.assertEqual(len(criteria), 8)
        report = self.agent.evaluate_patient_for_trial(patient, trial, criteria)
        self.assertEqual(report["overall_decision"], "PENDING_REVIEW")
        self.assertEqual(report["summary_counts"]["PASS"], 7)
        self.assertEqual(report["summary_counts"]["UNCLEAR"], 1)

    def test_groundedness_checker_passes_valid_and_catches_hallucination(self):
        trial = self.trials[2]  # NCT05920318 (HFpEF)
        patient = self.patients[2]  # SYN-PT-1003
        criteria = self.extractor.extract_criteria(trial)
        report = self.agent.evaluate_patient_for_trial(patient, trial, criteria)
        ver = self.checker.verify_report(report, patient)
        self.assertTrue(ver["is_fully_grounded"])
        self.assertEqual(ver["hallucination_rate_pct"], 0.0)

        # Inject a fabricated lab value claim and verify GroundednessChecker catches it
        corrupted = json.loads(json.dumps(report))
        corrupted["criterion_reports"][3]["evidence"] = "Lab NT-proBNP = 9999.0 pg/mL"
        ver_bad = self.checker.verify_report(corrupted, patient)
        self.assertFalse(ver_bad["is_fully_grounded"])
        self.assertGreater(ver_bad["hallucination_rate_pct"], 0.0)

    def test_active_learning_override_promotes_pending_to_eligible(self):
        store = ActiveLearningFeedbackStore()
        store.record_correction("SYN-PT-1001", "NCT05489210", "C8", "PASS", "Excised basal cell skin lesion cleared")
        trial = self.trials[0]
        patient = self.patients[0]
        criteria = self.extractor.extract_criteria(trial)
        report = self.agent.evaluate_patient_for_trial(patient, trial, criteria, overrides=store.get_overrides())
        self.assertEqual(report["overall_decision"], "ELIGIBLE")

    def test_multi_trial_ranking(self):
        patient = self.patients[2]  # SYN-PT-1003 (HFpEF + AFib)
        ranked = self.ranker.rank_trials_for_patient(patient, self.trials)
        self.assertEqual(ranked[0]["overall_decision"], "ELIGIBLE")
        self.assertIn(ranked[0]["nct_id"], ["NCT05920318", "NCT06301195"])

if __name__ == "__main__":
    unittest.main()
