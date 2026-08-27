from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CRITICAL_DIRS = [
    "data/signals",
    "data/questions",
    "data/relations",
    "schemas/v2",
    "validators",
    "generator",
    "evolution",
    "scheduler",
]

CRITICAL_FILES = [
    "evolution/evolution-policy.json",
    "mission/mission.json",
    "generator/methods/methods.json",
    "schemas/v2/question.schema.json",
    "schemas/v2/signal.schema.json",
    "schemas/v2/relation.schema.json",
    "validators/validate_proposal.py",
    "validators/publish_proposal.py",
    "validators/validate_dataset.py",
]

REQUIRED_MODULES = [
    "jsonschema",
    "pytest",
]

SAFE_EPHEMERAL_PATTERNS = [
    r"^scheduler/status\.json$",
    r"^generator/output/.*",
    r"^generator/input/.*",
    r"^evolution/ledger\.jsonl$",
    r"^evolution/post_evaluations\.jsonl$",
    r".*__pycache__.*",
    r".*\.pytest_cache.*",
    r".*\.pyc$",
]


def check_python_runtime() -> tuple[bool, str]:
    if sys.version_info < (3, 10):
        return False, f"Python >= 3.10 required, got {sys.version}"
    return True, "python_version_ok"


def check_dependencies() -> tuple[bool, list[str]]:
    missing = []
    for mod in REQUIRED_MODULES:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(mod)
    return len(missing) == 0, missing


def check_critical_paths(root: Path = ROOT) -> tuple[bool, list[str]]:
    missing = []
    for d in CRITICAL_DIRS:
        if not (root / d).is_dir():
            missing.append(f"Directory missing: {d}")
    for f in CRITICAL_FILES:
        if not (root / f).is_file():
            missing.append(f"File missing: {f}")
    return len(missing) == 0, missing


def check_git_workspace_hygiene(
    root: Path = ROOT,
    expected_branch: str = "main",
    enforce_branch: bool = True
) -> tuple[bool, str, list[str]]:
    """
    Ensures workspace is on expected branch and contains no unexpected dirty modifications.
    """
    # 1. Branch check
    res_branch = subprocess.run(["git", "branch", "--show-current"], cwd=str(root), capture_output=True, text=True)
    current_branch = res_branch.stdout.strip()

    if enforce_branch and expected_branch and current_branch != expected_branch:
        permit = os.getenv("PERMIT_ANY_BRANCH", "0") == "1"
        if not permit:
            return False, f"invalid_branch: expected '{expected_branch}', got '{current_branch}'", []

    # 2. Dirty files check
    res_status = subprocess.run(["git", "status", "--porcelain"], cwd=str(root), capture_output=True, text=True)
    if res_status.returncode != 0:
        return False, "git_status_failed", [res_status.stderr.strip()]

    lines = [line.strip() for line in res_status.stdout.splitlines() if line.strip()]
    unknown_dirty = []

    for line in lines:
        # line format: "XY path" or "XY orig -> path"
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            continue
        rel_path = parts[1].strip()
        if "->" in rel_path:
            rel_path = rel_path.split("->")[1].strip()

        # Check if matched by safe ephemeral patterns
        is_safe = any(re.match(pattern, rel_path) for pattern in SAFE_EPHEMERAL_PATTERNS)
        if not is_safe:
            unknown_dirty.append(rel_path)

    if unknown_dirty:
        return False, f"dirty_workspace_unknown_files: {', '.join(unknown_dirty)}", unknown_dirty

    return True, "workspace_clean", []


def run_preflight(root: Path = ROOT, enforce_branch: bool = True) -> tuple[bool, str, dict[str, Any]]:
    """
    Executes full preflight validation before any cycle is allowed to begin.
    """
    details: dict[str, Any] = {}

    py_ok, py_msg = check_python_runtime()
    details["python_runtime"] = {"ok": py_ok, "message": py_msg}
    if not py_ok:
        return False, f"PREFLIGHT_BLOCKED: {py_msg}", details

    deps_ok, missing_deps = check_dependencies()
    details["dependencies"] = {"ok": deps_ok, "missing": missing_deps}
    if not deps_ok:
        return False, f"PREFLIGHT_BLOCKED: missing dependencies: {', '.join(missing_deps)}", details

    paths_ok, missing_paths = check_critical_paths(root)
    details["critical_paths"] = {"ok": paths_ok, "missing": missing_paths}
    if not paths_ok:
        return False, f"PREFLIGHT_BLOCKED: missing critical paths: {', '.join(missing_paths)}", details

    git_ok, git_msg, dirty_files = check_git_workspace_hygiene(root=root, enforce_branch=enforce_branch)
    details["git_hygiene"] = {"ok": git_ok, "message": git_msg, "dirty_files": dirty_files}
    if not git_ok:
        return False, f"PREFLIGHT_BLOCKED: {git_msg}", details

    return True, "PREFLIGHT_PASSED", details


def main() -> int:
    passed, reason, details = run_preflight()
    if passed:
        print("[PREFLIGHT] All system and workspace checks PASSED.")
        return 0
    else:
        print(f"[PREFLIGHT] FAILED: {reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
