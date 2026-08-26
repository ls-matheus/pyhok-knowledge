from __future__ import annotations

import re
from typing import Any


FORBIDDEN_DIAGNOSTIC_TERMS = [
    "diagnose",
    "diagnosis",
    "confirms syndrome",
    "clinical diagnosis",
    "confirmed disorder",
    "has autism",
    "has adhd",
    "cures",
    "pathology",
]


class AdversarialCritic:
    """
    Adversarial Epistemic Critic:
    Role: Challenge, scrutinize, and attempt to disprove or find critical weaknesses in the proposed hypothesis.
    """

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def review_proposal(
        self,
        proposal: dict[str, Any],
        knowledge_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        challenges: list[str] = []
        contradictions: list[str] = []
        severity = 0.0

        q_data = proposal.get("question", {}) or proposal
        hypothesis = q_data.get("hypothesis", "")
        req_signals = q_data.get("required_signals", [])
        trigger = q_data.get("evaluation_trigger", {})
        rules = trigger.get("rules", [])

        # 1. Check for forbidden diagnostic / clinical overreach language
        hypo_lower = hypothesis.lower()
        for term in FORBIDDEN_DIAGNOSTIC_TERMS:
            if term in hypo_lower:
                challenges.append(f"Diagnostic overreach detected: mentions forbidden term '{term}'")
                severity += 0.40

        # 2. Check for missing or empty hypothesis
        if not hypothesis or len(hypothesis.strip()) < 10:
            challenges.append("Hypothesis statement is trivially short, vague, or empty.")
            severity += 0.50

        # 3. Check for unsubstantiated multi-signal rules
        if len(rules) == 0:
            challenges.append("Evaluation trigger contains zero operational rules.")
            severity += 0.60

        rule_signals = [r.get("signal_id") for r in rules if r.get("signal_id")]
        for rs in rule_signals:
            if rs not in req_signals:
                challenges.append(f"Trigger rule references signal '{rs}' not declared in required_signals.")
                severity += 0.30

        # 4. Check for direct semantic contradiction with existing canonical questions
        if knowledge_state and "questions" in knowledge_state:
            for ex_q in knowledge_state["questions"]:
                ex_signals = set(ex_q.get("required_signals", []))
                curr_signals = set(req_signals)
                # If exact same signals, check for opposite threshold direction with same interpretation
                if ex_signals == curr_signals and len(curr_signals) > 0:
                    ex_rules = ex_q.get("evaluation_trigger", {}).get("rules", [])
                    if len(ex_rules) == len(rules) == 1:
                        r_curr = rules[0]
                        r_ex = ex_rules[0]
                        if r_curr.get("signal_id") == r_ex.get("signal_id"):
                            op_curr = r_curr.get("operator")
                            op_ex = r_ex.get("operator")
                            # Direct inversion (< vs > on same signal with identical weights)
                            if (op_curr == ">" and op_ex == "<") or (op_curr == "<" and op_ex == ">"):
                                contradictions.append(
                                    f"Direct operator contradiction on signal '{r_curr.get('signal_id')}' with canonical question '{ex_q.get('id')}'"
                                )
                                severity += 0.35

        # 5. Check for tautological / empty thresholds
        for r in rules:
            thresh = r.get("threshold")
            if thresh is None or not isinstance(thresh, (int, float)):
                challenges.append("Rule threshold is missing or not a numerical value.")
                severity += 0.30

        severity = min(1.0, round(severity, 4))
        verdict = "FAIL" if severity >= 0.50 or contradictions else ("CHALLENGED" if severity > 0.0 else "PASS")

        return {
            "critic_role": "ADVERSARIAL_CRITIC",
            "verdict": verdict,
            "severity_score": severity,
            "challenges": challenges,
            "contradictions": contradictions,
            "passes_adversarial_check": (verdict in ("PASS", "CHALLENGED") and not contradictions and severity < 0.50),
        }


def run_adversarial_critic(proposal: dict[str, Any], knowledge_state: dict[str, Any] | None = None) -> dict[str, Any]:
    critic = AdversarialCritic()
    return critic.review_proposal(proposal, knowledge_state)
