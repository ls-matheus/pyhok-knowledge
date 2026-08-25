import json
import os
import sys
from pathlib import Path

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parents[1]

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

CONTEXT_FILE = ROOT / "generator/output/current_context.json"
PROMPT_FILE = ROOT / "prompts/01_graph_auditor.system.txt"
OUTPUT_FILE = ROOT / "generator/output/audit.json"

if not API_KEY:
    print("ERROR: GEMINI_API_KEY is missing.")
    sys.exit(1)

context = json.loads(
    CONTEXT_FILE.read_text(encoding="utf-8")
)

system_prompt = PROMPT_FILE.read_text(
    encoding="utf-8"
)

audit_schema = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "opportunities"],
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
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
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
                        "items": {"type": "string"}
                    },
                    "available_signals": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "available_methods": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "estimated_novelty": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1
                    },
                    "estimated_coverage_gain": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1
                    },
                    "priority": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1
                    }
                }
            }
        }
    }
}

prompt = f"""
Audit the current PyHok Knowledge Graph.

Do not create a question.
Do not create a relation.
Do not modify anything.

Find at most three defensible opportunities for evolution.

Repository:

{json.dumps(context, ensure_ascii=False, indent=2)}

Return JSON only.
If no useful change exists, return:

{{
  "status": "NO_USEFUL_CHANGE",
  "opportunities": []
}}
"""

client = genai.Client(api_key=API_KEY)

response = client.models.generate_content(
    model=MODEL,
    contents=prompt,
    config=types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=audit_schema,
        temperature=0.0
    )
)

try:
    result = json.loads(response.text)
except json.JSONDecodeError as exc:
    print("ERROR: invalid Gemini JSON:", exc)
    sys.exit(1)

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE.write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)

print(json.dumps(result, ensure_ascii=False, indent=2))
