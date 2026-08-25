#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path

from google import genai

ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = ROOT / "generator" / "input" / "test_observation.json"
OUTPUT_FILE = ROOT / "generator" / "output" / "generated_question.json"

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

if not API_KEY:
    print("ERROR: GEMINI_API_KEY is not configured.")
    sys.exit(1)

observation = json.loads(INPUT_FILE.read_text(encoding="utf-8"))

client = genai.Client(api_key=API_KEY)

prompt = f"""
You are the PyHok Epistemic Agent.

Your task is to propose ONE observational hypothesis for the Sinapse engine.

STRICT RULES:
- Do not diagnose any medical condition.
- Do not infer syndromes, disorders, disabilities, or clinical labels.
- Describe only an observable behavioral hypothesis.
- Use only signals explicitly listed in available_signals.
- Return ONLY valid JSON.
- Do not add markdown.
- Do not add explanatory text.

Required JSON structure:

{{
  "id": "q_...",
  "hypothesis": "...",
  "required_signals": ["sig_..."],
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
{json.dumps(observation, ensure_ascii=False, indent=2)}

Available signals:
{json.dumps(observation["available_signals"], ensure_ascii=False, indent=2)}
"""

response = client.models.generate_content(
    model=MODEL,
    contents=prompt,
)

text = response.text.strip()

try:
    result = json.loads(text)
except json.JSONDecodeError as exc:
    print("ERROR: Gemini did not return valid JSON.")
    print(text)
    raise SystemExit(1) from exc

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE.write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print(f"Generated question: {result.get('id', 'unknown')}")
print(f"Output: {OUTPUT_FILE}")
