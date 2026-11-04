# Project 003: Clinical Trial Eligibility Matching Agent

**Domain:** Healthcare | **Sub-Domain:** Clinical Research Operations | **AI Category:** Agentic AI  
**Primary Technology:** Retrieval + Structured Reasoning Agent over EHR Fields and Trial Criteria

## Architecture & Features
1. **Protocol Criteria Extraction Engine (`agent/criteria_extractor.py`)**: Parses dense free-text inclusion/exclusion criteria from ClinicalTrials.gov protocols into structured logic trees (demographics, ICD-10 diagnosis codes, LOINC lab thresholds, RxNorm medication histories, vitals/observations, and ambiguity detection).
2. **EHR Tool-Calling & Reasoning Agent (`agent/matching_engine.py`)**: Executes structured tool queries (`query_demographics`, `query_conditions`, `query_lab`, `query_observation`, `query_medications`, `query_clinical_notes`) against Synthea-formatted synthetic patient records.
3. **Auditable Criterion-by-Criterion Match Report & Groundedness Verifier**: Every criterion produces a `PASS`, `FAIL`, or `UNCLEAR` status with direct citations (`[EHR:labs.4548-4]`, `[EHR:meds.861004]`, etc.) and flags ambiguous clinical note criteria for human coordinator review.
4. **Multi-Trial Ranking & Active Learning Coordinator Feedback Loop**: Ranks all recruiting trials for a given patient and supports human-in-the-loop overrides that update eligibility decisions.
5. **Evaluation & Benchmark Suite (`evaluation/run_evaluation.py`)**: Evaluates criterion-extraction accuracy, eligibility-decision accuracy, hallucination/ungrounded rate, and clinical research coordinator time saved across 12 real-world trial protocols and 12 synthetic patients (144 patient-trial pairs, 972 criterion evaluations).

## Quickstart
```bash
python3 evaluation/run_evaluation.py
```
