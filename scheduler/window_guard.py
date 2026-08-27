from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
POLICY_FILE = ROOT / "evolution/evolution-policy.json"


def is_window_open(
    policy: dict[str, Any],
    current_dt: datetime | None = None,
    is_manual_override: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    """
    Checks if evolution window is open based on policy configuration.
    Returns (is_open: bool, reason: str, metadata: dict).
    """
    if is_manual_override:
        return True, "manual_workflow_dispatch", {"override": True}

    scheduler = policy.get("scheduler", {})
    if not scheduler.get("enabled", False):
        return False, "scheduler_disabled", {"enabled": False}

    tz_name = scheduler.get("timezone", "America/Sao_Paulo")
    try:
        timezone = ZoneInfo(tz_name)
    except Exception:
        timezone = ZoneInfo("UTC")

    now = current_dt.astimezone(timezone) if current_dt else datetime.now(timezone)

    start_str = scheduler.get("start", "08:00")
    end_str = scheduler.get("end", "20:00")

    try:
        start_hour, start_minute = map(int, start_str.split(":"))
        end_hour, end_minute = map(int, end_str.split(":"))
    except ValueError:
        return False, "invalid_window_format", {"start": start_str, "end": end_str}

    current_minutes = now.hour * 60 + now.minute
    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute

    if start_minutes <= end_minutes:
        open_window = start_minutes <= current_minutes < end_minutes
    else:
        # Overnight window support (e.g. 22:00 to 06:00)
        open_window = current_minutes >= start_minutes or current_minutes < end_minutes

    meta = {
        "current_time": now.isoformat(),
        "timezone": tz_name,
        "window": f"{start_str}-{end_str}",
        "current_minutes": current_minutes,
        "start_minutes": start_minutes,
        "end_minutes": end_minutes,
    }

    if open_window:
        return True, "within_scheduled_window", meta
    return False, "outside_scheduled_window", meta


def main() -> int:
    is_manual = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch" or os.getenv("MANUAL_OVERRIDE") == "1"

    if not POLICY_FILE.exists():
        print("EVOLUTION_WINDOW=CLOSED")
        print("REASON=policy_file_not_found")
        return 1

    policy = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    open_window, reason, meta = is_window_open(policy, is_manual_override=is_manual)

    if "current_time" in meta:
        print(f"CURRENT_TIME={meta['current_time']}")
    if "window" in meta:
        print(f"WINDOW={meta['window']}")

    print(f"REASON={reason}")

    if not open_window:
        print("EVOLUTION_WINDOW=CLOSED")
        return 1

    print("EVOLUTION_WINDOW=OPEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
