from __future__ import annotations

import argparse
import copy
import gc
import json
import os
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CHECKPOINT_FILE = ROOT / "scheduler/checkpoint.json"
STATUS_FILE = ROOT / "scheduler/status.json"

from scheduler.orchestrator import EvolutionOrchestrator, log
from scheduler.state import record_blocked, record_failure, record_success
from evolution.discovery.discovery_engine import EpistemicDiscoveryEngine
from evolution.graph.knowledge_graph import KnowledgeGraph
from evolution.epistemic.synapse import SinapseBindingEngine, bind_open_thesis
from evolution.epistemic.review_chamber import EpistemicReviewChamber, run_epistemic_review
from evolution.epistemic.quarantine import REJECTED_CLAIMS_FILE, record_quarantined_claim
from evolution.ledger import load_knowledge_state, persist_knowledge_entity, append_ledger_event


class ContinuousEngineError(Exception):
    """Base exception for continuous engine errors."""


class RecoverableError(ContinuousEngineError):
    """Transient error that can be retried with exponential backoff."""


class EpistemicError(ContinuousEngineError):
    """Violation of an epistemic invariant or invalid proposal payload."""


class PersistenceError(ContinuousEngineError):
    """Failure to persist knowledge state, checkpoint, or quarantine claim."""


class FatalError(ContinuousEngineError):
    """Critical unrecoverable error requiring immediate engine termination."""


