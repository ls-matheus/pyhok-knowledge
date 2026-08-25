import json
import os
import sys
from pathlib import Path

from google import genai
from google.genai import types


ROOT = Path(__file__).resolve().parents[1]

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")

CONTEXT_FILE = ROOT / "generator/input/agent_context.json"
AUDIT_FILE = ROOT / "generator/output/audit.json"
PROMPT_FILE = ROOT / "prompts/02_proposal_generator.system.txt"
OUTPUT_FILE = ROOT / "generator/output/proposal.json"


def build_context_if_needed():
    if CONTEXT_FILE.exists():
        return

    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "generator/build_agent_context.py")
        ],
        cwd=ROOT,
        capture_output=True,
        text=True
    )

    print(result.stdout)

    if result.returncode != 0:
        print(result.stderr)
        raise SystemExit(
            "Failed to build agent context."
        )


if not API_KEY:
    raise SystemExit(
        "GEMINI_API_KEY is missing."
    )

build_context_if_needed()

context = json.loads(
    CONTEXT_FILE.read_text(
        encoding="utf-8"
    )
)

audit = json.loads(
    AUDIT_FILE.read_text(
        encoding="utf-8"
    )
)

system_prompt = PROMPT_FILE.read_text(
    encoding="utf-8"
)

if audit.get("status") == "NO_USEFUL_CHANGE":
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        '{\n  "status": "NO_PROPOSAL"\n}\n',
        encoding="utf-8"
    )

    print("NO_PROPOSAL")
    raise SystemExit(0)

opportunities = audit.get(
    "opportunities",
    []
)

if not opportunities:
    OUTPUT_FILE.write_text(
        '{\n  "status": "NO_PROPOSAL"\n}\n',
        encoding="utf-8"
    )

    print("NO_PROPOSAL")
    raise SystemExit(0)

selected = max(
    opportunities,
    key=lambda item: (
        item.get(
            "estimated_coverage_gain",
            0.0
        ),
        item.get(
            "estimated_novelty",
            0.0
        ),
        item.get(
            "priority",
            0.0
        )
    )
)

response_schema = {
    "type": "object",
    "required": [
        "status"
    ],
    "properties": {
        "status": {
            "type": "string",
            "enum": [
                "PROPOSAL_READY",
                "NO_PROPOSAL"
            ]
        },
        "proposal": {
            "type": "object"
        }
    }
}

prompt = f"""
Generate exactly ONE PyHok Knowledge proposal based on this
selected opportunity:

{json.dumps(
    selected,
    ensure_ascii=False,
    indent=2
)}

Current repository:

{json.dumps(
    context,
    ensure_ascii=False,
    indent=2
)}

Use only known:
- signals
- questions
- relations
- evaluation methods
- mission rules

Do not invent identifiers.

Do not create a diagnostic claim.

If the opportunity cannot be safely expressed using the current
repository contracts, return:

{{
  "status": "NO_PROPOSAL"
}}

Return JSON only.
"""

client = genai.Client(
    api_key=API_KEY
)

response = client.models.generate_content(
    model=MODEL,
    contents=prompt,
    config=types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=response_schema,
        temperature=0.0
    )
)

try:
    result = json.loads(
        response.text
    )
except json.JSONDecodeError as exc:
    print(response.text)
    raise SystemExit(
        f"Gemini returned invalid JSON: {exc}"
    )

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_FILE.write_text(
    json.dumps(
        result,
        ensure_ascii=False,
        indent=2
    ) + "\n",
    encoding="utf-8"
)

print("=== PROPOSAL RESULT ===")
print(
    json.dumps(
        result,
        ensure_ascii=False,
        indent=2
    )
)
