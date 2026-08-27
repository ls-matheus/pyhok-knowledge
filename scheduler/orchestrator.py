from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
POLICY_FILE = ROOT / "evolution/evolution-policy.json"
PROPOSAL_OUTPUT_FILE = ROOT / "generator/output/proposal.json"
AUDIT_OUTPUT_FILE = ROOT / "generator/output/audit_result.json"

from scheduler.window_guard import is_window_open
from scheduler.preflight import run_preflight
from scheduler.state import (
    load_status,
    save_status,
    start_cycle,
    update_phase,
    record_success,
    record_failure,
    record_skip,
    record_blocked,
    is_circuit_open,
    is_auto_merge_enabled,
)
from scheduler.quality_gate import run_quality_gates
from evolution.ledger import (
    load_knowledge_state,
    hash_knowledge_state,
    hash_proposal,
    append_ledger_event,
)
from evolution.shadow import record_shadow_candidate
from evolution.manifest import create_cycle_manifest
from evolution.post_evaluator import evaluate_proposal_impact, attach_post_evaluation
from evolution.epistemic.review_chamber import run_epistemic_review, REJECTED_CLAIMS_FILE


def log(phase: str, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{phase}] {message}")


def run_subcommand(cmd: list[str], cwd: Path = ROOT) -> tuple[int, str, str]:
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


LEDGER_FILE = ROOT / "evolution/ledger.jsonl"
MANIFESTS_DIR = ROOT / "evolution/manifests"
EVALUATIONS_FILE = ROOT / "evolution/post_evaluations.jsonl"


