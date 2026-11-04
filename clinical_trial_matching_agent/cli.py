#!/usr/bin/env python3
import argparse
import json
import os
from agent.criteria_extractor import TrialCriteriaExtractor
from agent.matching_engine import EligibilityMatchingAgent
from agent.groundedness_checker import GroundednessChecker
from agent.multi_trial_ranker import MultiTrialRanker

def main():
    parser = argparse.ArgumentParser(description="Project 003: Clinical Trial Eligibility Matching Agent CLI")
    parser.add_argument("--patient", default="SYN-PT-1001", help="Patient ID (e.g. SYN-PT-1001)")
    parser.add_argument("--trial", default="NCT05489210", help="Trial NCT ID (e.g. NCT05489210)")
    parser.add_argument("--rank-all", action="store_true", help="Rank all 15 trials for the given patient")
    args = parser.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, "data", "trials_clinicaltrials_gov.json")) as f:
        trials = json.load(f)
    with open(os.path.join(base, "data", "patients_synthea_cohort.json")) as f:
        patients = json.load(f)

    patient = next((p for p in patients if p["patient_id"] == args.patient), patients[0])
    if args.rank_all:
        ranker = MultiTrialRanker()
        ranked = ranker.rank_trials_for_patient(patient, trials)
        print(f"=== Multi-Trial Ranking for {patient['patient_id']} ({patient['name']}) ===")
        for idx, r in enumerate(ranked, 1):
            print(f"{idx:2d}. {r['nct_id']} | {r['overall_decision']:14s} | Score: {r['match_score']:5.1f}% | {r['trial_title']}")
    else:
        trial = next((t for t in trials if t["nct_id"] == args.trial), trials[0])
        extractor = TrialCriteriaExtractor()
        agent = EligibilityMatchingAgent()
        checker = GroundednessChecker()
        criteria = extractor.extract_criteria(trial)
        report = agent.evaluate_patient_for_trial(patient, trial, criteria)
        grounding = checker.verify_report(report, patient)
        report["groundedness_audit"] = grounding
        print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
