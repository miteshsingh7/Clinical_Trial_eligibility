from typing import Dict, Any, List

class ActiveLearningFeedbackStore:
    """
    Stores clinical research coordinator overrides on ambiguous criteria and derives
    reusable disambiguation rules for future patient-trial screenings.
    """
    def __init__(self):
        self.overrides: Dict[str, str] = {}
        self.audit_log: List[Dict[str, Any]] = []

    def record_correction(self, patient_id: str, nct_id: str, criterion_id: str, new_status: str, coordinator_note: str):
        key = f"{patient_id}::{nct_id}::{criterion_id}"
        self.overrides[key] = new_status
        self.audit_log.append({
            "key": key,
            "new_status": new_status,
            "coordinator_note": coordinator_note
        })

    def get_overrides(self) -> Dict[str, str]:
        return dict(self.overrides)
