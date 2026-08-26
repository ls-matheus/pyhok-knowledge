from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = ROOT / "scheduler/status.json"
POLICY_FILE = ROOT / "evolution/evolution-policy.json"

DEFAULT_STATUS = {
    "status": "READY",
    "current_cycle_id": None,
    "last_run": None,
    "last_success": None,
    "last_failure": None,
    "last_error": None,
    "last_stop_reason": None,
    "processed_proposals": [],
    "last_opportunity_id": None,
    "last_proposal_id": None,
    "last_question_id": None,
    "last_branch": None,
    "last_pr_url": None,
    "consecutive_rejections": 0,
    "stats": {
        "total_runs": 0,
        "successful_runs": 0,
        "failed_runs": 0,
        "skipped_runs": 0
    }
}


def _get_now_iso(tz_name: str = "America/Sao_Paulo") -> str:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).isoformat()


def load_status() -> dict[str, Any]:
    if not STATUS_FILE.exists():
        return dict(DEFAULT_STATUS)
    try:
        data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        # Merge with default keys if missing
        merged = dict(DEFAULT_STATUS)
        merged.update(data)
        if "stats" not in merged or not isinstance(merged["stats"], dict):
            merged["stats"] = dict(DEFAULT_STATUS["stats"])
        return merged
    except Exception:
        return dict(DEFAULT_STATUS)


def save_status(data: dict[str, Any]) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def start_cycle(cycle_id: str | None = None) -> dict[str, Any]:
    current = load_status()
    now_str = _get_now_iso()
    if not cycle_id:
        cycle_id = f"cycle_{datetime.now(ZoneInfo('UTC')).strftime('%Y%m%d_%H%M%S')}"

    current["status"] = "WINDOW_OPEN"
    current["current_cycle_id"] = cycle_id
    current["last_run"] = now_str
    current["last_error"] = None
    current["last_stop_reason"] = None
    current["stats"]["total_runs"] += 1
    save_status(current)
    return current


def update_phase(phase: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    current = load_status()
    current["status"] = phase
    if metadata:
        for k, v in metadata.items():
            current[k] = v
    save_status(current)
    return current


def record_success(
    cycle_id: str | None = None,
    opportunity_id: str | None = None,
    proposal_id: str | None = None,
    question_id: str | None = None,
    branch: str | None = None,
    pr_url: str | None = None,
    stop_reason: str | None = None,
) -> dict[str, Any]:
    current = load_status()
    now_str = _get_now_iso()
    current["status"] = "READY"
    current["current_cycle_id"] = None
    current["last_success"] = now_str
    current["last_stop_reason"] = stop_reason or "cycle_completed_successfully"
    current["consecutive_rejections"] = 0
    current["stats"]["successful_runs"] += 1

    if proposal_id:
        if "processed_proposals" not in current or not isinstance(current["processed_proposals"], list):
            current["processed_proposals"] = []
        if proposal_id not in current["processed_proposals"]:
            current["processed_proposals"].append(proposal_id)
        current["last_proposal_id"] = proposal_id

    if opportunity_id:
        current["last_opportunity_id"] = opportunity_id
    if question_id:
        current["last_question_id"] = question_id
    if branch:
        current["last_branch"] = branch
    if pr_url:
        current["last_pr_url"] = pr_url

    save_status(current)
    return current


def record_failure(error: str, stop_reason: str = "error") -> dict[str, Any]:
    current = load_status()
    now_str = _get_now_iso()
    current["status"] = "FAILED"
    current["current_cycle_id"] = None
    current["last_failure"] = now_str
    current["last_error"] = str(error)
    current["last_stop_reason"] = stop_reason
    current["consecutive_rejections"] += 1
    current["stats"]["failed_runs"] += 1
    save_status(current)
    return current


def record_skip(reason: str) -> dict[str, Any]:
    current = load_status()
    current["status"] = "SKIPPED"
    current["current_cycle_id"] = None
    current["last_stop_reason"] = reason
    current["stats"]["skipped_runs"] += 1
    save_status(current)
    return current
