#!/usr/bin/env python3

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PROPOSAL_FILE = ROOT / "generator/output/proposal.json"
METHODS_FILE = ROOT / "generator/methods/methods.json"
TARGET_DIR = ROOT / "data/questions"


def load_json(path: Path):
    if not path.exists():
        raise SystemExit(f"Arquivo não encontrado: {path}")

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"JSON inválido em {path}: {exc}"
        )


def load_supported_methods():
    catalog = load_json(METHODS_FILE)

    return {
        (
            method["method_id"],
            method["version"],
        )
        for method in catalog.get("methods", [])
        if method.get("status") == "SUPPORTED"
    }


def build_question_entity(proposal, supported_methods):
    question = proposal.get("question")

    if not isinstance(question, dict):
        raise SystemExit(
            "Proposal question payload is missing."
        )

    question_id = question.get("id") or question.get("question_id")
    description = question.get("description")
    hypothesis = question.get("hypothesis") or description
    signal_ids = question.get("required_signals") or question.get("signal_ids")
    method_ids = question.get("method_ids")

    if not question_id:
        raise SystemExit(
            "Proposal question_id is missing."
        )

    if not hypothesis:
        raise SystemExit(
            "Proposal question hypothesis/description is missing."
        )

    if not isinstance(signal_ids, list) or not signal_ids:
        raise SystemExit(
            "Proposal question.required_signals/signal_ids must be a non-empty list."
        )

    evaluation_model = question.get("evaluation_model")
    if not isinstance(evaluation_model, dict):
        raise SystemExit(
            "Proposal question.evaluation_model is missing or invalid."
        )

    if not method_ids:
        if evaluation_model.get("method_id"):
            method_ids = [evaluation_model.get("method_id")]

    if not isinstance(method_ids, list) or not method_ids:
        raise SystemExit(
            "Proposal question.method_ids must be a non-empty list."
        )

    if len(method_ids) != 1:
        raise SystemExit(
            "QUESTION_CREATE currently requires exactly one evaluation method."
        )

    method_id = method_ids[0]

    matching_versions = sorted(
        version
        for candidate_method_id, version in supported_methods
        if candidate_method_id == method_id
    )

    if not matching_versions:
        raise SystemExit(
            f"Unsupported evaluation method: {method_id}"
        )

    method_version = matching_versions[-1]

    evaluation_trigger = question.get("evaluation_trigger")
    evidence_model = question.get("evidence_model")
    cortex_weights = question.get("cortex_weights")

    if not isinstance(evaluation_trigger, dict):
        raise SystemExit(
            "Proposal question.evaluation_trigger is missing or invalid."
        )

    if not isinstance(evidence_model, dict):
        raise SystemExit(
            "Proposal question.evidence_model is missing or invalid."
        )

    if not isinstance(cortex_weights, dict):
        raise SystemExit(
            "Proposal question.cortex_weights is missing or invalid."
        )

    evaluation_method_id = evaluation_model.get("method_id")
    evaluation_version = evaluation_model.get("version")
    parameters = evaluation_model.get("parameters")

    if evaluation_method_id != method_id:
        raise SystemExit(
            "evaluation_model.method_id does not match question.method_ids."
        )

    if evaluation_version != method_version:
        raise SystemExit(
            "evaluation_model.version does not match the supported method version."
        )

    if not isinstance(parameters, dict):
        raise SystemExit(
            "evaluation_model.parameters must be an object."
        )

    logical_operator = evaluation_trigger.get("logical_operator")
    rules = evaluation_trigger.get("rules")

    if logical_operator not in {"AND", "OR"}:
        raise SystemExit(
            "evaluation_trigger.logical_operator must be AND or OR."
        )

    if not isinstance(rules, list) or not rules:
        raise SystemExit(
            "evaluation_trigger.rules must be a non-empty list."
        )

    required_signal_set = set(signal_ids)

    operator_map = {
        "GREATER_THAN": ">",
        "LESS_THAN": "<",
        "GREATER_THAN_OR_EQUAL": ">=",
        "LESS_THAN_OR_EQUAL": "<=",
        "EQUAL": "==",
        "NOT_EQUAL": "!=",
    }

    normalized_rules = []

    for rule in rules:
        if not isinstance(rule, dict):
            raise SystemExit(
                "Each evaluation_trigger rule must be an object."
            )

        rule_signal_id = rule.get("signal_id")

        if rule_signal_id not in required_signal_set:
            raise SystemExit(
                "evaluation_trigger contains a signal not present in question.signal_ids."
            )

        operator = rule.get("operator")

        if operator in operator_map:
            operator = operator_map[operator]

        if operator not in {
            ">", "<", ">=", "<=", "==", "!="
        }:
            raise SystemExit(
                f"evaluation_trigger rule contains an unsupported operator: {operator}"
            )

        threshold = rule.get("threshold")
        if not isinstance(threshold, (int, float)):
            raise SystemExit(
                "evaluation_trigger rule threshold must be a number."
            )

        window_ms = rule.get("window_ms")
        if not isinstance(window_ms, (int, float)) or int(window_ms) < 1:
            raise SystemExit(
                "evaluation_trigger rule window_ms must be an integer >= 1."
            )

        normalized_rules.append({
            "signal_id": rule_signal_id,
            "operator": operator,
            "threshold": float(threshold) if isinstance(threshold, float) else threshold,
            "window_ms": int(window_ms),
        })

    evidence_signals = proposal.get("evidence_basis", {}).get("signals")

    if not isinstance(evidence_signals, list):
        raise SystemExit(
            "Proposal evidence_basis.signals is missing or invalid."
        )

    if set(evidence_signals) != required_signal_set:
        raise SystemExit(
            "Evidence signals do not match question.signal_ids."
        )

    for field in ("base_strength", "decay_rate_per_sec"):
        val = evidence_model.get(field)
        if not isinstance(val, (int, float)) or not (0.0 <= float(val) <= 1.0):
            raise SystemExit(
                f"evidence_model.{field} must be a number between 0.0 and 1.0."
            )

    for field in ("focus", "stress", "autonomy", "fatigue"):
        val = cortex_weights.get(field)
        if not isinstance(val, (int, float)) or not (-1.0 <= float(val) <= 1.0):
            raise SystemExit(
                f"cortex_weights.{field} must be a number between -1.0 and 1.0."
            )

    domain = proposal.get("domain")
    if not domain:
        raise SystemExit(
            "Proposal domain is missing."
        )

    question_entity = {
        "id": question_id,
        "hypothesis": hypothesis,
        "required_signals": signal_ids,
        "evaluation_trigger": {
            "logical_operator": logical_operator,
            "rules": normalized_rules,
        },
        "evaluation_model": {
            "method_id": evaluation_method_id,
            "version": evaluation_version,
            "parameters": parameters,
        },
        "evidence_model": {
            "base_strength": float(evidence_model["base_strength"]),
            "decay_rate_per_sec": float(evidence_model["decay_rate_per_sec"]),
        },
        "cortex_weights": {
            "focus": float(cortex_weights["focus"]),
            "stress": float(cortex_weights["stress"]),
            "autonomy": float(cortex_weights["autonomy"]),
            "fatigue": float(cortex_weights["fatigue"]),
        },
    }

    return question_entity


def main():
    proposal_doc = load_json(PROPOSAL_FILE)

    if proposal_doc.get("status") == "NO_PROPOSAL":
        print("Nothing to publish.")
        return 0

    if proposal_doc.get("status") != "PROPOSAL_READY":
        print("ERROR: proposal is not ready.")
        return 1

    proposal = proposal_doc.get("proposal")

    if not isinstance(proposal, dict):
        print("ERROR: proposal is missing or invalid.")
        return 1

    operation = proposal.get("operation")

    if operation != "QUESTION_CREATE":
        print(
            f"ERROR: unsupported publish operation: {operation}"
        )
        return 1

    supported_methods = load_supported_methods()

    try:
        question = build_question_entity(
            proposal,
            supported_methods,
        )
    except SystemExit as exc:
        print(f"ERROR: {exc}")
        return 1

    question_id = question["id"]

    target = TARGET_DIR / f"{question_id}.json"

    if target.exists():
        print(
            f"ERROR: question already exists: {target}"
        )
        return 1

    TARGET_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    target.write_text(
        json.dumps(
            question,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print("Published:", target)

    return 0


if __name__ == "__main__":
    sys.exit(main())
