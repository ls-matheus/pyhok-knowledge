from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

POLICY_FILE = ROOT / "evolution/evolution-policy.json"


def main() -> int:
    # Execução manual pelo GitHub Actions pode testar fora da janela.
    if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        print("EVOLUTION_WINDOW=OPEN")
        print("REASON=manual_workflow_dispatch")
        return 0

    policy = json.loads(
        POLICY_FILE.read_text(encoding="utf-8")
    )

    scheduler = policy["scheduler"]

    if not scheduler["enabled"]:
        print("EVOLUTION_WINDOW=CLOSED")
        print("REASON=scheduler_disabled")
        return 1

    timezone = ZoneInfo(
        scheduler["timezone"]
    )

    now = datetime.now(timezone)

    start_hour, start_minute = map(
        int,
        scheduler["start"].split(":")
    )

    end_hour, end_minute = map(
        int,
        scheduler["end"].split(":")
    )

    current_minutes = now.hour * 60 + now.minute
    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute

    if start_minutes <= end_minutes:
        open_window = (
            start_minutes <= current_minutes < end_minutes
        )
    else:
        open_window = (
            current_minutes >= start_minutes
            or current_minutes < end_minutes
        )

    print(
        f"CURRENT_TIME={now.isoformat()}"
    )

    print(
        f"WINDOW={scheduler['start']}-{scheduler['end']}"
    )

    if not open_window:
        print("EVOLUTION_WINDOW=CLOSED")
        return 1

    print("EVOLUTION_WINDOW=OPEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())