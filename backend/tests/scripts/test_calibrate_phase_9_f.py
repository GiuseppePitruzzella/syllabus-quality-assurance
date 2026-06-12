"""Regression tests for the Phase 9.F calibration runner."""
from __future__ import annotations

import copy

from scripts.calibrate_phase_9_f import REDACTED, _redact_gcp_project_id


def test_redact_gcp_project_id_recursively_without_touching_other_fields():
    payload = {
        "gcp_project_id": "private-project",
        "nested": {
            "gcp_project_id": "private-project",
            "gcp_location": "europe-west1",
        },
        "items": [{"gcp_project_id": "private-project"}, "unchanged"],
    }
    original = copy.deepcopy(payload)

    _redact_gcp_project_id(payload)

    assert payload == {
        "gcp_project_id": REDACTED,
        "nested": {
            "gcp_project_id": REDACTED,
            "gcp_location": "europe-west1",
        },
        "items": [{"gcp_project_id": REDACTED}, "unchanged"],
    }
    assert original["nested"]["gcp_location"] == payload["nested"]["gcp_location"]
