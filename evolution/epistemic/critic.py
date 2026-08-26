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

CAUSAL_OVERREACH_TERMS = [
    "definitively proves",
    "guarantees that",
    "invariably causes",
    "indisputable cause",
    "absolute proof",
]


class AdversarialCritic:
    """
    Adversarial Epistemic Critic:
    Role: Scrutinize, stress-test, and attempt to disprove or identify critical vulnerabilities in the proposed hypothesis.
    """

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def review_proposal(
        self,
        proposal: dict[str, Any] | None,
        knowledge_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        challenges: list[str] = []
        contradictions: list[str] = []
        severity = 0.0

        if not proposal or not isinstance(proposal, dict):
            return {
                "critic_role": "ADVERSARIAL_CRITIC",
                "verdict": "FAIL",
                "severity_score": 1.0,
                "logical_consistency_score": 0.0,
                "contradiction_status_score": 0.0,
                "adversarial_robustness_score": 0.0,
                "challenges": ["Proposal is null, empty, or not a dictionary."],
                "contradictions": [],
                "passes_adversarial_check": False,
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

        # 1. Check for forbidden diagnostic / clinical overreach language
        hypo_lower = hypothesis.lower()
        for term in FORBIDDEN_DIAGNOSTIC_TERMS:
            if term in hypo_lower:
                challenges.append(f"Diagnostic overreach detected: mentions forbidden term '{term}'")
                severity += 0.45

        # 2. Check for dogmatic causal overreach
        for term in CAUSAL_OVERREACH_TERMS:
            if term in hypo_lower:
                challenges.append(f"Uncalibrated causal overreach detected: mentions phrase '{term}'")
                severity += 0.30

        # 3. Check for missing or trivially short hypothesis
        if not hypothesis or len(hypothesis.strip()) < 10:
            challenges.append("Hypothesis statement is trivially short, vague, or empty.")
            severity += 0.50

        # 4. Check for operational trigger rules
        if len(rules) == 0:
            challenges.append("Evaluation trigger contains zero operational rules.")
            severity += 0.60

        rule_signals = [r.get("signal_id") for r in rules if isinstance(r, dict) and r.get("signal_id")]
        for rs in rule_signals:
            if rs not in req_signals:
                challenges.append(f"Trigger rule references signal '{rs}' not declared in required_signals.")
                severity += 0.30

        # 5. Check for valid thresholds and operators
        valid_operators = {">", "<", ">=", "<=", "==", "!="}
        for r in rules:
            if not isinstance(r, dict):
                challenges.append("Rule in trigger is not a valid dictionary object.")
                severity += 0.30
                continue
            op = r.get("operator")
            if op not in valid_operators:
                challenges.append(f"Invalid logical operator '{op}' in trigger rule.")
                severity += 0.35
            thresh = r.get("threshold")
            if thresh is None or not isinstance(thresh, (int, float)) or isinstance(thresh, bool):
                challenges.append("Rule threshold is missing or not a numerical value.")
                severity += 0.30
            elif abs(thresh) > 1e6:
                challenges.append(f"Extreme/tautological threshold detected: {thresh}")
                severity += 0.25

        # 6. Check for direct semantic contradiction with existing canonical questions
        if knowledge_state and isinstance(knowledge_state, dict) and "questions" in knowledge_state:
            ex_questions = knowledge_state.get("questions", [])
            if isinstance(ex_questions, list):
                for ex_q in ex_questions:
                    if not isinstance(ex_q, dict):
                        continue
                    ex_signals = set(ex_q.get("required_signals", []))
                    curr_signals = set(req_signals)
                    if ex_signals == curr_signals and len(curr_signals) > 0:
                        ex_rules = ex_q.get("evaluation_trigger", {}).get("rules", [])
                        if isinstance(ex_rules, list) and len(ex_rules) == len(rules) == 1:
                            r_curr = rules[0] if isinstance(rules[0], dict) else {}
                            r_ex = ex_rules[0] if isinstance(ex_rules[0], dict) else {}
                            if r_curr.get("signal_id") == r_ex.get("signal_id"):
                                op_curr = r_curr.get("operator")
                                op_ex = r_ex.get("operator")
                                if (op_curr == ">" and op_ex == "<") or (op_curr == "<" and op_ex == ">"):
                                    contradictions.append(
                                        f"Direct operator contradiction on signal '{r_curr.get('signal_id')}' with canonical question '{ex_q.get('id')}'"
                                    )
                                    severity += 0.40

        # Score calculations strictly bounded [0.0, 1.0]
        severity = min(1.0, max(0.0, round(severity, 4)))
        logical_consistency = min(1.0, max(0.0, round(1.0 - (len(challenges) * 0.20), 4)))
        contradiction_status = 0.0 if contradictions else 1.0
        adversarial_robustness = min(1.0, max(0.0, round(1.0 - severity, 4)))

        verdict = "FAIL" if severity >= 0.50 or contradictions else ("CHALLENGED" if severity > 0.0 else "PASS")

        return {
            "critic_role": "ADVERSARIAL_CRITIC",
            "verdict": verdict,
            "severity_score": severity,
            "logical_consistency_score": logical_consistency,
            "contradiction_status_score": contradiction_status,
            "adversarial_robustness_score": adversarial_robustness,
            "challenges": challenges,
            "contradictions": contradictions,
            "passes_adversarial_check": (verdict in ("PASS", "CHALLENGED") and not contradictions and severity < 0.50),
        }


def run_adversarial_critic(
    proposal: dict[str, Any] | None,
    knowledge_state: dict[str, Any] | None = None
) -> dict[str, Any]:
    critic = AdversarialCritic()
    return critic.review_proposal(proposal, knowledge_state)
