from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BASELINE_FILE = ROOT / "evolution/baseline.json"
DATA_DIR = ROOT / "data"
MISSION_FILE = ROOT / "mission/mission.json"

from evolution.ledger import hash_knowledge_state, compute_sha256, canonical_json_dumps


def capture_baseline(root: Path = ROOT) -> dict[str, Any]:
    """
    Captures an immutable, frozen baseline snapshot (N=0) of the knowledge graph and git state.
    """
    # 1. Git HEAD SHA
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, check=True)
        main_sha = res.stdout.strip()
    except Exception:
        main_sha = "unknown"

    # 2. Dataset State
    state_hash = hash_knowledge_state(data_dir=root / "data")

    # Load questions, signals, relations, methods
    questions = []
    questions_dir = root / "data/questions"
    if questions_dir.exists():
        for f in sorted(questions_dir.glob("*.json")):
            try:
                questions.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass

    signals = []
    signals_dir = root / "data/signals"
    if signals_dir.exists():
        for f in sorted(signals_dir.glob("*.json")):
            try:
                signals.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass

    relations = []
    relations_dir = root / "data/relations"
    if relations_dir.exists():
        for f in sorted(relations_dir.glob("*.json")):
            try:
                relations.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass

    methods = []
    methods_file = root / "generator/methods/methods.json"
    if methods_file.exists():
        try:
            methods_data = json.loads(methods_file.read_text(encoding="utf-8"))
            methods = methods_data.get("methods", [])
        except Exception:
            pass

    # 3. Domain Analysis & Known Gaps
    all_domains = []
    mission_file = root / "mission/mission.json"
    if mission_file.exists():
        try:
            m_data = json.loads(mission_file.read_text(encoding="utf-8"))
            for d in m_data.get("domains", []):
                if isinstance(d, str):
                    all_domains.append(d)
                elif isinstance(d, dict) and d.get("name"):
                    all_domains.append(d["name"])
        except Exception:
            pass

    # Find domains covered by questions (extracted from question context/trigger/signals)
    covered_domains = set()
    for q in questions:
        # Check explicit domain
        dom = q.get("domain")
        if isinstance(dom, str) and dom in all_domains:
            covered_domains.add(dom)
            continue
        # Check hypothesis or id for domain references
        qid = q.get("id", "")
        for m_dom in all_domains:
            if m_dom in qid:
                covered_domains.add(m_dom)

    total_domains = max(1, len(all_domains))
    coverage = len(covered_domains) / total_domains
    known_gaps = [d for d in all_domains if d not in covered_domains]

    density = len(relations) / max(1, len(questions))

    baseline_data = {
        "baseline_id": "baseline_n0",
        "created_at": datetime.now(ZoneInfo("UTC")).isoformat(),
        "main_sha": main_sha,
        "state_hash": state_hash,
        "counts": {
            "questions": len(questions),
            "signals": len(signals),
            "relations": len(relations),
            "methods": len(methods),
            "total_domains": len(all_domains),
            "covered_domains": len(covered_domains),
            "uncovered_domains": len(known_gaps)
        },
        "coverage": round(coverage, 4),
        "graph_density": round(density, 4),
        "redundancy": 0.0,
        "known_gaps": sorted(known_gaps),
        "covered_domain_list": sorted(list(covered_domains))
    }
    # Compute cryptographic digest for the baseline content
    baseline_data["baseline_hash"] = compute_sha256(baseline_data)
    return baseline_data


def save_baseline(baseline_data: dict[str, Any], baseline_path: Path = BASELINE_FILE) -> None:
    """
    Saves the baseline snapshot to disk.
    """
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(baseline_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_baseline(baseline_path: Path = BASELINE_FILE) -> dict[str, Any]:
    """
    Loads baseline snapshot from disk, capturing a new one if not yet present.
    """
    if not baseline_path.exists():
        data = capture_baseline()
        save_baseline(data, baseline_path)
        return data
    return json.loads(baseline_path.read_text(encoding="utf-8"))


def verify_baseline_integrity(baseline_path: Path = BASELINE_FILE) -> tuple[bool, str]:
    """
    Verifies that the frozen baseline snapshot has not been tampered with or modified.
    """
    if not baseline_path.exists():
        return False, "BASELINE_MISSING: baseline.json not found"

    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"BASELINE_CORRUPTED: invalid json - {exc}"

    if "baseline_hash" not in data:
        return False, "BASELINE_UNHASHED: missing baseline_hash field"

    stored_hash = data["baseline_hash"]
    data_to_verify = {k: v for k, v in data.items() if k != "baseline_hash"}
    expected_hash = compute_sha256(data_to_verify)

    if stored_hash != expected_hash:
        return False, f"BASELINE_TAMPERED: stored {stored_hash} != computed {expected_hash}"

    return True, "BASELINE_VALID"
