from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]


def run_cmd(cmd: list[str], cwd: Path = ROOT) -> tuple[int, str, str]:
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def run_quality_gates(
    verbose: bool = True,
    runner_fn: Callable[[list[str]], tuple[int, str, str]] = run_cmd,
) -> tuple[bool, list[dict[str, Any]]]:
    """
    Executes the full canonical quality gate sequence:
    1. pytest unit & contract tests
    2. validate_dataset.py (schema + cross-reference)
    3. conflict_check.py (domain conflicts)
    4. tools/validate_proposal.py (proposal schema & justifications)
    5. git diff --check (formatting & whitespace integrity)

    Returns (all_passed: bool, gate_results: list[dict]).
    """
    gates = [
        ("pytest", [
            sys.executable, "-m", "pytest", "-v",
            "-k", "not test_quality_gate"
        ]),
        ("validate_dataset", [sys.executable, str(ROOT / "validators/validate_dataset.py")]),
        ("conflict_check", [sys.executable, str(ROOT / "scripts/conflict_check.py")]),
        ("validate_proposal_tool", [sys.executable, str(ROOT / "tools/validate_proposal.py")]),
        ("measurement_gate", [sys.executable, str(ROOT / "evolution/measurement_gate.py")]),
        ("epistemic_gate", [sys.executable, str(ROOT / "evolution/epistemic_gate.py")]),
        ("continuous_discovery_gate", [sys.executable, str(ROOT / "evolution/continuous_discovery_gate.py")]),
        ("git_diff_check", [
            "git", "diff", "--check", "--", ".",
            ":!generator/output",
            ":!evolution/*.jsonl",
            ":!scheduler/*.json",
            ":!data/theses",
        ]),
    ]

    results = []
    all_passed = True

    for name, cmd in gates:
        code, out, err = runner_fn(cmd)
        passed = (code == 0)
        if not passed:
            all_passed = False
        results.append({
            "gate": name,
            "command": " ".join(cmd),
            "exit_code": code,
            "passed": passed,
            "stdout": out.strip(),
            "stderr": err.strip()
        })
        if verbose:
            status_str = "PASS" if passed else f"FAIL (code {code})"
            print(f"[QUALITY_GATE] {name}: {status_str}")

    return all_passed, results


def main() -> int:
    all_passed, results = run_quality_gates(verbose=True)
    if all_passed:
        print("[QUALITY_GATE] All quality gates passed successfully.")
        return 0
    else:
        print("[QUALITY_GATE] Quality gate failure detected. Auto-merge aborted.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
