#!/usr/bin/env python3

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    proposal_path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else ROOT / "tests/proposals/example_ai_proposal.json"
    )

    proposal = load_json(proposal_path)

    required = [
        "proposal_id",
        "generator",
        "reason",
        "changes"
    ]

    missing = [
        field
        for field in required
        if field not in proposal
    ]

    if missing:
        print(f"FAIL: proposal missing fields: {missing}")
        return 1

    if proposal["generator"]["type"] != "llm":
        print("FAIL: proposal generator must be llm")
        return 1

    changes = proposal["changes"]

    if not isinstance(changes["signals"], list):
        print("FAIL: signals must be a list")
        return 1

    if not isinstance(changes["questions"], list):
        print("FAIL: questions must be a list")
        return 1

    if not isinstance(changes["relations"], list):
        print("FAIL: relations must be a list")
        return 1

    print(f"Proposal: {proposal['proposal_id']}")
    print("Generator:", proposal["generator"]["model"])
    print("Proposal format: PASS")

    return 0


if __name__ == "__main__":
    sys.exit(main())
