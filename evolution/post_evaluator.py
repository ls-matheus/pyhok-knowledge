from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
EVALUATIONS_FILE = ROOT / "evolution/post_evaluations.jsonl"
MISSION_FILE = ROOT / "mission/mission.json"

MIN_COVERAGE_EFFECT = 0.05
MAX_REDUNDANCY_LIMIT = 0.70


def extract_domains_from_questions(questions: list[dict[str, Any]], mission_domains: list[str]) -> set[str]:
    covered = set()
    for q in questions:
        # Check explicit domain
        dom = q.get("domain")
        if isinstance(dom, str) and dom in mission_domains:
            covered.add(dom)
            continue
        # Check question ID pattern
        qid = q.get("id", "")
        for m_dom in mission_domains:
            if m_dom in qid:
                covered.add(m_dom)
    return covered


def compute_jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def evaluate_proposal_impact(
    state_before: dict[str, Any],
    proposal: dict[str, Any],
    state_after: dict[str, Any],
    max_redundancy_threshold: float = MAX_REDUNDANCY_LIMIT,
    min_effect_size: float = MIN_COVERAGE_EFFECT,
) -> dict[str, Any]:
    """
    Evaluates empirical multi-dimensional impact of an evolution proposal using objective graph metrics.
    """
    questions_before = state_before.get("questions", [])
    questions_after = state_after.get("questions", [])
    signals_before = state_before.get("signals", [])
    relations_before = state_before.get("relations", [])
    relations_after = state_after.get("relations", [])

    # Load mission domains
    mission_domains = []
    if MISSION_FILE.exists():
        try:
            m_data = json.loads(MISSION_FILE.read_text(encoding="utf-8"))
            for d in m_data.get("domains", []):
                if isinstance(d, str):
                    mission_domains.append(d)
                elif isinstance(d, dict) and d.get("name"):
                    mission_domains.append(d["name"])
        except Exception:
            pass
    total_domains = max(1, len(mission_domains))

    # 1. Domain Coverage Delta
    domains_before = extract_domains_from_questions(questions_before, mission_domains)
    domains_after = extract_domains_from_questions(questions_after, mission_domains)
    new_domains = domains_after - domains_before
    domain_coverage_delta = len(new_domains) / total_domains

    # 2. Signal Coverage Delta
    sigs_used_before = {s for q in questions_before for s in q.get("required_signals", [])}
    sigs_used_after = {s for q in questions_after for s in q.get("required_signals", [])}
    new_sigs = sigs_used_after - sigs_used_before
    total_available_signals = max(1, len(signals_before))
    signal_coverage_delta = len(new_sigs) / total_available_signals

    # 3. Graph Expansion Delta
    graph_size_before = len(questions_before) + len(relations_before)
    graph_size_after = len(questions_after) + len(relations_after)
    graph_expansion_delta = max(0.0, (graph_size_after - graph_size_before) / max(1, graph_size_before))

    # General coverage gain metric (blended signal/domain)
    coverage_gain = max(domain_coverage_delta, signal_coverage_delta, graph_expansion_delta if len(questions_after) > len(questions_before) else 0.0)

    # 4. Redundancy Calculation (Jaccard Similarity over Required Signals)
    prop_q = proposal.get("question", {})
    prop_signals = set(prop_q.get("required_signals", []))
    jaccard_scores = []

    for q in questions_before:
        if q.get("id") == prop_q.get("id"):
            continue
        q_sigs = set(q.get("required_signals", []))
        jaccard_scores.append(compute_jaccard_similarity(prop_signals, q_sigs))

    redundancy = max(jaccard_scores, default=0.0)
    novelty = 1.0 - redundancy

    # 5. Regression Detection
    regression = False
    regression_type = None

    ids_before = {q.get("id") for q in questions_before if q.get("id")}
    ids_after = {q.get("id") for q in questions_after if q.get("id")}

    if not ids_before.issubset(ids_after):
        regression = True
        regression_type = "unexpected_deletion"

    # 6. Multi-Dimensional Improvement Invariant
    has_meaningful_gain = (
        domain_coverage_delta > 0.0
        or signal_coverage_delta >= min_effect_size
        or (len(questions_after) > len(questions_before) and redundancy < max_redundancy_threshold)
    )

    actually_improved = (
        has_meaningful_gain
        and redundancy <= max_redundancy_threshold
        and not regression
    )

    return {
        "observed": {
            "novelty": round(novelty, 4),
            "coverage_gain": round(coverage_gain, 4),
            "domain_coverage_delta": round(domain_coverage_delta, 4),
            "signal_coverage_delta": round(signal_coverage_delta, 4),
            "graph_expansion_delta": round(graph_expansion_delta, 4),
            "redundancy": round(redundancy, 4),
            "regression": regression,
            "regression_type": regression_type,
        },
        "actually_improved": actually_improved,
        "evaluation_timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
    }


def attach_post_evaluation(
    cycle_id: str,
    evaluation_result: dict[str, Any],
    evaluations_path: Path = EVALUATIONS_FILE,
) -> None:
    """
    Appends an independent post-evaluation record to the evaluations journal without altering the immutable ledger.
    """
    evaluations_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "cycle_id": cycle_id,
        "post_evaluation": evaluation_result,
        "recorded_at": datetime.now(ZoneInfo("UTC")).isoformat(),
    }
    with open(evaluations_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
