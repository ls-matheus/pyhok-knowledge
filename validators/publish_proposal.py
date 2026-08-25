import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

proposal = json.loads(
    (ROOT / "generator/output/proposal.json")
    .read_text(encoding="utf-8")
)

if proposal["status"] == "NO_PROPOSAL":
    print("Nothing to publish.")
    sys.exit(0)

question = proposal["proposal"]["question"]

target = (
    ROOT
    / "data/questions"
    / f"{question['id']}.json"
)

if target.exists():
    print(
        f"ERROR: question already exists: {target}"
    )
    sys.exit(1)

target.write_text(
    json.dumps(
        question,
        ensure_ascii=False,
        indent=2
    ) + "\n",
    encoding="utf-8"
)

print("Published:", target)
