from __future__ import annotations

import re
from typing import Any


KNOWN_CONFOUNDER_MAP = {
    "sig_response_latency_variance_v1": [
        "system_thermal_throttling",
        "network_jitter",
        "user_multitasking",
        "practice_effect"
    ],
    "sig_gaze_fixation_duration_v1": [
        "screen_glare",
        "ambient_distraction",
        "visual_fatigue",
        "ambient_noise"
    ],
    "sig_test_pointer_velocity": [
        "dpi_scaling",
        "cursor_acceleration",
        "sensor_noise",
        "mouse_slip",
        "device_latency"
    ],
}

ALL_KNOWN_CONFOUNDERS = {
    "screen_glare": "ambient",
    "ambient_distraction": "ambient",
    "visual_fatigue": "behavioral",
    "ambient_noise": "ambient",
    "system_thermal_throttling": "hardware",
    "network_jitter": "hardware",
    "user_multitasking": "behavioral",
    "practice_effect": "behavioral",
    "dpi_scaling": "hardware",
    "cursor_acceleration": "hardware",
    "sensor_noise": "hardware",
    "mouse_slip": "hardware",
    "device_latency": "hardware",
    "sampling_rate_quantization": "measurement",
    "session_fatigue": "behavioral",
}


class AlternativeExplanationAgent:
    """
    Red-Team / Alternative Explanation Agent (v2):
    Role: Challenges the proposal by seeking non-causal explanations, unmodeled confounders, measurement artifacts, and Occam's razor violations.
    """

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def evaluate_alternatives(
        self,
        proposal: dict[str, Any] | None,
        knowledge_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        alternative_hypotheses: list[str] = []
        confounders_identified: list[str] = []
        mitigated_confounders: list[str] = []
        unmitigated_confounders: list[str] = []

        if not proposal or not isinstance(proposal, dict):
            return {
                "red_team_role": "ALTERNATIVE_EXPLANATION_AGENT",
                "verdict": "FAIL",
                "alternative_hypotheses": ["Proposal is null or empty."],
                "confounders_identified": [],
                "mitigated_confounders": [],
                "unmitigated_confounders": [],
                "parsimony_score": 0.0,
                "resistance_to_alternatives": 0.0,
                "passes_red_team_check": False,
            }

        q_data = proposal.get("question") if isinstance(proposal.get("question"), dict) else proposal
        if not isinstance(q_data, dict):
            q_data = {}

        hypothesis = str(q_data.get("hypothesis", "") or "")
        req_signals = q_data.get("required_signals", [])
        if not isinstance(req_signals, list):
            req_signals = []

        trigger = q_data.get("evaluation_trigger", {})
        if not isinstance(trigger, dict):
            trigger = {}
        rules = trigger.get("rules", [])
        if not isinstance(rules, list):
            rules = []

        hypo_lower = hypothesis.lower()

        # 1. Identify Confounders based on signals & text
        for sig in req_signals:
            if isinstance(sig, str) and sig in KNOWN_CONFOUNDER_MAP:
                for c in KNOWN_CONFOUNDER_MAP[sig]:
                    if c not in confounders_identified:
                        confounders_identified.append(c)

        for c_name in ALL_KNOWN_CONFOUNDERS:
            c_text = c_name.replace("_", " ")
            if c_text in hypo_lower or c_name in hypo_lower:
                if c_name not in confounders_identified:
                    confounders_identified.append(c_name)

        # 2. Check Mitigation Status
        for c in confounders_identified:
            c_clean = c.replace("_", " ")
            # If the hypothesis text or rules explicitly address / control for this confounder
            if f"controlling for {c_clean}" in hypo_lower or f"excluding {c_clean}" in hypo_lower or f"adjusted for {c_clean}" in hypo_lower:
                mitigated_confounders.append(c)
            else:
                unmitigated_confounders.append(c)

        if unmitigated_confounders:
            clean_unmitigated = [u.replace("_", " ") for u in unmitigated_confounders[:4]]
            alternative_hypotheses.append(
                f"Observed signals may be confounded by unmodeled factors: {', '.join(clean_unmitigated)}."
            )

        # 3. Principled Occam's Razor / Complexity Evaluation
        # Complexity is evaluated relative to the explanatory scope:
        num_rules = len(rules)
        num_signals = max(1, len(req_signals))
        ratio = num_rules / num_signals

        if num_rules == 0:
            parsimony_score = 0.0
        elif num_rules == 1:
            parsimony_score = 1.0
        elif num_rules <= 3:
            parsimony_score = 0.90
        elif num_rules <= 6:
            # If multi-signal, ratio is low (justified complexity)
            if ratio <= 2.0:
                parsimony_score = 0.75
            else:
                parsimony_score = 0.50
                alternative_hypotheses.append(
                    f"Overcomplicated rule structure ({num_rules} rules on {num_signals} signals); simpler threshold likely suffices."
                )
        else:
            # Severe Occam's razor penalty for > 6 rules
            parsimony_score = max(0.10, round(1.0 - (num_rules * 0.08), 4))
            alternative_hypotheses.append(
                f"Severe Occam's razor violation ({num_rules} rules). High risk of post-hoc overfitting."
            )

        # 4. Check for Subsumption by Simpler Canonical Questions
        if knowledge_state and isinstance(knowledge_state, dict) and "questions" in knowledge_state:
            ex_questions = knowledge_state.get("questions", [])
            if isinstance(ex_questions, list):
                for ex_q in ex_questions:
                    if not isinstance(ex_q, dict):
                        continue
                    ex_signals = set(ex_q.get("required_signals", []) if isinstance(ex_q.get("required_signals"), list) else [])
                    if set(req_signals).issubset(ex_signals) and len(req_signals) > 0:
                        ex_hypo = str(ex_q.get("hypothesis", "") or "").lower()
                        curr_words = set(re.findall(r"\w{4,}", hypo_lower))
                        ex_words = set(re.findall(r"\w{4,}", ex_hypo))
                        if len(curr_words & ex_words) >= 4:
                            alternative_hypotheses.append(
                                f"Proposed hypothesis is largely subsumed by simpler canonical question '{ex_q.get('id')}'."
                            )
                            parsimony_score = max(0.0, parsimony_score - 0.20)

        # Mathematical score bounds [0.0, 1.0]
        parsimony_score = min(1.0, max(0.0, round(parsimony_score, 4)))
        unmitigated_penalty = min(0.40, len(unmitigated_confounders) * 0.08)
        resistance_to_alternatives = min(1.0, max(0.0, round(1.0 - unmitigated_penalty - ((1.0 - parsimony_score) * 0.4), 4)))

        verdict = "PASS" if (resistance_to_alternatives >= 0.50 and parsimony_score >= 0.50) else "CHALLENGED"

        return {
            "red_team_role": "ALTERNATIVE_EXPLANATION_AGENT",
            "verdict": verdict,
            "alternative_hypotheses": alternative_hypotheses,
            "confounders_identified": sorted(confounders_identified),
            "mitigated_confounders": sorted(mitigated_confounders),
            "unmitigated_confounders": sorted(unmitigated_confounders),
            "parsimony_score": parsimony_score,
            "resistance_to_alternatives": resistance_to_alternatives,
            "passes_red_team_check": (verdict == "PASS" and parsimony_score >= 0.50),
        }


def run_alternative_explanation_agent(
    proposal: dict[str, Any] | None,
    knowledge_state: dict[str, Any] | None = None
) -> dict[str, Any]:
    agent = AlternativeExplanationAgent()
    return agent.evaluate_alternatives(proposal, knowledge_state)
