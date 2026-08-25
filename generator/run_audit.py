import json
import os
import sys
from pathlib import Path

from google import genai
from google.genai import types


ROOT = Path(__file__).resolve().parents[1]

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

CONTEXT_FILE = ROOT / "generator/input/agent_context.json"
PROMPT_FILE = ROOT / "prompts/01_graph_auditor.system.txt"
OUTPUT_FILE = ROOT / "generator/output/audit.json"


def build_context_if_needed():
    if CONTEXT_FILE.exists():
        return

    print("Building agent context...")

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

if not CONTEXT_FILE.exists():
    raise SystemExit(
        f"Context not found: {CONTEXT_FILE}"
    )

context = json.loads(
    CONTEXT_FILE.read_text(
        encoding="utf-8"
    )
)

system_prompt = PROMPT_FILE.read_text(
    encoding="utf-8"
)

response_schema = {
    "type": "object",
    "required": [
        "status",
        "opportunities"
    ],
    "properties": {
        "status": {
            "type": "string",
            "enum": [
                "ANALYSIS_COMPLETE",
                "NO_USEFUL_CHANGE"
            ]
        },
        "opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "opportunity_id",
                    "type",
                    "domain",
                    "description",
                    "existing_questions",
                    "available_signals",
                    "available_methods",
                    "estimated_novelty",
                    "estimated_coverage_gain",
                    "priority"
                ],
                "properties": {
                    "opportunity_id": {
                        "type": "string"
                    },
                    "type": {
                        "type": "string"
                    },
                    "domain": {
                        "type": "string"
                    },
                    "description": {
                        "type": "string"
                    },
                    "existing_questions": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "available_signals": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "available_methods": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "estimated_novelty": {
                        "type": "number"
                    },
                    "estimated_coverage_gain": {
                        "type": "number"
                    },
                    "priority": {
                        "type": "number"
                    }
                }
            }
        }
    }
}

prompt = f"""
Audit the current PyHok Knowledge Graph.

Do not create knowledge.
Do not modify the repository.
Do not invent missing entities.

Use only the supplied repository context.

Repository context:

{json.dumps(
    context,
    ensure_ascii=False,
    indent=2
)}

Identify at most three useful opportunities.

If no useful evolution exists, return:

{{
  "status": "NO_USEFUL_CHANGE",
  "opportunities": []
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

print("=== AUDIT RESULT ===")
print(
    json.dumps(
        result,
        ensure_ascii=False,
        indent=2
    )
)
