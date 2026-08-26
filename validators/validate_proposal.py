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


def load_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"Missing required file: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def collect_ids(directory: Path):
    ids = set()

    if not directory.exists():
        return ids

    for path in directory.glob("*.json"):
        document = load_json(path)
        value = document.get("id")

        if value:
            ids.add(value)

    return ids


def contains_forbidden_language(value):
    if not isinstance(value, str):
        return False

    text = value.lower()

    forbidden_terms = [
        "diagnose",
        "diagnosis",
        "confirms syndrome",
        "clinical diagnosis",
        "confirmed disorder",
        "has autism",
        "has adhd",
    ]

    return [
        term
        for term in forbidden_terms
        if term in text
    ]


def validate_question_create(
    proposal,
    mission,
    policy,
    methods,
    known_signals,
    known_questions,
):
    errors = []

    question = proposal.get("question")

    if not isinstance(question, dict):
        return ["Question payload is missing."]

    question_id = question.get("id")

    if not question_id:
        errors.append("Question id is missing.")
    elif question_id in known_questions:
        errors.append(
            f"Question already exists: {question_id}"
        )

    domain = proposal.get("domain")

    if domain not in mission.get("domains", []):
        errors.append(
            f"Unknown mission domain: {domain}"
        )

    # ------------------------------------------------------------
    # QuestionEntity v2 structure
    # ------------------------------------------------------------

    required_question_fields = [
        "id",
        "hypothesis",
        "required_signals",
        "evaluation_trigger",
        "evaluation_model",
        "evidence_model",
        "cortex_weights",
    ]

    for field in required_question_fields:
        if field not in question:
            errors.append(
                f"question.{field} is missing."
            )

    # ------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------

    signal_ids = question.get("required_signals", [])

    if not isinstance(signal_ids, list):
        errors.append(
            "question.required_signals must be a list."
        )
        signal_ids = []

    for signal_id in signal_ids:
        if signal_id not in known_signals:
            errors.append(
                f"Unknown signal: {signal_id}"
            )

    # ------------------------------------------------------------
    # Evaluation trigger
    # ------------------------------------------------------------

    trigger = question.get(
        "evaluation_trigger",
        {},
    )

    if not isinstance(trigger, dict):
        errors.append(
            "question.evaluation_trigger must be an object."
        )
        trigger = {}

    rules = trigger.get("rules", [])

    if not isinstance(rules, list):
        errors.append(
            "question.evaluation_trigger.rules must be a list."
        )
        rules = []

    trigger_signal_ids = []

    for rule in rules:
        if not isinstance(rule, dict):
            errors.append(
                "Evaluation trigger rule must be an object."
            )
            continue

        signal_id = rule.get("signal_id")

        if signal_id:
            trigger_signal_ids.append(signal_id)

            if signal_id not in known_signals:
                errors.append(
                    f"Unknown trigger signal: {signal_id}"
                )

    for signal_id in trigger_signal_ids:
        if signal_id not in signal_ids:
            errors.append(
                "Trigger signal is not declared in "
                "question.required_signals: "
                f"{signal_id}"
            )

    # ------------------------------------------------------------
    # Evaluation method
    # ------------------------------------------------------------

    evaluation_model = question.get(
        "evaluation_model",
        {},
    )

    if not isinstance(evaluation_model, dict):
        errors.append(
            "question.evaluation_model must be an object."
        )
        evaluation_model = {}

    method_id = evaluation_model.get("method_id")
    version = evaluation_model.get("version")

    supported_methods = {
        (
            method.get("method_id"),
            method.get("version"),
        )
        for method in methods.get("methods", [])
        if method.get("status") == "SUPPORTED"
    }

    if not method_id:
        errors.append(
            "question.evaluation_model.method_id is missing."
        )

    if not version:
        errors.append(
            "question.evaluation_model.version is missing."
        )

    if method_id and version:
        if (method_id, version) not in supported_methods:
            errors.append(
                "Unsupported evaluation method: "
                f"{method_id} v{version}"
            )

    # ------------------------------------------------------------
    # Evidence consistency
    # ------------------------------------------------------------

    evidence = proposal.get("evidence_basis")

    if not isinstance(evidence, dict):
        errors.append(
            "evidence_basis is missing."
        )
    else:
        evidence_signals = evidence.get("signals", [])
        evidence_methods = evidence.get("methods", [])

        if sorted(evidence_signals) != sorted(signal_ids):
            errors.append(
                "Evidence signals do not match "
                "question.required_signals."
            )

        if method_id:
            expected_methods = [method_id]

            if sorted(evidence_methods) != sorted(expected_methods):
                errors.append(
                    "Evidence methods do not match "
                    "question.evaluation_model.method_id."
                )

    # ------------------------------------------------------------
    # Structured justification
    # ------------------------------------------------------------

    required_justifications = [
        "rationale",
        "novelty_justification",
        "computability_justification",
        "individuality_justification",
        "uncertainty_justification",
    ]

    for field in required_justifications:
        value = proposal.get(field)

        if not isinstance(value, str) or not value.strip():
            errors.append(
                f"{field} is missing."
            )

    # ------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------

    confidence = proposal.get("confidence")

    minimum_confidence = policy.get(
        "limits",
        {},
    ).get(
        "minimum_confidence_in_proposal",
        0.0,
    )

    if not isinstance(confidence, (int, float)):
        errors.append(
            "confidence is missing or invalid."
        )
    elif not 0.0 <= confidence <= 1.0:
        errors.append(
            "confidence must be between 0 and 1."
        )
    elif confidence < minimum_confidence:
        errors.append(
            "Confidence below policy threshold."
        )

    # ------------------------------------------------------------
    # Forbidden language
    # ------------------------------------------------------------

    text_fields = [
        "rationale",
        "novelty_justification",
        "computability_justification",
        "individuality_justification",
        "uncertainty_justification",
    ]

    hypothesis = question.get(
        "hypothesis",
        "",
    )

    text_values = [hypothesis]

    for field in text_fields:
        text_values.append(
            proposal.get(field, "")
        )

    for value in text_values:
        for term in contains_forbidden_language(value):
            errors.append(
                f"Forbidden diagnostic language: {term}"
            )

    # ------------------------------------------------------------
    # Mission scope
    # ------------------------------------------------------------

    if mission.get("scope", {}).get(
        "runtime_execution"
    ) is True:
        errors.append(
            "Mission runtime scope is invalid."
        )

    if mission.get("scope", {}).get(
        "diagnosis"
    ) is True:
        errors.append(
            "Mission diagnosis scope is invalid."
        )

    return errors

