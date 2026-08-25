#!/usr/bin/env bash
set -e

echo "=== PyHok Knowledge Test Suite ==="

python -m pytest -q

echo
echo "=== Cross-reference validation ==="

python validators/validate_dataset.py

echo
echo "=== AI proposal validation ==="

python tools/validate_proposal.py

echo
echo "=================================="
echo "ALL TESTS PASSED"
echo "=================================="
