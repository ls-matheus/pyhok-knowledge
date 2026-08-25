import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROPOSAL = json.loads(
    (ROOT / "generator/output/proposal.json")
    .read_text(encoding="utf-8")
)

if PROPOSAL["status"] == "NO_PROPOSAL":
    print("VALIDATION: NO_PROPOSAL")
    sys.exit(0)

proposal = PROPOSAL["proposal"]

context = json.loads(
    (ROOT / "generator/output/current_context.json")
    .read_text(encoding="utf-8")
)

mission = context["mission"]
policy = context["evolution_policy"]
method_catalog = context["methods"]["methods"]

known_signals = {
    item["id"]
    for item in context["signals"]
}

known_questions = {
    item["id"]
    for item in context["questions"]
}

supported_methods = {
    (
        method["method_id"],
        method["version"]
    )
    for method in method_catalog
    if method["status"] == "SUPPORTED"
}

errors = []

# Mission
if proposal["mission_version"] != mission["mission_version"]:
    errors.append("Mission version mismatch.")

question = proposal["question"]

# Duplicate
if question["id"] in known_questions:
    errors.append(
        f"Question already exists: {question['id']}"
    )

# Signals
for signal_id in question.get("required_signals", []):
    if signal_id not in known_signals:
        errors.append(
            f"Unknown signal: {signal_id}"
        )

for rule in question.get(
    "evaluation_trigger",
    {}
).get("rules", []):
    if rule["signal_id"] not in known_signals:
        errors.append(
            f"Unknown trigger signal: {rule['signal_id']}"
        )

# Evaluation method
evaluation = question.get("evaluation_model")

if not evaluation:
    errors.append(
        "evaluation_model is missing."
    )
else:
    method_key = (
        evaluation["method_id"],
        evaluation["version"]
    )

    if method_key not in supported_methods:
        errors.append(
            "Unsupported evaluation method: "
            f"{evaluation['method_id']} "
            f"v{evaluation['version']}"
        )

# Novelty
metadata = proposal["reasoning_metadata"]

if (
    metadata.get("novelty_score", 0)
    < policy["limits"]["minimum_novelty_score"]
):
    errors.append("Novelty below policy threshold.")

if (
    metadata.get("coverage_gain", 0)
    < policy["limits"]["minimum_coverage_gain"]
):
    errors.append("Coverage gain below policy threshold.")

# Forbidden diagnostic claims
forbidden = [
    "diagnose",
    "diagnosis",
    "confirms syndrome",
    "has autism",
    "has adhd",
    "clinical diagnosis",
    "confirmed disorder"
]

hypothesis = question["hypothesis"].lower()

for term in forbidden:
    if term in hypothesis:
        errors.append(
            f"Forbidden diagnostic phrase: {term}"
        )

# Relation references
for field in (
    "related_questions",
    "complements",
    "contradicts"
):
    for question_id in metadata.get(field, []):
        if question_id not in known_questions:
            errors.append(
                f"Unknown question reference: {question_id}"
            )

if errors:
    print("VALIDATION: REJECTED")
    for error in errors:
        print("-", error)
    sys.exit(1)

print("VALIDATION: APPROVED")
print(
    "Question:",
    question["id"]
)
