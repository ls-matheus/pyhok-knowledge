#!/usr/bin/env python3

import json
import os
import re
import sys
from pathlib import Path

from google import genai
from google.genai import types
from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = ROOT / "generator/input/test_observation.json"
METHODS_FILE = ROOT / "generator/methods/methods.json"
AI_SCHEMA_FILE = ROOT / "generator/ai_question_response.schema.json"
CANONICAL_SCHEMA_FILE = ROOT / "schemas/v2/question.schema.json"
OUTPUT_DIR = ROOT / "generator/output/questions"

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

if not API_KEY:
    print("ERROR: GEMINI_API_KEY is not configured.")
    sys.exit(1)


def fail(message: str) -> None:
    print(f"GENERATOR REJECTED: {message}")
    raise SystemExit(1)


observation = json.loads(
    INPUT_FILE.read_text(encoding="utf-8")
)

methods = json.loads(
    METHODS_FILE.read_text(encoding="utf-8")
)

ai_schema = json.loads(
    AI_SCHEMA_FILE.read_text(encoding="utf-8")
)

canonical_schema = json.loads(
    CANONICAL_SCHEMA_FILE.read_text(encoding="utf-8")
)

enabled_methods = [
    method
    for method in methods["methods"]
    if method.get("enabled") is True
]

allowed_method_ids = {
    method["method_id"]
    for method in enabled_methods
}

available_signals = set(
    observation["available_signals"]
)

prompt = f"""
You are the PyHok Epistemic Agent.

Generate exactly ONE observational hypothesis.

The hypothesis is NOT a diagnosis.
Do not mention:
- syndromes
- disorders
- disabilities
- medical conditions
- clinical diagnoses

Use ONLY these available signal identifiers:

{json.dumps(sorted(available_signals), ensure_ascii=False)}

Use ONLY these evaluation methods:

{json.dumps(enabled_methods, ensure_ascii=False, indent=2)}

You MUST include evaluation_model.

If the hypothesis describes deviation from a personal or local baseline,
the evaluation method MUST be method_baseline_deviation.

Do not invent:
- signal IDs
- method IDs
- method versions
- schema fields
- capabilities
- sensor sources

Use only the fields defined by the output schema.

Observation:

{json.dumps(observation, ensure_ascii=False, indent=2)}
"""

client = genai.Client(api_key=API_KEY)

response = client.models.generate_content(
    model=MODEL,
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ai_schema,
        temperature=0.0,
    ),
)

text = response.text.strip()

try:
    result = json.loads(text)
except json.JSONDecodeError as exc:
    fail(f"Gemini did not return valid JSON: {exc}")


# ------------------------------------------------------------
# Local AI-output validation
# ------------------------------------------------------------

ai_validator = Draft7Validator(ai_schema)
ai_errors = sorted(
    ai_validator.iter_errors(result),
    key=lambda error: list(error.path),
)

if ai_errors:
    fail(
        "structured output failed local AI schema validation: "
        + "; ".join(error.message for error in ai_errors)
    )


canonical_validator = Draft7Validator(canonical_schema)

canonical_errors = sorted(
    canonical_validator.iter_errors(result),
    key=lambda error: list(error.path),
)

if canonical_errors:
    fail(
        "question failed canonical schema validation: "
        + "; ".join(error.message for error in canonical_errors)
    )


question_id = result["id"]

if not re.fullmatch(
    r"q_[a-z0-9_]+",
    question_id,
):
    fail(f"invalid question id: {question_id}")


# ------------------------------------------------------------
# Signal allowlist
# ------------------------------------------------------------

for signal_id in result["required_signals"]:
    if signal_id not in available_signals:
        fail(
            f"unknown signal referenced: {signal_id}"
        )

for rule in result["evaluation_trigger"]["rules"]:
    signal_id = rule["signal_id"]

    if signal_id not in available_signals:
        fail(
            f"unknown trigger signal: {signal_id}"
        )


# ------------------------------------------------------------
# Method allowlist
# ------------------------------------------------------------

evaluation_model = result["evaluation_model"]
method_id = evaluation_model["method_id"]

if method_id not in allowed_method_ids:
    fail(
        f"unknown or disabled evaluation method: {method_id}"
    )


# ------------------------------------------------------------
# Baseline semantic guard
# ------------------------------------------------------------

hypothesis = result["hypothesis"].lower()

baseline_terms = (
    "baseline",
    "linha de base",
    "linha-base",
    "personal baseline",
    "local baseline",
)

mentions_baseline = any(
    term in hypothesis
    for term in baseline_terms
)

if (
    mentions_baseline
    and method_id != "method_baseline_deviation"
):
    fail(
        "hypothesis references baseline but selected method "
        "is not method_baseline_deviation"
    )


# ------------------------------------------------------------
# Duplicate protection
# ------------------------------------------------------------

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

output_file = OUTPUT_DIR / f"{question_id}.json"

if output_file.exists():
    fail(
        f"question already exists: {output_file}"
    )


output_file.write_text(
    json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

print(
    f"QUESTION APPROVED LOCALLY: {question_id}"
)
print(
    f"METHOD: {method_id}"
)
print(
    f"OUTPUT: {output_file}"
)
