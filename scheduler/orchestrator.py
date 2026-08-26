from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
POLICY_FILE = ROOT / "evolution/evolution-policy.json"
PROPOSAL_OUTPUT_FILE = ROOT / "generator/output/proposal.json"
AUDIT_OUTPUT_FILE = ROOT / "generator/output/audit_result.json"

from scheduler.window_guard import is_window_open
from scheduler.state import (
    load_status,
    save_status,
    start_cycle,
    update_phase,
    record_success,
    record_failure,
    record_skip,
)
from scheduler.quality_gate import run_quality_gates


def log(phase: str, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{phase}] {message}")


def run_subcommand(cmd: list[str], cwd: Path = ROOT) -> tuple[int, str, str]:
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


class EvolutionOrchestrator:
    def __init__(
        self,
        policy_path: Path = POLICY_FILE,
        dry_run: bool = False,
        skip_git: bool = False,
        force_window: bool = False,
        runner_fn: Callable[[list[str]], tuple[int, str, str]] = run_subcommand,
    ):
        self.policy_path = policy_path
        self.dry_run = dry_run
        self.skip_git = skip_git
        self.force_window = force_window
        self.runner = runner_fn
        self.policy = self._load_policy()

    def _load_policy(self) -> dict[str, Any]:
        if not self.policy_path.exists():
            return {}
        return json.loads(self.policy_path.read_text(encoding="utf-8"))

    def execute_cycle(self) -> dict[str, Any]:
        log("INIT", "Starting autonomous evolution cycle...")

        # 1. Check Window Guard
        open_window, reason, meta = is_window_open(
            self.policy,
            is_manual_override=self.force_window or (os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch") or (os.getenv("MANUAL_OVERRIDE") == "1")
        )
        if not open_window:
            log("WINDOW_GUARD", f"Evolution window is CLOSED ({reason}). Skipping cycle.")
            record_skip(reason=f"window_closed: {reason}")
            return {"status": "SKIPPED", "reason": reason}

        # 2. Check Policy Limits (Rate Limits & Consecutive Rejections)
        status_data = load_status()
        max_rejections = self.policy.get("limits", {}).get("max_consecutive_rejections", 2)
        if status_data.get("consecutive_rejections", 0) >= max_rejections and not self.force_window:
            log("POLICY", f"Max consecutive rejections reached ({max_rejections}). Stopping cycle.")
            record_skip(reason="consecutive_rejections_limit_reached")
            return {"status": "SKIPPED", "reason": "consecutive_rejections_limit_reached"}

        # 3. Start Cycle State
        cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_cycle(cycle_id)
        log("STATE", f"Cycle {cycle_id} initiated. Status: WINDOW_OPEN")

        try:
            # 4. Build Context
            log("CONTEXT", "Building repository knowledge context...")
            update_phase("BUILDING_CONTEXT")
            code, out, err = self.runner([sys.executable, str(ROOT / "generator/build_context.py")])
            if code != 0:
                raise RuntimeError(f"build_context failed: {err or out}")

            # 5. Audit Knowledge Graph
            log("AUDIT", "Auditing knowledge graph for evolution opportunities...")
            update_phase("AUDITING")
            code, out, err = self.runner([sys.executable, str(ROOT / "generator/run_audit.py")])
            if code != 0:
                raise RuntimeError(f"run_audit failed: {err or out}")

            # 6. Generate Proposal
            log("PROPOSAL", "Generating evolution proposal...")
            update_phase("GENERATING_PROPOSAL")
            code, out, err = self.runner([sys.executable, str(ROOT / "generator/run_proposal.py")])
            if code != 0:
                raise RuntimeError(f"run_proposal failed: {err or out}")

            # 7. Check Proposal Result
            if not PROPOSAL_OUTPUT_FILE.exists():
                raise RuntimeError("proposal.json not produced by generator")

            proposal_data = json.loads(PROPOSAL_OUTPUT_FILE.read_text(encoding="utf-8"))
            proposal_status = proposal_data.get("status")

            if proposal_status == "NO_PROPOSAL":
                log("PROPOSAL", "No useful evolution opportunity found. Gracefully terminating cycle.")
                record_success(cycle_id=cycle_id, stop_reason="no_useful_change")
                return {"status": "NO_PROPOSAL", "cycle_id": cycle_id}

            if proposal_status != "PROPOSAL_READY":
                raise RuntimeError(f"Unexpected proposal status: {proposal_status}")

            prop = proposal_data.get("proposal", {})
            proposal_id = prop.get("proposal_id", "prop_unknown")
            opportunity_id = prop.get("opportunity_id")
            confidence = prop.get("confidence", 0.0)

            # Check Minimum Confidence Threshold from Policy
            min_confidence = self.policy.get("limits", {}).get("minimum_confidence_in_proposal", 0.8)
            if confidence < min_confidence:
                log("POLICY", f"Proposal confidence ({confidence}) below minimum required ({min_confidence}). Rejecting.")
                record_failure(error=f"confidence {confidence} < {min_confidence}", stop_reason="confidence_below_threshold")
                return {"status": "FAILED", "reason": "confidence_below_threshold"}

            log("PROPOSAL", f"Proposal {proposal_id} ready (confidence: {confidence})")
            update_phase("PROPOSAL_READY", {"last_proposal_id": proposal_id, "last_opportunity_id": opportunity_id})

            # 8. Validate Proposal
            log("VALIDATION", "Validating proposal against schema and epistemic policy...")
            update_phase("VALIDATING_PROPOSAL")
            code, out, err = self.runner([sys.executable, str(ROOT / "validators/validate_proposal.py")])
            if code != 0:
                raise RuntimeError(f"validate_proposal rejected proposal: {err or out}")

            # 9. Publish Proposal into Working Tree
            log("PUBLISH", "Publishing proposal into canonical dataset...")
            update_phase("PUBLISHING")
            code, out, err = self.runner([sys.executable, str(ROOT / "validators/publish_proposal.py")])
            if code != 0:
                raise RuntimeError(f"publish_proposal failed: {err or out}")

            # 10. Run Full Quality Gates
            log("QUALITY_GATE", "Running comprehensive quality gates...")
            update_phase("QUALITY_GATES")
            all_gates_pass, gate_results = run_quality_gates(verbose=True)
            if not all_gates_pass:
                failed_gates = [g["gate"] for g in gate_results if not g["passed"]]
                raise RuntimeError(f"Quality gates failed: {', '.join(failed_gates)}")

            # 11. Git Branch, Commit, Push & PR Lifecycle
            branch_name = f"agent/evolution-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            pr_url = None

            if not self.skip_git:
                log("BRANCH", f"Creating evolution branch {branch_name}...")
                self.runner(["git", "checkout", "-b", branch_name])
                self.runner(["git", "add", "-A"])

                code, diff_out, _ = self.runner(["git", "diff", "--cached", "--quiet"])
                if code == 0:
                    log("BRANCH", "No changes produced by proposal. Exiting cleanly.")
                    self.runner(["git", "checkout", "main"])
                    self.runner(["git", "branch", "-D", branch_name])
                    record_success(cycle_id=cycle_id, stop_reason="no_knowledge_changes")
                    return {"status": "NO_CHANGES", "cycle_id": cycle_id}

                log("COMMIT", "Committing proposed knowledge...")
                self.runner(["git", "commit", "-m", f"agent: propose knowledge evolution {proposal_id}"])

                log("PUSH", f"Pushing branch {branch_name}...")
                self.runner(["git", "push", "origin", branch_name])

                log("PR", "Creating pull request...")
                pr_body = (
                    f"Automated knowledge proposal generated by the PyHok Knowledge Agent.\n\n"
                    f"- Proposal: `{proposal_id}`\n"
                    f"- Opportunity: `{opportunity_id}`\n"
                    f"- Confidence: `{confidence}`\n\n"
                    f"Quality Gates: All 5 canonical gates PASSED."
                )
                code, pr_out, pr_err = self.runner([
                    "gh", "pr", "create",
                    "--base", "main",
                    "--head", branch_name,
                    "--title", f"Agent Evolution: {proposal_id}",
                    "--body", pr_body
                ])
                if code == 0:
                    pr_url = pr_out.strip()
                    log("PR", f"Pull request created: {pr_url}")

            # 12. Record Successful Cycle Completion
            question_id = prop.get("question", {}).get("id") or prop.get("question", {}).get("question_id")
            record_success(
                cycle_id=cycle_id,
                opportunity_id=opportunity_id,
                proposal_id=proposal_id,
                question_id=question_id,
                branch=branch_name if not self.skip_git else None,
                pr_url=pr_url,
                stop_reason="cycle_completed_successfully"
            )
            log("SUCCESS", f"Evolution cycle {cycle_id} completed successfully!")
            return {
                "status": "SUCCESS",
                "cycle_id": cycle_id,
                "proposal_id": proposal_id,
                "opportunity_id": opportunity_id,
                "branch": branch_name,
                "pr_url": pr_url
            }

        except Exception as exc:
            log("ERROR", f"Evolution cycle {cycle_id} failed: {exc}")
            record_failure(error=str(exc), stop_reason="pipeline_error")
            return {"status": "FAILED", "cycle_id": cycle_id, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="PyHok Knowledge Autonomous Evolution Orchestrator")
    parser.add_argument("--force", action="store_true", help="Force execution regardless of window guard")
    parser.add_argument("--skip-git", action="store_true", help="Skip git branch/commit/push/PR operations")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    args = parser.parse_args()

    orchestrator = EvolutionOrchestrator(
        force_window=args.force,
        skip_git=args.skip_git,
        dry_run=args.dry_run
    )
    result = orchestrator.execute_cycle()
    status = result.get("status")

    if status in ("SUCCESS", "NO_PROPOSAL", "NO_CHANGES", "SKIPPED"):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
