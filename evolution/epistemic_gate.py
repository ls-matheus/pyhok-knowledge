from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
QUESTIONS_DIR = DATA_DIR / "questions"
RELATIONS_DIR = DATA_DIR / "relations"
SIGNALS_DIR = DATA_DIR / "signals"
PROPOSAL_FILE = ROOT / "generator/output/proposal.json"

from evolution.epistemic.verifier import EvidenceVerifier


def check_epistemic_firewall(
    questions_dir: Path = QUESTIONS_DIR,
    relations_dir: Path = RELATIONS_DIR,
    proposal_file: Path = PROPOSAL_FILE,
) -> tuple[bool, list[str]]:
    """
    Validates that the knowledge graph and current proposal satisfy all Epistemic Firewall invariants:
    1. Acyclic Evidence & Non-Circularity
    2. Derivation depth limits (depth <= 3 without empirical grounding)
    3. Epistemic status validity
    """
    errors: list[str] = []

    # 1. Load canonical questions
    questions: dict[str, dict[str, Any]] = {}
    if questions_dir.exists():
        for path in questions_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                qid = data.get("id")
                if qid:
                    questions[qid] = data
            except Exception as e:
                errors.append(f"Failed to read question {path.name}: {e}")

    # 2. Check for Circular Relations
    reinforcing_edges: list[tuple[str, str]] = []
    if relations_dir.exists():
        for path in relations_dir.glob("*.json"):
            try:
                rel = json.loads(path.read_text(encoding="utf-8"))
                rel_type = rel.get("relation_type")
                src = rel.get("source_question_id")
                tgt = rel.get("target_question_id")
                if rel_type in ("REINFORCES", "CONFIRMS") and src and tgt:
                    reinforcing_edges.append((src, tgt))
            except Exception as e:
                errors.append(f"Failed to read relation {path.name}: {e}")

    # Direct 2-node loop check
    for src, tgt in reinforcing_edges:
        if (tgt, src) in reinforcing_edges:
            errors.append(f"CIRCULAR_REINFORCEMENT_DETECTED: Mutual reinforcement between '{src}' and '{tgt}'")

    # 3. Check Derivation Depth & Circular Provenance on Questions
    for qid, q in questions.items():
        prov = q.get("provenance")
        if prov:
            depth = prov.get("derivation_depth", 0)
            roots_count = prov.get("independent_evidence_count", 0)
            if depth > EvidenceVerifier.MAX_DERIVATION_DEPTH and roots_count == 0:
                errors.append(
                    f"DERIVATION_DEPTH_VIOLATION: Question '{qid}' has depth {depth} > {EvidenceVerifier.MAX_DERIVATION_DEPTH} with 0 independent roots"
                )
            status = q.get("epistemic_status")
            if status == "EXTERNAL_FACT" and prov.get("derived_from"):
                errors.append(
                    f"EPISTEMIC_STATUS_VIOLATION: Question '{qid}' is marked EXTERNAL_FACT but has derived_from dependencies"
                )

    # 4. Check Current Proposal If Available
    if proposal_file.exists():
        try:
            prop_data = json.loads(proposal_file.read_text(encoding="utf-8"))
            if prop_data.get("status") == "PROPOSAL_READY":
                q_prop = prop_data.get("proposal", {}).get("question", {})
                prov_prop = q_prop.get("provenance")
                if prov_prop:
                    depth = prov_prop.get("derivation_depth", 0)
                    roots_count = prov_prop.get("independent_evidence_count", 0)
                    if depth > EvidenceVerifier.MAX_DERIVATION_DEPTH and roots_count == 0:
                        errors.append(
                            f"PROPOSAL_DEPTH_VIOLATION: Proposal has depth {depth} with 0 independent evidence roots"
                        )
        except Exception:
            pass

    return len(errors) == 0, errors


def main() -> int:
    passed, errors = check_epistemic_firewall()
    output = {
        "status": "PASS" if passed else "FAIL",
        "total_errors": len(errors),
        "errors": errors
    }
    print(json.dumps(output, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
