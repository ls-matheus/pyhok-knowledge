#!/usr/bin/env python3

import json
import os
import re
import sys
from pathlib import Path

from google import genai

ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = ROOT / "generator" / "input" / "test_observation.json"
METHODS_FILE = ROOT / "generator" / "methods" / "methods.json"
OUTPUT_DIR = ROOT / "generator" / "output" / "questions"

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

if not API_KEY:
    print("ERROR: GEMINI_API_KEY is not configured.")
    sys.exit(1)

observation = json.loads(
    INPUT_FILE.read_text(encoding="utf-8")
)

methods = json.loads(
    METHODS_FILE.read_text(encoding="utf-8")
)

available_methods = methods["methods"]

client = genai.Client(api_key=API_KEY)

prompt = f"""
You are the PyHok Epistemic Agent.

Your task is to propose ONE observational hypothesis for the
PyHok Sinapse engine.

STRICT RULES:

1. Do not diagnose medical conditions.
2. Do not infer syndromes, disorders, disabilities, or clinical labels.
3. Describe only an observable behavioral hypothesis.
4. Use only signals explicitly listed in available_signals.
5. Select exactly ONE evaluation method from available_methods.
6. Do not invent a method_id.
7. The evaluation method must match the semantic meaning of the hypothesis.
8. Return ONLY valid JSON.
9. Do not add markdown.
10. Do not add explanatory text.
11. The hypothesis may refer to a baseline only if the selected
    evaluation method supports baseline comparison.

Required JSON structure:

{{
  "id": "q_...",
  "hypothesis": "...",

  "required_signals": [
    "sig_..."
  ],

  "evaluation_trigger": {{
    "logical_operator": "AND",
    "rules": [
      {{
        "signal_id": "sig_...",
        "operator": ">",
        "threshold": 0.0,
        "window_ms": 1000
      }}
    ]
  }},

  "evaluation_model": {{
    "method_id": "method_...",
    "version": "1.0.0",
    "parameters": {{}}
  }},

  "evidence_model": {{
    "base_strength": 0.0,
    "decay_rate_per_sec": 0.0
  }},

  "cortex_weights": {{
    "focus": 0.0,
    "stress": 0.0,
    "autonomy": 0.0,
    "fatigue": 0.0
  }}
}}

Observation:

{json.dumps(
    observation,
    ensure_ascii=False,
    indent=2
)}

Available signals:

{json.dumps(
    observation["available_signals"],
    ensure_ascii=False,
    indent=2
)}

Available evaluation methods:

{json.dumps(
    available_methods,
    ensure_ascii=False,
    indent=2
)}
"""

response = client.models.generate_content(
    model=MODEL,
    contents=prompt
)

text = response.text.strip()

try:
    result = json.loads(text)
except json.JSONDecodeError as exc:
    print("ERROR: Gemini did not return valid JSON.")
    print(text)
    raise SystemExit(1) from exc

question_id = result.get("id", "")

if not re.fullmatch(r"q_[a-z0-9_]+", question_id):
    print(f"ERROR: invalid question id: {question_id}")
    sys.exit(1)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

output_file = OUTPUT_DIR / f"{question_id}.json"

if output_file.exists():
    print(f"ERROR: question already exists: {output_file}")
    sys.exit(1)

output_file.write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)

print(f"Generated question: {question_id}")
print(f"Output: {output_file}")
