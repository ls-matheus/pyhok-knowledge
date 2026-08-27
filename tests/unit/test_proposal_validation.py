import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_ai_proposal_shape():
    path = ROOT / "tests/proposals/example_ai_proposal.json"

    with path.open("r", encoding="utf-8") as f:
        proposal = json.load(f)

    assert proposal["generator"]["type"] == "llm"
    assert proposal["changes"]["questions"]
