from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.ledger import (
    canonical_json_dumps,
    compute_sha256,
    hash_knowledge_state,
    hash_proposal,
    append_ledger_event,
    verify_ledger_integrity,
    read_ledger_events,
)


# ----------------------------------------------------------------------
# 1. Hashing Determinism Tests
# ----------------------------------------------------------------------

def test_canonical_json_dumps_key_order_independence():
    obj1 = {"b": 2, "a": 1, "nested": {"z": 26, "y": 25}}
    obj2 = {"a": 1, "b": 2, "nested": {"y": 25, "z": 26}}
    assert canonical_json_dumps(obj1) == canonical_json_dumps(obj2)
    assert compute_sha256(obj1) == compute_sha256(obj2)


def test_hash_value_difference():
    obj1 = {"a": 1, "b": 2}
    obj2 = {"a": 1, "b": 3}
    assert compute_sha256(obj1) != compute_sha256(obj2)


def test_hash_type_difference():
    obj1 = {"a": 1}
    obj2 = {"a": "1"}
    obj3 = {"a": 1.0}
    assert compute_sha256(obj1) != compute_sha256(obj2)
    # Both SHA256 string formats
    assert compute_sha256(obj1).startswith("sha256:")
    assert len(compute_sha256(obj1)) == 7 + 64


def test_hash_knowledge_state():
    state_mock = {
        "questions": [{"id": "q_001", "hypothesis": "hyp A"}],
        "signals": [{"id": "sig_001", "name": "signal A"}],
        "relations": [{"source": "q_001", "target": "q_002"}],
        "methods": [{"method_id": "method_01", "version": "1.0.0"}]
    }
    hash_val = hash_knowledge_state(state_mock)
    assert hash_val.startswith("sha256:")


# ----------------------------------------------------------------------
# 2. Ledger Append & Chaining Tests
# ----------------------------------------------------------------------

@pytest.fixture
def sample_event_1() -> dict:
    return {
        "cycle_id": "cycle_20260826_140001",
        "timestamp": "2026-08-26T14:00:01Z",
        "previous_event_hash": None,
        "initial_state_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
        "proposal_hash": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
        "resulting_state_hash": "sha256:3333333333333333333333333333333333333333333333333333333333333333",
        "proposal_id": "prop_opp_motor_instability_01",
        "predictions": {
            "novelty_score": 0.85,
            "coverage_gain": 0.20,
            "confidence": 0.90
        },
        "gate_verdict": {
            "valid": True,
            "safe": True,
            "classification": "PREDICTED_IMPROVEMENT"
        },
        "action_taken": "SHADOW_RECORDED",
        "post_evaluation": None
    }


@pytest.fixture
def sample_event_2() -> dict:
    return {
        "cycle_id": "cycle_20260826_143001",
        "timestamp": "2026-08-26T14:30:01Z",
        "previous_event_hash": None,  # Will be auto-computed by append_ledger_event
        "initial_state_hash": "sha256:3333333333333333333333333333333333333333333333333333333333333333",
        "proposal_hash": "sha256:4444444444444444444444444444444444444444444444444444444444444444",
        "resulting_state_hash": "sha256:5555555555555555555555555555555555555555555555555555555555555555",
        "proposal_id": "prop_opp_temporal_persistence_02",
        "predictions": {
            "novelty_score": 0.78,
            "coverage_gain": 0.15,
            "confidence": 0.88
        },
        "gate_verdict": {
            "valid": True,
            "safe": True,
            "classification": "PREDICTED_IMPROVEMENT"
        },
        "action_taken": "SHADOW_RECORDED",
        "post_evaluation": None
    }


def test_append_first_event_and_chaining(tmp_path, sample_event_1, sample_event_2):
    ledger_path = tmp_path / "ledger.jsonl"

    # 1. First event
    ev1 = append_ledger_event(sample_event_1, ledger_path=ledger_path)
    assert ev1["previous_event_hash"] is None

    events = read_ledger_events(ledger_path)
    assert len(events) == 1
    assert events[0]["cycle_id"] == "cycle_20260826_140001"

    # 2. Second event chains to hash of event 1
    ev2 = append_ledger_event(sample_event_2, ledger_path=ledger_path)
    expected_prev_hash = compute_sha256(ev1)
    assert ev2["previous_event_hash"] == expected_prev_hash

    events_2 = read_ledger_events(ledger_path)
    assert len(events_2) == 2
    assert events_2[1]["previous_event_hash"] == expected_prev_hash


def test_append_rejects_duplicate_cycle_id(tmp_path, sample_event_1):
    ledger_path = tmp_path / "ledger.jsonl"
    append_ledger_event(sample_event_1, ledger_path=ledger_path)

    with pytest.raises(ValueError, match="Duplicate cycle_id"):
        append_ledger_event(sample_event_1, ledger_path=ledger_path)


def test_append_rejects_schema_invalid_event(tmp_path, sample_event_1):
    ledger_path = tmp_path / "ledger.jsonl"
    invalid_event = dict(sample_event_1)
    invalid_event["predictions"]["novelty_score"] = 2.5  # > 1.0 invalid

    with pytest.raises(ValueError, match="Ledger event failed schema validation"):
        append_ledger_event(invalid_event, ledger_path=ledger_path)


# ----------------------------------------------------------------------
# 3. Integrity Verification & Tamper Detection Tests
# ----------------------------------------------------------------------

def test_verify_ledger_valid(tmp_path, sample_event_1, sample_event_2):
    ledger_path = tmp_path / "ledger.jsonl"
    append_ledger_event(sample_event_1, ledger_path=ledger_path)
    append_ledger_event(sample_event_2, ledger_path=ledger_path)

    is_valid, errors = verify_ledger_integrity(ledger_path=ledger_path)
    assert is_valid is True
    assert errors == []


def test_verify_detects_tampered_payload(tmp_path, sample_event_1, sample_event_2):
    ledger_path = tmp_path / "ledger.jsonl"
    append_ledger_event(sample_event_1, ledger_path=ledger_path)
    append_ledger_event(sample_event_2, ledger_path=ledger_path)

    # Manually tamper event 1 in file
    lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    event_1_modified = json.loads(lines[0])
    event_1_modified["predictions"]["novelty_score"] = 0.99  # Tampered!
    lines[0] = json.dumps(event_1_modified)
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, errors = verify_ledger_integrity(ledger_path=ledger_path)
    assert is_valid is False
    assert any("Hash chain broken" in err for err in errors)


def test_verify_detects_deleted_intermediate_line(tmp_path, sample_event_1, sample_event_2):
    ledger_path = tmp_path / "ledger.jsonl"
    append_ledger_event(sample_event_1, ledger_path=ledger_path)
    append_ledger_event(sample_event_2, ledger_path=ledger_path)

    # Manually delete event 1 (leaving only event 2 which has non-null previous hash)
    lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    ledger_path.write_text(lines[1] + "\n", encoding="utf-8")

    is_valid, errors = verify_ledger_integrity(ledger_path=ledger_path)
    assert is_valid is False
    assert any("First event must have previous_event_hash=null" in err for err in errors)
