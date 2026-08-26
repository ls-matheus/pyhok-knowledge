import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, RefResolver


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "v2"
FIXTURE_DIR = ROOT / "tests" / "fixtures"


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_validator(schema_name):
    schema_path = SCHEMA_DIR / schema_name
    schema = load_json(schema_path)

    schema_store = {}
    for path in SCHEMA_DIR.glob("*.json"):
        s = load_json(path)
        if "$id" in s:
            schema_store[s["$id"]] = s
        schema_store[path.name] = s
        schema_store[path.resolve().as_uri()] = s

    resolver = RefResolver(
        schema_path.resolve().as_uri(),
        schema,
        store=schema_store,
    )

    return Draft7Validator(schema, resolver=resolver)


def test_signal_schema():
    validator = build_validator("signal.schema.json")
    instance = load_json(
        FIXTURE_DIR / "valid/signals/sig_pointer_velocity.json"
    )

    errors = list(validator.iter_errors(instance))

    assert errors == []


def test_question_schema():
    validator = build_validator("question.schema.json")
    instance = load_json(
        FIXTURE_DIR / "valid/questions/q_motor_instability.json"
    )

    errors = list(validator.iter_errors(instance))

    assert errors == []


def test_relation_schema():
    validator = build_validator("relation.schema.json")
    instance = load_json(
        FIXTURE_DIR / "valid/relations/reinforces.json"
    )

    errors = list(validator.iter_errors(instance))

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

    assert missing == ["sig_that_does_not_exist"]