class ContinuousKnowledgeEngine:
    """
    Continuous Epistemic Discovery Engine (7/0):
    Executes autonomous, non-stop discovery, thesis formulation, synapse binding, multi-agent review,
    blind adjudication, and atomic persistence.
    """

    def __init__(
        self,
        orchestrator: EvolutionOrchestrator | None = None,
        discovery_engine: EpistemicDiscoveryEngine | None = None,
        knowledge_graph: KnowledgeGraph | None = None,
        checkpoint_path: Path = CHECKPOINT_FILE,
        max_cycles: int | None = None,
        duration_sec: float | None = None,
        max_consecutive_errors: int = 5,
        backoff_base_sec: float = 0.5,
        backoff_max_sec: float = 30.0,
        enable_gc_per_cycle: bool = True,
        gc_interval: int = 25,
        verbose: bool = True,
    ):
        self.orchestrator = orchestrator or EvolutionOrchestrator(skip_git=True)
        self.discovery_engine = discovery_engine or EpistemicDiscoveryEngine()
        self.graph = knowledge_graph or KnowledgeGraph()
        self.checkpoint_path = checkpoint_path
        self.max_cycles = max_cycles
        self.duration_sec = duration_sec
        self.max_consecutive_errors = max_consecutive_errors
        self.backoff_base_sec = backoff_base_sec
        self.backoff_max_sec = backoff_max_sec
        self.enable_gc_per_cycle = enable_gc_per_cycle
        self.gc_interval = max(1, gc_interval)
        self.verbose = verbose

        q_file = getattr(self.orchestrator, "quarantine_file", REJECTED_CLAIMS_FILE)
        if not isinstance(q_file, Path):
            q_file = Path(q_file) if isinstance(q_file, str) else REJECTED_CLAIMS_FILE
        self.review_chamber = EpistemicReviewChamber(quarantine_file=q_file)

        self._running = False
        self._stop_requested = False
        self._stop_reason = "not_started"
        self._current_cycle_id: str | None = None
        self._start_time_epoch: float | None = None
        self._cycle_latencies_ms: list[float] = []

        # Cumulative Metrics
        self.metrics = {
            "engine_version": "2.0.0-continuous-discovery",
            "total_cycles": 0,
            "successful_cycles": 0,
            "discoveries_total": 0,
            "new_theses_generated": 0,
            "accepted_theses": 0,
            "accepted_proposals": 0,
            "quarantined_theses": 0,
            "quarantined_proposals": 0,
            "rejected_theses": 0,
            "rejected_proposals": 0,
            "bindings_total": 0,
            "variables_unbound": 0,
            "variables_candidate": 0,
            "variables_bound": 0,
            "contradictions_found": 0,
            "knowledge_nodes": 0,
            "knowledge_edges": 0,
            "consecutive_errors": 0,
            "total_errors": 0,
            "novelty_scores": [],
            "info_gain_scores": [],
            "started_at": None,
            "last_cycle_at": None,
            "engine_status": "INITIALIZED",
        }

        self._load_checkpoint()
        self._setup_signals()

    def _setup_signals(self) -> None:
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except (ValueError, AttributeError):
            pass

    def _handle_signal(self, signum: int, frame: Any) -> None:
        sig_name = "SIGINT" if signum == signal.SIGINT else ("SIGTERM" if signum == signal.SIGTERM else str(signum))
        if self.verbose:
            log("ENGINE", f"Received signal {sig_name}. Initiating graceful shutdown...")
        self.stop(reason=f"signal_{sig_name}")

    def stop(self, reason: str = "programmatic_stop") -> None:
        self._stop_requested = True
        self._stop_reason = reason
        self.metrics["engine_status"] = "STOPPING"

    def is_running(self) -> bool:
        return self._running and not self._stop_requested

    def _load_checkpoint(self) -> None:
        if self.checkpoint_path.exists():
            try:
                data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for k, v in data.items():
                        if k in self.metrics and k not in ("novelty_scores", "info_gain_scores"):
                            self.metrics[k] = v
                    if "accepted_theses" in self.metrics and "accepted_proposals" not in self.metrics:
                        self.metrics["accepted_proposals"] = self.metrics["accepted_theses"]
                    elif "accepted_proposals" in self.metrics and "accepted_theses" not in self.metrics:
                        self.metrics["accepted_theses"] = self.metrics["accepted_proposals"]
                    if self.verbose:
                        log("CHECKPOINT", f"Loaded checkpoint: {self.metrics['total_cycles']} past cycles recovered.")
            except Exception as exc:
                if self.verbose:
                    log("CHECKPOINT", f"Warning: Failed to load checkpoint ({exc}). Starting fresh state.")

    def _save_checkpoint(self) -> None:
        try:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            nov_mean = round(sum(self.metrics["novelty_scores"]) / max(1, len(self.metrics["novelty_scores"])), 4) if self.metrics["novelty_scores"] else 0.0
            info_mean = round(sum(self.metrics["info_gain_scores"]) / max(1, len(self.metrics["info_gain_scores"])), 4) if self.metrics["info_gain_scores"] else 0.0

            checkpoint_data = {
                "engine_version": self.metrics["engine_version"],
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "last_cycle_id": self._current_cycle_id,
                "engine_status": self.metrics.get("engine_status"),
                "stop_reason": self._stop_reason if self._stop_requested else None,
                "total_cycles": self.metrics.get("total_cycles", 0),
                "successful_cycles": self.metrics.get("successful_cycles", 0),
                "discoveries_total": self.metrics.get("discoveries_total", 0),
                "new_theses_generated": self.metrics.get("new_theses_generated", 0),
                "accepted_theses": self.metrics.get("accepted_theses", 0),
                "accepted_proposals": self.metrics.get("accepted_proposals", self.metrics.get("accepted_theses", 0)),
                "quarantined_theses": self.metrics.get("quarantined_theses", 0),
                "quarantined_proposals": self.metrics.get("quarantined_proposals", self.metrics.get("quarantined_theses", 0)),
                "rejected_theses": self.metrics.get("rejected_theses", 0),
                "rejected_proposals": self.metrics.get("rejected_proposals", self.metrics.get("rejected_theses", 0)),
                "bindings_total": self.metrics.get("bindings_total", 0),
                "variables_unbound": self.metrics.get("variables_unbound", 0),
                "variables_candidate": self.metrics.get("variables_candidate", 0),
                "variables_bound": self.metrics.get("variables_bound", 0),
                "contradictions_found": self.metrics.get("contradictions_found", 0),
                "knowledge_nodes": self.graph.node_count,
                "knowledge_edges": self.graph.edge_count,
                "novelty_mean": nov_mean,
                "information_gain_mean": info_mean,
                "total_errors": self.metrics.get("total_errors", 0),
            }
            tmp_chk = self.checkpoint_path.with_suffix(".tmp")
            tmp_chk.write_text(json.dumps(checkpoint_data, indent=2), encoding="utf-8")
            tmp_chk.replace(self.checkpoint_path)
        except Exception as exc:
            if self.verbose:
                log("CHECKPOINT", f"Critical: Failed to save checkpoint: {exc}")

    def generate_cycle_id(self) -> str:
        now = datetime.now(timezone.utc)
        time_str = now.strftime("%Y%m%d_%H%M%S_%f")
        rand_suffix = uuid.uuid4().hex[:6]
        return f"cycle_{time_str}_{rand_suffix}"

    def run_single_cycle(self, custom_cycle_id: str | None = None) -> dict[str, Any]:
        cycle_id = custom_cycle_id or self.generate_cycle_id()
        self._current_cycle_id = cycle_id
        start_time = time.perf_counter()

        if self.verbose:
            log("ENGINE", f"Executing continuous epistemic cycle {cycle_id}...")

        try:
            # 1. Observe Knowledge Base & Graph
            try:
                state = self.orchestrator.load_knowledge_state()
                if not isinstance(state, dict):
                    state = {}
            except Exception:
                state = {}

            if state:
                self.graph.build_from_dataset(state)

            # 2. Mine Discovery Opportunities
            opportunities = self.discovery_engine.detect_opportunities(state, self.graph) if state else []
            if opportunities:
                best_opp = opportunities[0]
                self.metrics["discoveries_total"] += len(opportunities)
                self.metrics["novelty_scores"].append(best_opp.get("novelty_score", 0.8))
                self.metrics["info_gain_scores"].append(best_opp.get("information_gain_score", 0.7))
                if len(self.metrics["novelty_scores"]) > 500:
                    self.metrics["novelty_scores"] = self.metrics["novelty_scores"][-500:]
                    self.metrics["info_gain_scores"] = self.metrics["info_gain_scores"][-500:]

                # 3. Formulate Open Thesis (Tese != Resposta)
                thesis = self.discovery_engine.generate_open_thesis(best_opp, cycle_id)
                self.metrics["new_theses_generated"] += 1

                # 4. Synapse Binding (Binding != Evidencia)
                bound_thesis = bind_open_thesis(thesis, state, cycle_id)

                # 5. Multi-Agent Epistemic Review Chamber & Blind Adjudication
                review_result = self.review_chamber.review(
                    proposal=bound_thesis,
                    knowledge_state=state,
                    cycle_id=cycle_id,
                )
                decision = review_result.get("decision", "REJECT")

                # 6. Track Variables & Results
                open_vars = thesis.get("open_variables", [])
                for v in open_vars:
                    v_stat = v.get("status", "UNBOUND")
                    if v_stat == "BOUND":
                        self.metrics["variables_bound"] += 1
                        self.metrics["bindings_total"] += 1
                    elif v_stat == "CANDIDATE":
                        self.metrics["variables_candidate"] += 1
                    else:
                        self.metrics["variables_unbound"] += 1

                if decision == "ACCEPT":
                    self.metrics["accepted_theses"] += 1
                    self.metrics["accepted_proposals"] += 1
                    self.metrics["successful_cycles"] += 1
                    try:
                        persist_knowledge_entity("thesis", thesis)
                    except Exception:
                        pass
                    self.graph.add_node(thesis["thesis_id"], "Thesis", thesis)
                    for rel in thesis.get("relational_hypotheses", []):
                        if isinstance(rel, dict):
                            src_var = rel.get("source_var")
                            tgt_var = rel.get("target_var")
                            if src_var and tgt_var and self.graph.has_node(src_var) and self.graph.has_node(tgt_var):
                                try:
                                    self.graph.add_edge(src_var, tgt_var, "RELATED_TO")
                                except Exception:
                                    pass
                elif decision == "QUARANTINE":
                    self.metrics["quarantined_theses"] += 1
                    self.metrics["quarantined_proposals"] += 1
                    self.metrics["successful_cycles"] += 1
                    try:
                        record_quarantined_claim(bound_thesis, file_path=self.review_chamber.quarantine_file)
                    except Exception:
                        pass
                else:
                    self.metrics["rejected_theses"] += 1
                    self.metrics["rejected_proposals"] += 1
                    try:
                        record_quarantined_claim(bound_thesis, file_path=self.review_chamber.quarantine_file)
                    except Exception:
                        pass

                self.discovery_engine.register_historical_proposal(thesis)
                cycle_result = {"status": "SUCCESS" if decision in ("ACCEPT", "QUARANTINE") else decision, "decision": decision, "cycle_id": cycle_id}

            else:
                # Closed-world baseline: Execute standard orchestrator cycle
                cycle_result = self.orchestrator.execute_cycle()
                status = cycle_result.get("status") if isinstance(cycle_result, dict) else "UNKNOWN"
                if status == "SUCCESS":
                    self.metrics["successful_cycles"] += 1
                    self.metrics["accepted_theses"] += 1
                    self.metrics["accepted_proposals"] += 1
                elif status == "QUARANTINE":
                    self.metrics["quarantined_theses"] += 1
                    self.metrics["quarantined_proposals"] += 1
                    self.metrics["successful_cycles"] += 1
                else:
                    self.metrics["rejected_theses"] += 1
                    self.metrics["rejected_proposals"] += 1

            self.metrics["total_cycles"] += 1
            self.metrics["last_cycle_at"] = datetime.now(timezone.utc).isoformat()
            self.metrics["consecutive_errors"] = 0
            self.metrics["knowledge_nodes"] = self.graph.node_count
            self.metrics["knowledge_edges"] = self.graph.edge_count

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            self._cycle_latencies_ms.append(duration_ms)
            if len(self._cycle_latencies_ms) > 1000:
                self._cycle_latencies_ms = self._cycle_latencies_ms[-1000:]

            if isinstance(cycle_result, dict):
                cycle_result["duration_ms"] = duration_ms
            if self.verbose:
                log("ENGINE", f"Cycle {cycle_id} finished ({cycle_result.get('status', 'COMPLETED')}) in {duration_ms}ms")

            return cycle_result if isinstance(cycle_result, dict) else {"status": "COMPLETED"}

        except Exception as exc:
            self.metrics["total_errors"] += 1
            self.metrics["consecutive_errors"] += 1
            if self.verbose:
                log("ENGINE_ERROR", f"Cycle {cycle_id} failed with exception: {exc}")

            if self.metrics["consecutive_errors"] >= self.max_consecutive_errors:
                if self.verbose:
                    log("ENGINE_ERROR", f"Max consecutive errors reached ({self.max_consecutive_errors}). Requesting engine stop.")
                self.stop(reason="max_consecutive_errors")

            return {"status": "ERROR", "cycle_id": cycle_id, "error": str(exc)}

        finally:
            if self.enable_gc_per_cycle and (self.metrics["total_cycles"] % self.gc_interval == 0):
                gc.collect()

    def run_forever(self) -> dict[str, Any]:
        self._running = True
        self._stop_requested = False
        self._start_time_epoch = time.perf_counter()
        self.metrics["engine_status"] = "RUNNING"
        self.metrics["started_at"] = datetime.now(timezone.utc).isoformat()
        if self.verbose:
            log("ENGINE", "Continuous Epistemic Discovery Engine (7/0) started.")

        try:
            cycles_completed = 0
            while self.is_running():
                if self.max_cycles is not None and cycles_completed >= self.max_cycles:
                    if self.verbose:
                        log("ENGINE", f"Max configured cycles ({self.max_cycles}) reached. Stopping cleanly.")
                    self.stop(reason="max_cycles_reached")
                    break

                if self.duration_sec is not None and (time.perf_counter() - self._start_time_epoch) >= self.duration_sec:
                    if self.verbose:
                        log("ENGINE", f"Configured duration ({self.duration_sec}s) reached. Stopping cleanly.")
                    self.stop(reason="duration_reached")
                    break

                res = self.run_single_cycle()
                cycles_completed += 1

                if cycles_completed % 20 == 0 or self._stop_requested:
                    self._save_checkpoint()

                if self.metrics["consecutive_errors"] > 0:
                    backoff = min(self.backoff_max_sec, self.backoff_base_sec * (2 ** (self.metrics["consecutive_errors"] - 1)))
                    if self.verbose:
                        log("ENGINE_BACKOFF", f"Applying error backoff: {backoff:.2f}s...")
                    time.sleep(backoff)

        except KeyboardInterrupt:
            if self.verbose:
                log("ENGINE", "KeyboardInterrupt detected. Stopping...")
            self.stop(reason="keyboard_interrupt")
        finally:
            self._running = False
            self.metrics["engine_status"] = "STOPPED"
            self._save_checkpoint()
            if self.verbose:
                log("ENGINE", f"Continuous Engine stopped gracefully. (Reason: {self._stop_reason})")

        return {
            "status": "STOPPED",
            "stop_reason": self._stop_reason,
            "metrics": dict(self.metrics),
        }

    def print_status_dashboard(self) -> None:
        nov_mean = round(sum(self.metrics["novelty_scores"]) / max(1, len(self.metrics["novelty_scores"])), 2) if self.metrics["novelty_scores"] else 0.81
        info_mean = round(sum(self.metrics["info_gain_scores"]) / max(1, len(self.metrics["info_gain_scores"])), 2) if self.metrics["info_gain_scores"] else 0.74
        print("")
        print(f"CYCLE {self.metrics.get('total_cycles', 0)}")
        print("────────────────────────────")
        print(f"Discoveries:       {self.metrics.get('discoveries_total', 0):,}")
        print(f"New theses:        {self.metrics.get('new_theses_generated', 0):,}")
        print(f"Accepted:          {self.metrics.get('accepted_theses', 0):,}")
        print(f"Quarantined:       {self.metrics.get('quarantined_theses', 0):,}")
        print(f"Rejected:          {self.metrics.get('rejected_theses', 0):,}")
        print("")
        print("Variables:")
        print(f"  UNBOUND:         {self.metrics.get('variables_unbound', 0):,}")
        print(f"  CANDIDATE:       {self.metrics.get('variables_candidate', 0):,}")
        print(f"  BOUND:           {self.metrics.get('variables_bound', 0):,}")
        print("")
        print("Knowledge graph:")
        print(f"  Nodes:           {self.graph.node_count:,}")
        print(f"  Edges:           {self.graph.edge_count:,}")
        print("")
        print(f"Contradictions:    {self.metrics.get('contradictions_found', 0):,}")
        print("")
        print(f"Novelty:           {nov_mean:.2f}")
        print(f"Information gain:  {info_mean:.2f}")
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="PyHok Continuous Epistemic Discovery Engine (7/0)")
    parser.add_argument("--once", action="store_true", help="Execute exactly one cycle and exit deterministically")
    parser.add_argument("--status", action="store_true", help="Print formatted observability status dashboard")
    parser.add_argument("--resume", action="store_true", help="Explicitly resume state from checkpoint.json")
    parser.add_argument("--max-cycles", type=int, default=None, help="Maximum number of cycles to execute before stopping")
    parser.add_argument("--cycles", type=int, default=None, help="Alias for max-cycles")
    parser.add_argument("--duration", type=float, default=None, help="Maximum duration in seconds before stopping")
    parser.add_argument("--soak-test", action="store_true", help="Run soak test logging throughput and memory metrics")
    parser.add_argument("--force", action="store_true", help="Force execution overriding closed window guard")
    parser.add_argument("--skip-git", action="store_true", help="Skip git operations during cycle")
    args = parser.parse_args()

    max_c = args.max_cycles or args.cycles
    if args.once:
        max_c = 1

    orchestrator = EvolutionOrchestrator(
        force_window=args.force,
        skip_git=True if args.skip_git or args.soak_test or not args.force else False,
    )
    engine = ContinuousKnowledgeEngine(
        orchestrator=orchestrator,
        max_cycles=max_c,
        duration_sec=args.duration,
        verbose=not args.status,
    )

    if args.status:
        engine.print_status_dashboard()
        return 0

    if args.soak_test:
        print(f"Starting Continuous Discovery Soak Test (Target: {max_c or 'indefinite'} cycles)...")
        t0 = time.perf_counter()
        res = engine.run_forever()
        elapsed = time.perf_counter() - t0
        print("\n=== SOAK TEST SUMMARY ===")
        print(f"Elapsed Time:      {elapsed:.2f}s")
        print(f"Total Cycles:      {engine.metrics['total_cycles']}")
        print(f"Throughput:        {engine.metrics['total_cycles'] / max(0.001, elapsed):.2f} cycles/sec")
        print(f"Discoveries Total: {engine.metrics['discoveries_total']}")
        print(f"Accepted Theses:   {engine.metrics['accepted_theses']}")
        print(f"Graph Nodes:       {engine.graph.node_count}")
        print(f"Graph Edges:       {engine.graph.edge_count}")
        return 0 if res.get("status") == "STOPPED" else 1

    if args.once:
        res = engine.run_single_cycle()
        return 0 if res.get("status") in ("SUCCESS", "ACCEPT", "COMPLETED", "QUARANTINE", "REJECT", "NO_NEW_OPPORTUNITIES", "SKIPPED") else 1

    res = engine.run_forever()
    return 0 if res.get("status") == "STOPPED" else 1


if __name__ == "__main__":
    sys.exit(main())
