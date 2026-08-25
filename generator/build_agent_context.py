from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path):
    if not path.exists():
        return {}

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def read_many(directory: Path):
    result = []

    if not directory.exists():
        return result

    for path in sorted(
        directory.glob("*.json")
    ):
        result.append(
            json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        )

    return result


def main():
    context = {
        "mission": read_json(
            ROOT / "mission/mission.json"
        ),
        "evolution_policy": read_json(
            ROOT / "evolution/evolution-policy.json"
        ),
        "signals": read_many(
            ROOT / "data/signals"
        ),
        "questions": read_many(
            ROOT / "data/questions"
        ),
        "relations": read_many(
            ROOT / "data/relations"
        ),
        "methods": read_json(
            ROOT / "generator/methods/methods.json"
        )
    }

    output = ROOT / "generator/input/agent_context.json"

    output.write_text(
        json.dumps(
            context,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    print(
        f"Agent context written to {output}"
    )


if __name__ == "__main__":
    main()