def main():
    proposal_doc = load_json(PROPOSAL_FILE)

    if proposal_doc.get("status") == "NO_PROPOSAL":
        print("VALIDATION: NO_PROPOSAL")
        return 0

    if proposal_doc.get("status") != "PROPOSAL_READY":
        print("VALIDATION: REJECTED")
        print("- Invalid proposal status.")
        return 1

    proposal = proposal_doc.get("proposal")

    if not isinstance(proposal, dict) or not proposal:
        print("VALIDATION: REJECTED")
        print("- proposal is missing or empty")
        return 1

    mission = load_json(MISSION_FILE)
    policy = load_json(POLICY_FILE)
    methods = load_json(METHODS_FILE)

    known_signals = collect_ids(SIGNALS_DIR)
    known_questions = collect_ids(QUESTIONS_DIR)

    errors = []

    # ------------------------------------------------------------
    # Operation
    # ------------------------------------------------------------

    operation = proposal.get("operation")

    allowed_operations = policy.get(
        "allowed_proposal_types",
        []
    )

    if operation not in allowed_operations:
        errors.append(
            f"Operation not allowed by policy: {operation}"
        )

    # ------------------------------------------------------------
    # Proposal identity
    # ------------------------------------------------------------

    if not proposal.get("proposal_id"):
        errors.append(
            "proposal_id is missing."
        )

    if not proposal.get("opportunity_id"):
        errors.append(
            "opportunity_id is missing."
        )

    # ------------------------------------------------------------
    # QUESTION_CREATE
    # ------------------------------------------------------------

    if operation == "QUESTION_CREATE":
        errors.extend(
            validate_question_create(
                proposal=proposal,
                mission=mission,
                policy=policy,
                methods=methods,
                known_signals=known_signals,
                known_questions=known_questions,
            )
        )

    # ------------------------------------------------------------
    # Final decision
    # ------------------------------------------------------------

    if errors:
        print("VALIDATION: REJECTED")

        for error in errors:
            print(f"- {error}")

        return 1

    print("VALIDATION: APPROVED")
    print(
        "Proposal:",
        proposal["proposal_id"],
    )
    print(
        "Operation:",
        proposal["operation"],
    )
    print(
        "Domain:",
        proposal.get("domain"),
    )
    print(
        "Question:",
        proposal["question"]["id"],
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
