#!/usr/bin/env python3

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

signals = {}
questions = {}

for path in (ROOT / "dataset" / "signals").glob("*.json"):
    data = json.loads(path.read_text())
    signals[data["id"]] = data

for path in (ROOT / "dataset" / "questions").glob("*.json"):
    data = json.loads(path.read_text())
    questions[data["id"]] = data

errors = []

for question_id, question in questions.items():
    for signal_id in question["required_signals"]:
        if signal_id not in signals:
            errors.append(
                f"Question {question_id} references unknown signal {signal_id}"
            )

    for rule in question["evaluation_trigger"]["rules"]:
        signal_id = rule["signal_id"]
        if signal_id not in signals:
            errors.append(
                f"Question {question_id} trigger references unknown signal {signal_id}"
            )

if errors:
    print("CONFLICT CHECK: FAILED")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("CONFLICT CHECK: PASSED")
print(f"Signals: {len(signals)}")
print(f"Questions: {len(questions)}")
