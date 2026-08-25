import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "v2"
FIXTURE_DIR = ROOT / "tests" / "fixtures"


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_signal_schema():
    schema = load_json(SCHEMA_DIR / "signal.schema.json")
    instance = load_json(
        FIXTURE_DIR / "valid/signals/sig_pointer_velocity.json"
    )

    errors = list(Draft7Validator(schema).iter_errors(instance))

    assert errors == []


def test_question_schema():
    schema = load_json(SCHEMA_DIR / "question.schema.json")
    instance = load_json(
        FIXTURE_DIR / "valid/questions/q_motor_instability.json"
    )

    errors = list(Draft7Validator(schema).iter_errors(instance))

    assert errors == []


def test_relation_schema():
    schema = load_json(SCHEMA_DIR / "relation.schema.json")
    instance = load_json(
        FIXTURE_DIR / "valid/relations/reinforces.json"
    )

    errors = list(Draft7Validator(schema).iter_errors(instance))

    assert errors == []


def test_invalid_question_reference_is_detected():
    question = load_json(
        FIXTURE_DIR / "invalid/question_missing_signal.json"
    )

    signal_ids = {
        load_json(path)["id"]
        for path in (
            FIXTURE_DIR / "valid/signals"
        ).glob("*.json")
    }

    missing = [
        signal_id
        for signal_id in question["required_signals"]
        if signal_id not in signal_ids
    ]

    assert missing == ["sig_does_not_exist"]
