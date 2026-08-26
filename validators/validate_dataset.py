#!/usr/bin/env python3

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "v2"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_schema(name: str):
    return load_json(SCHEMA_DIR / name)


def validate_schema(instance, schema_name):
    schema_path = SCHEMA_DIR / schema_name
    schema = load_schema(schema_name)

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

    validator = Draft7Validator(
        schema,
        resolver=resolver,
    )

    errors = sorted(validator.iter_errors(instance), key=str)

    return errors


def load_fixtures():
    signals = {}
    questions = {}
    relations = []

    for path in (ROOT / "tests" / "fixtures" / "valid" / "signals").glob("*.json"):
        data = load_json(path)
        signals[data["id"]] = data

    for path in (ROOT / "tests" / "fixtures" / "valid" / "questions").glob("*.json"):
        data = load_json(path)
        questions[data["id"]] = data

    for path in (ROOT / "tests" / "fixtures" / "valid" / "relations").glob("*.json"):
        relations.append(load_json(path))

    return signals, questions, relations


def validate_cross_references(signals, questions, relations):
    errors = []

    for question_id, question in questions.items():
        for signal_id in question["required_signals"]:
            if signal_id not in signals:
                errors.append(
                    f"{question_id}: required signal not found: {signal_id}"
                )

        for rule in question["evaluation_trigger"]["rules"]:
            signal_id = rule["signal_id"]

            if signal_id not in signals:
                errors.append(
                    f"{question_id}: trigger signal not found: {signal_id}"
                )

    for relation in relations:
        source = relation["source_question_id"]
        target = relation["target_question_id"]

        if source not in questions:
            errors.append(
                f"Relation source not found: {source}"
            )

        if target not in questions:
            errors.append(
                f"Relation target not found: {target}"
            )

    return errors


def main():
    signals, questions, relations = load_fixtures()

    print("=== Schema validation ===")

    for signal in signals.values():
        errors = validate_schema(
            signal,
            "signal.schema.json"
        )

        if errors:
            for error in errors:
                print(f"ERROR signal: {error.message}")

            return 1

    for question in questions.values():
        errors = validate_schema(
            question,
            "question.schema.json"
        )

        if errors:
            for error in errors:
                print(f"ERROR question: {error.message}")

            return 1

    for relation in relations:
        errors = validate_schema(
            relation,
            "relation.schema.json"
        )

        if errors:
            for error in errors:
                print(f"ERROR relation: {error.message}")

            return 1

    print("Schema validation: PASS")

    print()
    print("=== Cross-reference validation ===")

    errors = validate_cross_references(
        signals,
        questions,
        relations
    )

    if errors:
        for error in errors:
            print(f"ERROR: {error}")

        return 1

    print("Cross-reference validation: PASS")

    print()
    print("=== Dataset validation summary ===")
    print(f"Signals:   {len(signals)}")
    print(f"Questions: {len(questions)}")
    print(f"Relations: {len(relations)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
