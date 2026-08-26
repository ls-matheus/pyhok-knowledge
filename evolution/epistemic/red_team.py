from __future__ import annotations

import re
from typing import Any


KNOWN_CONFOUNDERS = {
    "sig_response_latency_variance_v1": ["system_thermal_throttling", "network_jitter", "user_multitasking"],
    "sig_gaze_fixation_duration_v1": ["screen_glare", "ambient_distraction", "visual_fatigue"],
    "sig_test_pointer_velocity": ["hardware_dpi_scaling", "cursor_acceleration", "physical_mouse_slip"],
}


class AlternativeExplanationAgent:
    """
    Red-Team / Alternative Explanation Agent:
    Role: Challenges the proposal by seeking simpler, non-causal explanations, potential confounders, and Occam's razor violations.
    """

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def evaluate_alternatives(
        self,
        proposal: dict[str, Any],
        knowledge_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        q_data = proposal.get("question", {}) or proposal
        hypothesis = q_data.get("hypothesis", "")
        req_signals = q_data.get("required_signals", [])
        trigger = q_data.get("evaluation_trigger", {})
        rules = trigger.get("rules", [])

        alternative_hypotheses: list[str] = []
        confounders: list[str] = []
        parsimony_penalty = 0.0

        # 1. Identify Confounders based on required signals
        for sig in req_signals:
            if sig in KNOWN_CONFOUNDERS:
                confounders.extend(KNOWN_CONFOUNDERS[sig])

        # 2. Check for Overcomplicated Rules (Occam's razor violation)
        if len(rules) > 4:
            parsimony_penalty += 0.30
            alternative_hypotheses.append(
                f"Rule structure ({len(rules)} conditions) exhibits high complexity; simpler linear threshold may fit noise."
            )

        # 3. Check for Confounder Sensitivity in Hypothesis
        hypo_lower = hypothesis.lower()
        unmitigated_confounders: list[str] = []
        for c in confounders:
            c_clean = c.replace("_", " ")
            if c_clean not in hypo_lower and len(unmitigated_confounders) < 3:
                unmitigated_confounders.append(c_clean)

        if unmitigated_confounders:
            alternative_hypotheses.append(
                f"Phenomenon may be explained by unmodeled confounders: {', '.join(unmitigated_confounders)}."
            )

        # 4. Check for Subsumption by Existing Canonical Questions
        if knowledge_state and "questions" in knowledge_state:
            for ex_q in knowledge_state["questions"]:
                ex_signals = set(ex_q.get("required_signals", []))
                if set(req_signals).issubset(ex_signals) and len(req_signals) > 0:
                    ex_hypo = ex_q.get("hypothesis", "")
                    # If high semantic overlap
                    if len(set(hypo_lower.split()) & set(ex_hypo.lower().split())) >= 4:
                        alternative_hypotheses.append(
                            f"Proposed hypothesis is largely subsumed by simpler canonical question '{ex_q.get('id')}'."
                        )
                        parsimony_penalty += 0.25

        parsimony_score = max(0.0, round(1.0 - parsimony_penalty, 4))
        resistance_to_alternatives = max(0.0, round(1.0 - (len(alternative_hypotheses) * 0.20) - (parsimony_penalty * 0.5), 4))
        verdict = "PASS" if resistance_to_alternatives >= 0.50 else "CHALLENGED"

        return {
            "red_team_role": "ALTERNATIVE_EXPLANATION_AGENT",
            "verdict": verdict,
            "alternative_hypotheses": alternative_hypotheses,
            "confounders_identified": sorted(list(set(confounders))),
            "unmitigated_confounders": unmitigated_confounders,
            "parsimony_score": parsimony_score,
            "resistance_to_alternatives": resistance_to_alternatives,
            "passes_red_team_check": (verdict == "PASS" and parsimony_score >= 0.50),
        }


def run_alternative_explanation_agent(
    proposal: dict[str, Any],
    knowledge_state: dict[str, Any] | None = None
) -> dict[str, Any]:
    agent = AlternativeExplanationAgent()
    return agent.evaluate_alternatives(proposal, knowledge_state)
