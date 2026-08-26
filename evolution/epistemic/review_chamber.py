from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evolution.epistemic.critic import AdversarialCritic
from evolution.epistemic.verifier import EvidenceVerifier
from evolution.epistemic.red_team import AlternativeExplanationAgent
from evolution.epistemic.judge import BlindEpistemicJudge
from evolution.epistemic.quarantine import record_quarantined_claim, check_prior_rejections, REJECTED_CLAIMS_FILE


class EpistemicReviewChamber:
    """
    Coordinates the parallel multi-agent epistemic review chamber (v2):
    Generator -> [Critic || Verifier || Red-Team || Active Memory] -> Blind Judge -> (Accept / Quarantine).
    """

    def __init__(
        self,
        critic: AdversarialCritic | None = None,
        verifier: EvidenceVerifier | None = None,
        red_team: AlternativeExplanationAgent | None = None,
        judge: BlindEpistemicJudge | None = None,
        quarantine_file: Path = REJECTED_CLAIMS_FILE,
    ):
        self.critic = critic or AdversarialCritic()
        self.verifier = verifier or EvidenceVerifier()
        self.red_team = red_team or AlternativeExplanationAgent()
        self.judge = judge or BlindEpistemicJudge()
        self.quarantine_file = quarantine_file

    def review(
        self,
        proposal: dict[str, Any],
        knowledge_state: dict[str, Any] | None = None,
        cycle_id: str | None = None,
    ) -> dict[str, Any]:
        # 1. Adversarial Critic Review (Parallel Peer 1)
        critic_review = self.critic.review_proposal(proposal, knowledge_state)

        # 2. Evidence & Provenance Verification (Parallel Peer 2)
        verifier_review = self.verifier.verify_provenance(proposal, knowledge_state)

        # 3. Red-Team / Alternative Explanation Review (Parallel Peer 3)
        red_team_review = self.red_team.evaluate_alternatives(proposal, knowledge_state)

        # 4. Active Negative Memory Review (Parallel Peer 4)
        memory_review = check_prior_rejections(proposal, file_path=self.quarantine_file)

        # 5. Blind Epistemic Judgment
        judge_ruling = self.judge.judge(
            proposal=proposal,
            critic_review=critic_review,
            verifier_review=verifier_review,
            red_team_review=red_team_review,
            memory_review=memory_review,
        )

        decision = judge_ruling.get("decision")

        # 6. Handle Outcome
        if decision in ("QUARANTINE", "REJECT"):
            record_quarantined_claim(
                proposal=proposal,
                judge_ruling=judge_ruling,
                critic_review=critic_review,
                verifier_review=verifier_review,
                red_team_review=red_team_review,
                cycle_id=cycle_id,
                file_path=self.quarantine_file
            )

        # Inject epistemic metadata into question if ACCEPTED
        elif decision == "ACCEPT":
            q_data = proposal.get("question") if "question" in proposal else proposal
            if isinstance(q_data, dict):
                q_data["epistemic_status"] = judge_ruling.get("assigned_epistemic_status", "HYPOTHESIS")
                if "provenance" not in q_data:
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
            "reviewed_proposal": proposal,
        }


def run_epistemic_review(
    proposal: dict[str, Any],
    knowledge_state: dict[str, Any] | None = None,
    cycle_id: str | None = None,
    quarantine_file: Path = REJECTED_CLAIMS_FILE,
) -> dict[str, Any]:
    chamber = EpistemicReviewChamber(quarantine_file=quarantine_file)
    return chamber.review(proposal, knowledge_state, cycle_id)
