import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROPOSAL_FILE = ROOT / "generator/output/proposal.json"
MISSION_FILE = ROOT / "mission/mission.json"
POLICY_FILE = ROOT / "evolution/evolution-policy.json"
METHODS_FILE = ROOT / "generator/methods/methods.json"
SIGNALS_DIR = ROOT / "data/signals"
QUESTIONS_DIR = ROOT / "data/questions"
RELATIONS_DIR = ROOT / "data/relations"


def load_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"Missing required file: {path}")

    return json.loads(
        path.read_text(encoding="utf-8")
    )


proposal_doc = load_json(PROPOSAL_FILE)

if proposal_doc.get("status") == "NO_PROPOSAL":
    print("VALIDATION: NO_PROPOSAL")
    sys.exit(0)

proposal = proposal_doc.get("proposal")

if not isinstance(proposal, dict) or not proposal:
    print("VALIDATION: REJECTED")
    print("- proposal is missing or empty")
    sys.exit(1)

mission = load_json(MISSION_FILE)
policy = load_json(POLICY_FILE)
methods = load_json(METHODS_FILE)

known_signals = set()
known_questions = set()

for path in SIGNALS_DIR.glob("*.json"):
    signal = load_json(path)
    signal_id = signal.get("id")

    if signal_id:
        known_signals.add(signal_id)

for path in QUESTIONS_DIR.glob("*.json"):
    question = load_json(path)
    question_id = question.get("id")

    if question_id:
        known_questions.add(question_id)

errors = []

# ------------------------------------------------------------
# Proposal metadata
# ------------------------------------------------------------

mission_version = proposal.get("mission_version")

if mission_version != mission.get("mission_version"):
    errors.append(
        "Mission version mismatch."
    )

# ------------------------------------------------------------
# Question
# ------------------------------------------------------------

question = proposal.get("question")

if not isinstance(question, dict):
    errors.append(
        "Question payload is missing."
    )
else:

    question_id = question.get("id")

    if not question_id:
        errors.append(
            "Question id is missing."
        )

    elif question_id in known_questions:
        errors.append(
            f"Question already exists: {question_id}"
        )

    hypothesis = question.get(
        "hypothesis",
        ""
    ).lower()

    forbidden_terms = [
        "diagnose",
        "diagnosis",
        "confirms syndrome",
        "clinical diagnosis",
        "confirmed disorder",
        "has autism",
        "has adhd"
    ]

    for term in forbidden_terms:
        if term in hypothesis:
            errors.append(
                f"Forbidden diagnostic language: {term}"
            )

    # --------------------------------------------------------
    # Required signals
    # --------------------------------------------------------

    for signal_id in question.get(
        "required_signals",
        []
    ):
        if signal_id not in known_signals:
            errors.append(
                f"Unknown signal: {signal_id}"
            )

    # --------------------------------------------------------
    # Trigger signals
    # --------------------------------------------------------

    trigger = question.get(
        "evaluation_trigger",
        {}
    )

    for rule in trigger.get(
        "rules",
        []
    ):
        signal_id = rule.get(
            "signal_id"
        )

        if signal_id not in known_signals:
            errors.append(
                f"Unknown trigger signal: {signal_id}"
            )

    # --------------------------------------------------------
    # Evaluation method
    # --------------------------------------------------------

    evaluation_model = question.get(
        "evaluation_model"
    )

    if not isinstance(
        evaluation_model,
        dict
    ):
        errors.append(
            "evaluation_model is missing."
        )
    else:
        method_id = evaluation_model.get(
            "method_id"
        )

        method_version = evaluation_model.get(
            "version"
        )

        supported = any(
            method.get("status") == "SUPPORTED"
            and method.get("method_id") == method_id
            and method.get("version") == method_version
            for method in methods.get(
                "methods",
                []
            )
        )

        if not supported:
            errors.append(
                "Unsupported evaluation method: "
                f"{method_id} v{method_version}"
            )

    # --------------------------------------------------------
    # Cortex weights
    # --------------------------------------------------------

    weights = question.get(
        "cortex_weights"
    )

    if not isinstance(
        weights,
        dict
    ):
        errors.append(
            "cortex_weights is missing."
        )
    else:
        for dimension in (
            "focus",
            "stress",
            "autonomy",
            "fatigue"
        ):
            value = weights.get(
                dimension
            )

            if not isinstance(
                value,
                (int, float)
            ):
                errors.append(
                    f"Invalid cortex weight: {dimension}"
                )

            elif not -1.0 <= value <= 1.0:
                errors.append(
                    f"Cortex weight out of range: {dimension}"
                )

# ------------------------------------------------------------
# Reasoning metadata
# ------------------------------------------------------------

metadata = proposal.get(
    "reasoning_metadata"
)

if not isinstance(
    metadata,
    dict
):
    errors.append(
        "reasoning_metadata is missing."
    )
else:

    novelty = metadata.get(
        "novelty_score",
        0.0
    )

    coverage_gain = metadata.get(
        "coverage_gain",
        0.0
    )

    minimum_novelty = policy[
        "limits"
    ][
        "minimum_novelty_score"
    ]

    minimum_coverage = policy[
        "limits"
    ][
        "minimum_coverage_gain"
    ]

    if novelty < minimum_novelty:
        errors.append(
            "Novelty below policy threshold."
        )

    if coverage_gain < minimum_coverage:
        errors.append(
            "Coverage gain below policy threshold."
        )

    for field in (
        "related_questions",
        "complements",
        "contradicts"
    ):
        for question_id in metadata.get(
            field,
            []
        ):
            if question_id not in known_questions:
                errors.append(
                    f"Unknown related question: {question_id}"
                )

# ------------------------------------------------------------
# Final decision
# ------------------------------------------------------------

if errors:
    print("VALIDATION: REJECTED")

    for error in errors:
        print(f"- {error}")

    sys.exit(1)

print("VALIDATION: APPROVED")
print(
    "Question:",
    proposal["question"]["id"]
)
print(
    "Mission:",
    mission["mission_version"]
)
