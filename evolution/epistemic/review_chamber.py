from __future__ import annotations

import copy
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from evolution.epistemic.critic import AdversarialCritic
from evolution.epistemic.verifier import EvidenceVerifier
from evolution.epistemic.red_team import AlternativeExplanationAgent
from evolution.epistemic.judge import BlindEpistemicJudge
from evolution.epistemic.quarantine import record_quarantined_claim, check_prior_rejections, REJECTED_CLAIMS_FILE


class EpistemicReviewChamber:
    """
    Coordinates the parallel multi-agent epistemic review chamber (v2.2):
    Generator -> Sanitizer -> [Critic || Verifier || Red-Team || Active Memory] -> Blind Judge -> (Accept / Quarantine).
    Guarantees that input proposals are never mutated in-place and executes peer reviewers in isolated threads.
    """

    def __init__(
        self,
        critic: AdversarialCritic | None = None,
        verifier: EvidenceVerifier | None = None,
        red_team: AlternativeExplanationAgent | None = None,
        judge: BlindEpistemicJudge | None = None,
        quarantine_file: Path = REJECTED_CLAIMS_FILE,
        parallel_workers: int = 4,
    ):
        self.critic = critic or AdversarialCritic()
        self.verifier = verifier or EvidenceVerifier()
        self.red_team = red_team or AlternativeExplanationAgent()
        self.judge = judge or BlindEpistemicJudge()
        self.quarantine_file = quarantine_file
        self.parallel_workers = max(1, parallel_workers)

    def review(
        self,
        proposal: dict[str, Any] | None,
        knowledge_state: dict[str, Any] | None = None,
        cycle_id: str | None = None,
    ) -> dict[str, Any]:
        if not proposal or not isinstance(proposal, dict):
            fallback_judge = self.judge.judge(None, None, None)
            return {
                "status": "REJECT",
                "decision": "REJECT",
                "judge_ruling": fallback_judge,
                "critic_review": {},
                "verifier_review": {},
                "red_team_review": {},
                "memory_review": {},
                "reviewed_proposal": proposal,
            }

        # Make a deep copy to prevent mutation of the caller's input payload
        reviewed_proposal = copy.deepcopy(proposal)

        # 1. Execute 4 isolated peer reviews in parallel
        critic_review: dict[str, Any] = {}
        verifier_review: dict[str, Any] = {}
        red_team_review: dict[str, Any] = {}
        memory_review: dict[str, Any] = {}

        tasks = {
            "critic": lambda: self.critic.review_proposal(reviewed_proposal, knowledge_state),
            "verifier": lambda: self.verifier.verify_provenance(reviewed_proposal, knowledge_state),
            "red_team": lambda: self.red_team.evaluate_alternatives(reviewed_proposal, knowledge_state),
            "memory": lambda: check_prior_rejections(reviewed_proposal, file_path=self.quarantine_file),
        }

        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            future_to_key = {executor.submit(fn): key for key, fn in tasks.items()}
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"error": str(exc), "status": "FAIL"}

                if key == "critic":
                    critic_review = result
                elif key == "verifier":
                    verifier_review = result
                elif key == "red_team":
                    red_team_review = result
                elif key == "memory":
                    memory_review = result

        # 2. Blind Epistemic Judgment (Deterministic input order)
        judge_ruling = self.judge.judge(
            proposal=reviewed_proposal,
            critic_review=critic_review,
            verifier_review=verifier_review,
            red_team_review=red_team_review,
            memory_review=memory_review,
        )

        decision = judge_ruling.get("decision")

        # 3. Controlled Persistence (Only if not ACCEPT)
        if decision in ("QUARANTINE", "REJECT"):
            record_quarantined_claim(
                proposal=reviewed_proposal,
                judge_ruling=judge_ruling,
                critic_review=critic_review,
                verifier_review=verifier_review,
                red_team_review=red_team_review,
                cycle_id=cycle_id,
                file_path=self.quarantine_file
            )

        # 4. Attach Provenance Metadata to Enriched Proposal if ACCEPTED
        elif decision == "ACCEPT":
            q_data = reviewed_proposal.get("question") if isinstance(reviewed_proposal.get("question"), dict) else reviewed_proposal
            if isinstance(q_data, dict):
                q_data["epistemic_status"] = judge_ruling.get("assigned_epistemic_status", "HYPOTHESIS")
                if "provenance" not in q_data or not isinstance(q_data["provenance"], dict):
                    q_data["provenance"] = {}
                q_data["provenance"]["epistemic_status"] = q_data["epistemic_status"]
                q_data["provenance"]["derived_from"] = q_data["provenance"].get("derived_from", [])
                q_data["provenance"]["evidence_roots"] = verifier_review.get("evidence_roots", [])
                q_data["provenance"]["derivation_depth"] = verifier_review.get("derivation_depth", 1)
                q_data["provenance"]["independent_evidence_count"] = verifier_review.get("independent_evidence_count", 1)
                q_data["provenance"]["generator_model"] = q_data["provenance"].get("generator_model", "pyhok-agent-v2")
                q_data["provenance"]["cycle_id"] = cycle_id or "cycle_unknown"
                q_data["provenance"]["judge_ruling"] = {
                    "decision": decision,
                    "epistemic_score": judge_ruling.get("epistemic_score"),
                    "epistemic_vector": judge_ruling.get("epistemic_vector"),
                    "critic_severity": critic_review.get("severity_score"),
                }

        return {
            "status": "APPROVED" if decision == "ACCEPT" else decision,
            "decision": decision,
            "judge_ruling": judge_ruling,
            "critic_review": critic_review,
            "verifier_review": verifier_review,
            "red_team_review": red_team_review,
            "memory_review": memory_review,
            "reviewed_proposal": reviewed_proposal,
        }


def run_epistemic_review(
    proposal: dict[str, Any] | None,
    knowledge_state: dict[str, Any] | None = None,
    cycle_id: str | None = None,
    quarantine_file: Path = REJECTED_CLAIMS_FILE,
) -> dict[str, Any]:
    chamber = EpistemicReviewChamber(quarantine_file=quarantine_file)
    return chamber.review(proposal, knowledge_state, cycle_id)
