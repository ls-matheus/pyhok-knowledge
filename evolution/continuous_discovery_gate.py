from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.graph.knowledge_graph import KnowledgeGraph, CyclicProvenanceError
from evolution.discovery.discovery_engine import EpistemicDiscoveryEngine
from evolution.epistemic.synapse import SinapseBindingEngine
from evolution.epistemic.verifier import EvidenceVerifier


def run_continuous_discovery_gate(knowledge_state: dict[str, Any] | None = None) -> tuple[bool, list[str]]:
    errors: list[str] = []

    # 1. Verify Knowledge Graph DAG Acyclicity on Dataset
    graph = KnowledgeGraph()
    if knowledge_state:
        try:
            graph.build_from_dataset(knowledge_state)
        except CyclicProvenanceError as exc:
            errors.append(f"Knowledge graph dataset contains circular provenance: {exc}")

    # 2. Verify Discovery Engine Opportunity Generation & Score Bounds
    discovery = EpistemicDiscoveryEngine()
    test_state = {
        "signals": [
            {"id": "sig_pointer_velocity", "domain": "motor_control"},
            {"id": "sig_reaction_time", "domain": "timing"},
        ],
        "questions": []
    }
    opportunities = discovery.detect_opportunities(test_state)
    if not opportunities:
        errors.append("Discovery engine failed to identify opportunities from unlinked signals.")
    else:
        for opp in opportunities:
            for score_key in ("novelty_score", "information_gain_score", "exploration_priority"):
                val = opp.get(score_key)
                if val is None or not isinstance(val, (int, float)) or not math.isfinite(val) or not (0.0 <= val <= 1.0):
                    errors.append(f"Opportunity {opp.get('opportunity_id')} has invalid score {score_key}={val}")

    # 3. Verify Open Thesis Variable Taxonomy & Synapse Non-Fabrication
    if opportunities:
        thesis = discovery.generate_open_thesis(opportunities[0])
        open_vars = thesis.get("open_variables", [])
        if not open_vars:
            errors.append("Open thesis generated zero open variables.")
        for v in open_vars:
            stat = v.get("status")
            if stat not in ("UNBOUND", "CANDIDATE", "BOUND", "INVALID"):
                errors.append(f"Open variable {v.get('id')} has invalid status taxonomy: {stat}")

        # Bind against empty context -> must remain UNBOUND (Honesty principle)
        synapse = SinapseBindingEngine()
        bound = synapse.prepare_or_bind(thesis, context={})
        unbound_vars = [v for v in bound.get("open_variables", []) if v.get("status") == "UNBOUND"]
        if not unbound_vars:
            errors.append("Synapse fabricated bindings on empty context (violation of Closed-World Honesty).")

        # 4. Verify Evidence Verifier blocks DERIVED status on Synapse-only bindings
        verifier = EvidenceVerifier()
        prop = {"question": bound}
        v_res = verifier.verify_provenance(prop)
        if v_res.get("eligible_for_derived_status") is True:
            errors.append("EvidenceVerifier illegally granted DERIVED status to unrooted bound thesis.")

    return len(errors) == 0, errors


def main() -> int:
    # Load canonical dataset for verification
    data_dir = ROOT / "data"
    signals_dir = data_dir / "signals"
    questions_dir = data_dir / "questions"
    relations_dir = data_dir / "relations"

    state: dict[str, Any] = {"signals": [], "questions": [], "relations": []}
    if signals_dir.exists():
        for p in signals_dir.glob("*.json"):
            try:
                state["signals"].append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
    if questions_dir.exists():
        for p in questions_dir.glob("*.json"):
            try:
                state["questions"].append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
    if relations_dir.exists():
        for p in relations_dir.glob("*.json"):
            try:
                state["relations"].append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass

    passed, errs = run_continuous_discovery_gate(state)
    if not passed:
        print("[GATE_FAIL] continuous_discovery_gate detected violations:")
        for e in errs:
            print(f"  - {e}")
        return 1

    print("[GATE_PASS] continuous_discovery_gate: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
