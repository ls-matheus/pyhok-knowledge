#!/usr/bin/env python3

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parents[1]

QUESTION_SCHEMA = ROOT / "schemas/v2/question.schema.json"
METHOD_CATALOG = ROOT / "generator/methods/methods.json"
SIGNALS_DIR = ROOT / "data/signals"
QUESTIONS_DIR = ROOT / "data/questions"


def fail(messages):
    print("VALIDATION: REJECTED")

    for message in messages:
        print(f"- {message}")

    raise SystemExit(1)


def main():
    if len(sys.argv) != 2:
        print(
            "usage: python validators/validate_question.py "
            "<question.json>"
        )
        raise SystemExit(2)

    question_path = Path(sys.argv[1])

    if not question_path.exists():
        fail([f"Question does not exist: {question_path}"])

    question = json.loads(
        question_path.read_text(encoding="utf-8")
    )

    schema = json.loads(
        QUESTION_SCHEMA.read_text(encoding="utf-8")
    )

    errors = sorted(
        Draft7Validator(schema).iter_errors(question),
        key=lambda error: list(error.path),
    )

    if errors:
        fail([
            f"Schema: {error.message}"
            for error in errors
        ])

    # --------------------------------------------------------
    # Known signals
    # --------------------------------------------------------

    known_signals = set()

    for path in SIGNALS_DIR.glob("*.json"):
        signal = json.loads(
            path.read_text(encoding="utf-8")
        )
        known_signals.add(signal["id"])

    reference_errors = []

    for signal_id in question["required_signals"]:
        if signal_id not in known_signals:
            reference_errors.append(
                f"Unknown signal: {signal_id}"
            )

    for rule in question["evaluation_trigger"]["rules"]:
        signal_id = rule["signal_id"]

        if signal_id not in known_signals:
            reference_errors.append(
                f"Unknown trigger signal: {signal_id}"
            )

    if reference_errors:
        fail(reference_errors)

    # --------------------------------------------------------
    # Known evaluation methods
    # --------------------------------------------------------

    catalog = json.loads(
        METHOD_CATALOG.read_text(encoding="utf-8")
    )

    known_methods = {
        (
            method["method_id"],
            method["version"],
        )
        for method in catalog["methods"]
        if method["status"] == "SUPPORTED"
    }

    evaluation_model = question["evaluation_model"]

    method_key = (
        evaluation_model["method_id"],
        evaluation_model["version"],
    )

    if method_key not in known_methods:
        fail([
            "Unsupported evaluation method: "
            f"{evaluation_model['method_id']} "
            f"v{evaluation_model['version']}"
        ])

    # --------------------------------------------------------
    # Duplicate ID
    # --------------------------------------------------------

    question_id = question["id"]

    existing = QUESTIONS_DIR / f"{question_id}.json"

    if existing.exists() and existing.resolve() != question_path.resolve():
        fail([
            f"Question already exists: {question_id}"
        ])

    print("VALIDATION: APPROVED")
    print(f"Question: {question_id}")
    print(
        "Method: "
        f"{evaluation_model['method_id']} "
        f"v{evaluation_model['version']}"
    )


if __name__ == "__main__":
    main()