class EvolutionOrchestrator:
    def __init__(
        self,
        policy_path: Path = POLICY_FILE,
        ledger_path: Path | None = None,
        manifests_dir: Path | None = None,
        evaluations_path: Path | None = None,
        quarantine_file: Path | None = None,
        dry_run: bool = False,
        skip_git: bool = False,
        force_window: bool = False,
        skip_preflight: bool = False,
        runner_fn: Callable[[list[str]], tuple[int, str, str]] = run_subcommand,
    ):
        self.policy_path = policy_path
        self.ledger_path = ledger_path or LEDGER_FILE
        self.manifests_dir = manifests_dir or MANIFESTS_DIR
        self.evaluations_path = evaluations_path or EVALUATIONS_FILE
        self.quarantine_file = quarantine_file or REJECTED_CLAIMS_FILE
        self.dry_run = dry_run
        self.skip_git = skip_git
        self.force_window = force_window
        self.skip_preflight = skip_preflight
        self.runner = runner_fn
        self.policy = self._load_policy()

    def _load_policy(self) -> dict[str, Any]:
        if not self.policy_path.exists():
            return {}
        return json.loads(self.policy_path.read_text(encoding="utf-8"))

    def execute_cycle(self) -> dict[str, Any]:
        log("INIT", "Starting autonomous evolution cycle...")
        timestamp_start = datetime.now(ZoneInfo("UTC")).isoformat()

        # 1. Circuit Breaker Check
        circuit_open, trip_reason = is_circuit_open()
        if circuit_open and not self.force_window:
            log("CIRCUIT_BREAKER", f"Circuit breaker is OPEN ({trip_reason}). Aborting cycle.")
            record_blocked(reason=f"circuit_breaker_open: {trip_reason}")
            return {"status": "CIRCUIT_OPEN", "reason": trip_reason}

        # 2. Preflight Environment & Workspace Validation
        if not self.skip_preflight:
            log("PREFLIGHT", "Executing system and workspace hygiene preflight checks...")
            preflight_ok, preflight_reason, preflight_details = run_preflight(
                root=ROOT,
                enforce_branch=not self.skip_git
            )
            if not preflight_ok:
                log("PREFLIGHT", f"Preflight blocked: {preflight_reason}")
                record_blocked(reason=preflight_reason)
                return {"status": "BLOCKED", "reason": preflight_reason, "details": preflight_details}

        # 3. Check Window Guard
        open_window, reason, meta = is_window_open(
            self.policy,
            is_manual_override=self.force_window or (os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch") or (os.getenv("MANUAL_OVERRIDE") == "1")
        )
        if not open_window:
            log("WINDOW_GUARD", f"Evolution window is CLOSED ({reason}). Skipping cycle.")
            record_skip(reason=f"window_closed: {reason}")
            return {"status": "SKIPPED", "reason": reason}

        # 4. Check Policy Limits (Rate Limits & Consecutive Failures)
        status_data = load_status()
        max_failures = self.policy.get("limits", {}).get("max_consecutive_rejections", 3)
        if status_data.get("consecutive_failures", 0) >= max_failures and not self.force_window:
            log("POLICY", f"Max consecutive failures reached ({max_failures}). Stopping cycle.")
            record_skip(reason="consecutive_failures_limit_reached")
            return {"status": "SKIPPED", "reason": "consecutive_failures_limit_reached"}

        # 5. Start Cycle State
        cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_cycle(cycle_id)
        log("STATE", f"Cycle {cycle_id} initiated. Status: PREFLIGHT -> RUNNING")

        try:
            # Capture initial real state snapshot and git SHA
            initial_state = load_knowledge_state()
            initial_state_hash = hash_knowledge_state(initial_state)
            dataset_counts_before = {
                "questions": len(initial_state.get("questions", [])),
                "signals": len(initial_state.get("signals", [])),
                "relations": len(initial_state.get("relations", [])),
            }

            code_head, head_out, _ = self.runner(["git", "rev-parse", "HEAD"])
            main_before_sha = head_out.strip() if code_head == 0 else "unknown"

            # 6. Build Context
            log("CONTEXT", "Building repository knowledge context...")
            update_phase("BUILDING_CONTEXT")
            code, out, err = self.runner([sys.executable, str(ROOT / "generator/build_context.py")])
            if code != 0:
                raise RuntimeError(f"build_context failed: {err or out}")

            # 7. Audit Knowledge Graph
            log("AUDIT", "Auditing knowledge graph for evolution opportunities...")
            update_phase("AUDITING")
            code, out, err = self.runner([sys.executable, str(ROOT / "generator/run_audit.py")])
            if code != 0:
                raise RuntimeError(f"run_audit failed: {err or out}")

            # 8. Generate Proposal
            log("PROPOSAL", "Generating evolution proposal...")
            update_phase("GENERATING_PROPOSAL")
            code, out, err = self.runner([sys.executable, str(ROOT / "generator/run_proposal.py")])
            if code != 0:
                raise RuntimeError(f"run_proposal failed: {err or out}")

            # 9. Check Proposal Result
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

            # 9a. Sinapse Variable Binding (Instantiate open variables from context deterministically)
            from evolution.epistemic.synapse import bind_open_thesis
            prop = bind_open_thesis(prop, initial_state)

            # 9b. Multi-Agent Epistemic Review (Adversarial Critic + Evidence Verifier -> Blind Judge)
            log("EPISTEMIC", "Convening Epistemic Review Chamber (Critic + Verifier -> Blind Judge)...")
            update_phase("EPISTEMIC_REVIEW")
            epistemic_result = run_epistemic_review(
                proposal=prop,
                knowledge_state=initial_state,
                cycle_id=cycle_id,
                quarantine_file=self.quarantine_file
            )
            decision = epistemic_result.get("decision")
            if decision in ("QUARANTINE", "REJECT"):
                reason = epistemic_result.get("judge_ruling", {}).get("quarantine_reason", f"epistemic_{decision.lower()}")
                log("EPISTEMIC", f"Proposal placed in {decision} by Blind Judge: {reason}")
                record_success(cycle_id=cycle_id, stop_reason=f"epistemic_{decision.lower()}")
                return {"status": decision, "cycle_id": cycle_id, "reason": reason}

            # Update proposal file with approved provenance before validation & publishing
            proposal_data["proposal"] = epistemic_result.get("reviewed_proposal", prop)
            PROPOSAL_OUTPUT_FILE.write_text(json.dumps(proposal_data, indent=2), encoding="utf-8")

            # 10. Validate Proposal
            log("VALIDATION", "Validating proposal against schema and epistemic policy...")
            update_phase("VALIDATING_PROPOSAL")
            code, out, err = self.runner([sys.executable, str(ROOT / "validators/validate_proposal.py")])
            if code != 0:
                raise RuntimeError(f"validate_proposal rejected proposal: {err or out}")

            # 11. Record in Shadow Evolution Ledger
            log("SHADOW", "Recording candidate in Evolution Ledger (Shadow Mode)...")
            record_shadow_candidate(
                cycle_id=cycle_id,
                proposal_data=proposal_data,
                initial_state_hash=initial_state_hash,
                ledger_path=self.ledger_path
            )

            # 12. Workspace Branch Isolation & Publishing
            branch_name = f"agent/evolution-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            pr_url = None
            proposal_commit_sha = None

            if not self.skip_git:
                log("BRANCH", f"Creating isolated evolution branch {branch_name}...")
                self.runner(["git", "checkout", "-b", branch_name])

            # 13. Publish Proposal into Working Tree (Isolated on Feature Branch)
            log("PUBLISH", "Publishing proposal into canonical dataset...")
            update_phase("PUBLISHING")
            code, out, err = self.runner([sys.executable, str(ROOT / "validators/publish_proposal.py")])
            if code != 0:
                raise RuntimeError(f"publish_proposal failed: {err or out}")

            # 14. Run Full Quality Gates
            log("QUALITY_GATE", "Running comprehensive quality gates...")
            update_phase("QUALITY_GATES")
            all_gates_pass, gate_results = run_quality_gates(verbose=True, runner_fn=self.runner)
            if not all_gates_pass:
                failed_gates = [g["gate"] for g in gate_results if not g["passed"]]
                raise RuntimeError(f"Quality gates failed: {', '.join(failed_gates)}")

            # 15. Capture Resulting State Dynamically & Compute Empirical Post-Evaluation
            resulting_state = load_knowledge_state()
            resulting_state_hash = hash_knowledge_state(resulting_state)
            dataset_counts_after = {
                "questions": len(resulting_state.get("questions", [])),
                "signals": len(resulting_state.get("signals", [])),
                "relations": len(resulting_state.get("relations", [])),
            }

            post_eval = evaluate_proposal_impact(
                state_before=initial_state,
                proposal=prop,
                state_after=resulting_state
            )
            attach_post_evaluation(cycle_id=cycle_id, evaluation_result=post_eval, evaluations_path=self.evaluations_path)

            # 16. Git Commit, Push & PR Lifecycle
            if not self.skip_git:
                self.runner(["git", "add", "-A"])
                code, diff_out, _ = self.runner(["git", "diff", "--cached", "--quiet"])
                if code == 0:
                    log("BRANCH", "No changes produced by proposal. Exiting cleanly.")
                    self.runner(["git", "checkout", "main"])
                    self.runner(["git", "branch", "-D", branch_name])
                    record_success(cycle_id=cycle_id, stop_reason="no_knowledge_changes")
                    return {"status": "NO_CHANGES", "cycle_id": cycle_id}

                log("COMMIT", "Committing proposed knowledge...")
                code, c_out, _ = self.runner(["git", "commit", "-m", f"agent: propose knowledge evolution {proposal_id}"])
                code_sha, sha_out, _ = self.runner(["git", "rev-parse", "HEAD"])
                if code_sha == 0:
                    proposal_commit_sha = sha_out.strip()

                log("PUSH", f"Pushing branch {branch_name}...")
                self.runner(["git", "push", "origin", branch_name])

                log("PR", "Creating pull request...")
                pr_body = (
                    f"Automated knowledge proposal generated by the PyHok Knowledge Agent.\n\n"
                    f"- Proposal: `{proposal_id}`\n"
                    f"- Opportunity: `{opportunity_id}`\n"
                    f"- Confidence: `{confidence}`\n"
                    f"- Initial State Hash: `{initial_state_hash}`\n\n"
                    f"Quality Gates: All canonical gates PASSED in Shadow Mode."
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

                if is_auto_merge_enabled():
                    log("AUTO_MERGE", "Auto-merge enabled. Requesting PR squash merge...")
                    self.runner(["gh", "pr", "merge", branch_name, "--squash", "--delete-branch"])
                else:
                    log("AUTO_MERGE", "Auto-merge disabled (Shadow Mode). PR left for observation.")
                    # Return to main and verify No-Silent-Mutation Guard on main
                    self.runner(["git", "checkout", "main"])
                    state_on_main = hash_knowledge_state()
                    if state_on_main != initial_state_hash:
                        raise RuntimeError("SHADOW_MUTATION_DETECTED: Dataset on main was mutated during shadow observation")

            # 17. Create Cycle Manifest
            question_id = prop.get("question", {}).get("id") or prop.get("question", {}).get("question_id")

            predicted_metrics = {
                "novelty_score": float(prop.get("novelty_score", 0.85)),
                "coverage_gain": float(prop.get("coverage_gain", 0.20)),
                "confidence": float(confidence),
            }

            create_cycle_manifest(
                cycle_id=cycle_id,
                main_before_sha=main_before_sha,
                state_before_hash=initial_state_hash,
                state_after_hash=resulting_state_hash,
                proposal_hash=hash_proposal(prop),
                dataset_counts_before=dataset_counts_before,
                dataset_counts_after=dataset_counts_after,
                predicted_metrics=predicted_metrics,
                observed_metrics=post_eval.get("observed", {}),
                gate_verdict={"valid": True, "safe": True, "classification": "PREDICTED_IMPROVEMENT"},
                action_taken="SHADOW_RECORDED",
                timestamp_start=timestamp_start,
                manifests_dir=self.manifests_dir
            )

            record_success(
                cycle_id=cycle_id,
                opportunity_id=opportunity_id,
                proposal_id=proposal_id,
                question_id=question_id,
                branch=branch_name if not self.skip_git else None,
                pr_url=pr_url,
                stop_reason="cycle_completed_successfully",
                audit_trail={
                    "main_before_sha": main_before_sha,
                    "state_before_hash": initial_state_hash,
                    "state_after_hash": resulting_state_hash,
                    "proposal_commit_sha": proposal_commit_sha
                }
            )

            # 19. Terminal No-Silent-Mutation Guard (Final Absolute Step)
            if not self.skip_git:
                code_stat, stat_out, _ = self.runner(["git", "status", "--porcelain", "data/"])
                code_head, head_out, _ = self.runner(["git", "rev-parse", "HEAD"])
                final_main_sha = head_out.strip() if code_head == 0 else ""
                state_on_main = hash_knowledge_state()

                if state_on_main != initial_state_hash or stat_out.strip() != "" or (main_before_sha and final_main_sha != main_before_sha):
                    raise RuntimeError(
                        f"TERMINAL_MUTATION_DETECTED: main state violation (hash_match={state_on_main == initial_state_hash}, clean_data={stat_out.strip() == ''}, sha_match={final_main_sha == main_before_sha})"
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
    parser.add_argument("--force", action="store_true", help="Force execution regardless of window guard or circuit breaker")
    parser.add_argument("--skip-git", action="store_true", help="Skip git branch/commit/push/PR operations")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip preflight environment checks")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    args = parser.parse_args()

    orchestrator = EvolutionOrchestrator(
        force_window=args.force,
        skip_git=args.skip_git,
        skip_preflight=args.skip_preflight,
        dry_run=args.dry_run
    )
    result = orchestrator.execute_cycle()
    status = result.get("status")

    if status in ("SUCCESS", "NO_PROPOSAL", "NO_CHANGES", "SKIPPED"):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
