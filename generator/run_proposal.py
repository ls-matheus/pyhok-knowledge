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
AUDIT_FILE = ROOT / "generator/output/audit.json"
PROMPT_FILE = ROOT / "prompts/02_proposal_generator.system.txt"
OUTPUT_FILE = ROOT / "generator/output/proposal.json"

if not API_KEY:
    print("ERROR: GEMINI_API_KEY is missing.")
    sys.exit(1)

context = json.loads(
    CONTEXT_FILE.read_text(encoding="utf-8")
)

audit = json.loads(
    AUDIT_FILE.read_text(encoding="utf-8")
)

system_prompt = PROMPT_FILE.read_text(
    encoding="utf-8"
)

if audit["status"] == "NO_USEFUL_CHANGE":
    OUTPUT_FILE.write_text(
        '{\n  "status": "NO_PROPOSAL"\n}\n',
        encoding="utf-8"
    )
    print("NO_PROPOSAL")
    sys.exit(0)

opportunities = audit.get("opportunities", [])

if not opportunities:
    OUTPUT_FILE.write_text(
        '{\n  "status": "NO_PROPOSAL"\n}\n',
        encoding="utf-8"
    )
    print("NO_PROPOSAL")
    sys.exit(0)

selected = max(
    opportunities,
    key=lambda item: (
        item["estimated_coverage_gain"],
        item["estimated_novelty"],
        item["priority"]
    )
)

proposal_schema = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status"],
    "properties": {
        "status": {
            "type": "string",
            "enum": [
                "PROPOSAL_READY",
                "NO_PROPOSAL"
            ]
        },
        "proposal": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "proposal_id",
                "proposal_type",
                "mission_version",
                "target_question_id",
                "question",
                "reasoning_metadata"
            ],
            "properties": {
                "proposal_id": {
                    "type": "string"
                },
                "proposal_type": {
                    "type": "string",
                    "enum": [
                        "QUESTION_CREATE",
                        "QUESTION_UPDATE",
                        "RELATION_CREATE"
                    ]
                },
                "mission_version": {
                    "type": "string"
                },
                "target_question_id": {
                    "type": "string"
                },
                "question": {
                    "type": "object"
                },
                "reasoning_metadata": {
                    "type": "object"
                }
            }
        }
    }
}

prompt = f"""
Generate ONE and ONLY ONE knowledge proposal.

Selected opportunity:

{json.dumps(selected, ensure_ascii=False, indent=2)}

Current repository:

{json.dumps(context, ensure_ascii=False, indent=2)}

Rules:

- use only existing signal IDs;
- use only supported evaluation methods;
- never invent identifiers;
- never create diagnostic claims;
- do not duplicate an existing question;
- do not create unsupported runtime behavior;
- if the opportunity cannot be expressed safely and coherently,
  return NO_PROPOSAL.

Return JSON only.
"""

client = genai.Client(api_key=API_KEY)

response = client.models.generate_content(
    model=MODEL,
    contents=prompt,
    config=types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=proposal_schema,
        temperature=0.0
    )
)

try:
    result = json.loads(response.text)
except json.JSONDecodeError as exc:
    print("ERROR: invalid proposal JSON:", exc)
    sys.exit(1)

OUTPUT_FILE.write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)

print(json.dumps(result, ensure_ascii=False, indent=2))
