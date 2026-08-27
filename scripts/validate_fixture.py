#!/usr/bin/env python3

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])

try:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Root must be an object")
    print(f"VALID JSON: {path}")
except Exception as exc:
    print(f"INVALID JSON: {path}")
    print(exc)
    sys.exit(1)
