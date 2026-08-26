from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

MISSION_FILE = ROOT / "mission/mission.json"
POLICY_FILE = ROOT / "evolution/evolution-policy.json"

SIGNALS_DIR = ROOT / "data/signals"
QUESTIONS_DIR = ROOT / "data/questions"
RELATIONS_DIR = ROOT / "data/relations"
METHODS_FILE = ROOT / "generator/methods/methods.json"

AGENT_CONTEXT_FILE = ROOT / "generator/input/agent_context.json"
CURRENT_CONTEXT_FILE = (
    ROOT / "generator/input/current_knowledge_context.json"
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def read_many(directory: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    if not directory.exists():
        return result

    for path in sorted(directory.glob("*.json")):
        result.append(
            json.loads(
                path.read_text(encoding="utf-8")
            )
        )

    return result


def get_id(item: dict[str, Any]) -> str | None:
    return (
        item.get("id")
        or item.get("question_id")
        or item.get("signal_id")
        or item.get("relation_id")
        or item.get("method_id")
        or item.get("opportunity_id")
    )


def get_domain(item: dict[str, Any]) -> str | None:
    domain = item.get("domain")

    if isinstance(domain, str):
        return domain

    return None


def collect_ids(
    items: list[dict[str, Any]]
) -> set[str]:
    return {
        item_id
        for item in items
        if (item_id := get_id(item)) is not None
    }


def extract_question_signal_ids(
    question: dict[str, Any]
) -> list[str]:
    candidates = (
        question.get("signal_ids")
        or question.get("signals")
        or question.get("required_signals")
        or []
    )

    if not isinstance(candidates, list):
        return []

    result = []

    for item in candidates:
        if isinstance(item, str):
            result.append(item)

        elif isinstance(item, dict):
            item_id = (
                item.get("id")
                or item.get("signal_id")
            )

            if item_id:
                result.append(item_id)

    return result


def extract_question_method_id(
    question: dict[str, Any]
) -> str | None:
    method = (
        question.get("method_id")
        or question.get("evaluation_method")
    )

    if isinstance(method, str):
        return method

    if isinstance(method, dict):
        return (
            method.get("id")
            or method.get("method_id")
        )

    return None


def extract_relation_targets(
    relation: dict[str, Any]
) -> list[str]:
    result = []

    for key in (
        "source",
        "source_id",
        "source_question_id",
        "target",
        "target_id",
        "target_question_id"
    ):
        value = relation.get(key)

        if isinstance(value, str):
            result.append(value)

    return result


def build_derived_state(
    mission: dict[str, Any],
    signals: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    methods: list[dict[str, Any]],
) -> dict[str, Any]:

    signal_ids = collect_ids(signals)
    question_ids = collect_ids(questions)
    method_ids = collect_ids(methods)
    relation_ids = collect_ids(relations)

    mission_domains = set(
        mission.get("domains", [])
    )

    question_domains = {
        domain
        for question in questions
        if (domain := get_domain(question))
    }

    domains_with_questions = sorted(
        question_domains
    )

    domains_without_questions = sorted(
        mission_domains - question_domains
    )

    questions_without_signals = []
    questions_without_methods = []

    for question in questions:
        question_id = get_id(question)

        if not question_id:
            continue

        required_signals = extract_question_signal_ids(
            question
        )

        missing_signals = [
            signal_id
            for signal_id in required_signals
            if signal_id not in signal_ids
        ]

        if missing_signals:
            questions_without_signals.append(
                {
                    "question_id": question_id,
                    "missing_signals": missing_signals
                }
            )

        method_id = extract_question_method_id(
            question
        )

        if method_id and method_id not in method_ids:
            questions_without_methods.append(
                {
                    "question_id": question_id,
                    "missing_method": method_id
                }
            )

    relations_with_missing_targets = []

    valid_graph_ids = (
        question_ids
        | signal_ids
        | relation_ids
    )

    for relation in relations:
        relation_id = get_id(relation)

        if not relation_id:
            continue

        targets = extract_relation_targets(
            relation
        )

        missing_targets = [
            target
            for target in targets
            if target not in valid_graph_ids
        ]

        if missing_targets:
            relations_with_missing_targets.append(
                {
                    "relation_id": relation_id,
                    "missing_targets": missing_targets
                }
            )

    relation_question_ids = set()

    for relation in relations:
        for target in extract_relation_targets(
            relation
        ):
            if target in question_ids:
                relation_question_ids.add(target)

    questions_without_relations = sorted(
        question_ids - relation_question_ids
    )

    return {
        "signal_count": len(signals),
        "question_count": len(questions),
        "relation_count": len(relations),
        "method_count": len(methods),

        "domains_with_questions":
            domains_with_questions,

        "domains_without_questions":
            domains_without_questions,

        "questions_without_relations":
            questions_without_relations,

        "relations_with_missing_targets":
            relations_with_missing_targets,

        "questions_with_missing_signals":
            questions_without_signals,

        "questions_with_missing_methods":
            questions_without_methods
    }


def build_context() -> dict[str, Any]:
    mission = read_json(MISSION_FILE)
    evolution_policy = read_json(POLICY_FILE)

    signals = read_many(SIGNALS_DIR)
    questions = read_many(QUESTIONS_DIR)
    relations = read_many(RELATIONS_DIR)

    methods_document = read_json(METHODS_FILE)

    methods = methods_document.get(
        "methods",
        []
    )

    if not isinstance(methods, list):
        methods = []

    return {
        "mission": mission,
        "evolution_policy": evolution_policy,
        "signals": signals,
        "questions": questions,
        "relations": relations,
        "methods": methods
    }


def build_current_knowledge_context(
    context: dict[str, Any]
) -> dict[str, Any]:

    mission = context["mission"]
    evolution_policy = context["evolution_policy"]
    signals = context["signals"]
    questions = context["questions"]
    relations = context["relations"]
    methods = context["methods"]

    derived_state = build_derived_state(
        mission=mission,
        signals=signals,
        questions=questions,
        relations=relations,
        methods=methods
    )

    return {
        "context_version": "1.0.0",

        "context_type":
            "CURRENT_KNOWLEDGE_CONTEXT",

        "purpose":
            "Representar exclusivamente o estado atual conhecido "
            "do Knowledge Graph do PyHok para uso pelo agente "
            "de evolução.",

        "authority": {
            "source": "repository",

            "rule":
                "Somente informações presentes no estado atual "
                "do repositório são consideradas conhecidas.",

            "unknown_policy":
                "Tudo que não estiver presente deve ser tratado "
                "como UNKNOWN."
        },

        "mission": mission,

        "evolution_policy": evolution_policy,

        "knowledge_graph": {
            "signals": signals,
            "questions": questions,
            "relations": relations,
            "methods": methods
        },

        "derived_state": derived_state,

        "constraints": {
            "must_not_invent_signals": True,
            "must_not_invent_questions": True,
            "must_not_invent_methods": True,
            "must_not_invent_relations": True,
            "must_not_invent_runtime_capabilities": True,
            "must_not_invent_identifiers": True,
            "must_preserve_uncertainty": True,
            "must_preserve_individual_variability": True,
            "must_remain_non_diagnostic": True,
            "must_use_existing_evaluation_methods": True
        },

        "status": {
            "state": "CURRENT",
            "generated_from_repository": True
        }
    }


def write_json(
    path: Path,
    data: dict[str, Any]
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )


def main() -> None:
    context = build_context()

    write_json(
        AGENT_CONTEXT_FILE,
        context
    )

    current_context = (
        build_current_knowledge_context(
            context
        )
    )

    write_json(
        CURRENT_CONTEXT_FILE,
        current_context
    )

    derived = current_context[
        "derived_state"
    ]

    print(
        f"Agent context written to "
        f"{AGENT_CONTEXT_FILE}"
    )

    print(
        f"Current knowledge context written to "
        f"{CURRENT_CONTEXT_FILE}"
    )

    print("Knowledge graph:")

    print(
        f"  signals: "
        f"{derived['signal_count']}"
    )

    print(
        f"  questions: "
        f"{derived['question_count']}"
    )

    print(
        f"  relations: "
        f"{derived['relation_count']}"
    )

    print(
        f"  methods: "
        f"{derived['method_count']}"
    )

    print(
        f"  domains without questions: "
        f"{len(derived['domains_without_questions'])}"
    )

    print(
        f"  questions without relations: "
        f"{len(derived['questions_without_relations'])}"
    )

    print(
        f"  questions with missing signals: "
        f"{len(derived['questions_with_missing_signals'])}"
    )

    print(
        f"  questions with missing methods: "
        f"{len(derived['questions_with_missing_methods'])}"
    )

    print(
        f"  relations with missing targets: "
        f"{len(derived['relations_with_missing_targets'])}"
    )


if __name__ == "__main__":
    main()
