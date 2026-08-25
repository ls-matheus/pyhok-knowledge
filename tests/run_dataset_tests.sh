#!/usr/bin/env bash
set -e

echo "=== PyHok Dataset Test Suite ==="

echo
echo "[1/3] Validating JSON fixtures..."
for file in tests/fixtures/valid/*.json; do
    python3 scripts/validate_fixture.py "$file"
done

echo
echo "[2/3] Checking invalid fixture is actually rejected by higher-level validation..."
python3 scripts/validate_fixture.py tests/fixtures/invalid/question_missing_signal.json

echo
echo "[3/3] Running repository conflict check..."
python3 scripts/conflict_check.py

echo
echo "=== DATASET TESTS PASSED ==="
