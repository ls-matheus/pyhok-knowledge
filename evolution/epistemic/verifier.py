from __future__ import annotations

from typing import Any


class EvidenceVerifier:
    """
    Evidence and Provenance Verifier:
    Role: Verify topological provenance, prevent circular reasoning, compute derivation depth, and verify evidence pre-existence.
    """

    MAX_DERIVATION_DEPTH = 3

    def __init__(self, max_depth: int = MAX_DERIVATION_DEPTH):
        self.max_depth = max_depth

    def verify_provenance(
        self,
        proposal: dict[str, Any],
        knowledge_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        q_data = proposal.get("question", {}) or proposal
        proposal_id = proposal.get("proposal_id", "prop_unknown")
        req_signals = q_data.get("required_signals", [])
        prov = q_data.get("provenance", {})

        derived_from = prov.get("derived_from", [])
        evidence_roots = prov.get("evidence_roots", [])

        # Default evidence roots to declared signals if not explicitly specified
        if not evidence_roots:
            evidence_roots = list(req_signals)

        errors: list[str] = []
        circularity_detected = False

        # 1. Verify Pre-Existing Evidence (Signals exist in canonical dataset)
        canonical_signals = set()
        if knowledge_state and "signals" in knowledge_state:
            canonical_signals = {s.get("id") for s in knowledge_state["signals"] if s.get("id")}

        if canonical_signals:
            missing_signals = [s for s in req_signals if s not in canonical_signals]
            if missing_signals:
                errors.append(f"Required signals not found in pre-existing canonical signals: {missing_signals}")

        # 2. Check for Direct Self-Derivation / Circularity
        q_id = q_data.get("id")
        if q_id and q_id in derived_from:
            circularity_detected = True
            errors.append(f"Self-referential derivation detected: question '{q_id}' derives from itself.")

        # 3. Compute Derivation Depth from Ancestors in Knowledge State
        parent_depths: list[int] = []
        existing_questions_map = {}
        if knowledge_state and "questions" in knowledge_state:
            for q in knowledge_state["questions"]:
                qid = q.get("id")
                if qid:
                    existing_questions_map[qid] = q

        for parent_id in derived_from:
            parent_q = existing_questions_map.get(parent_id)
            if parent_q:
                p_prov = parent_q.get("provenance", {})
                p_depth = p_prov.get("derivation_depth", 0)
                parent_depths.append(p_depth)
                # Check for ancestral loops
                p_ancestors = set(p_prov.get("derived_from", []))
                if q_id and q_id in p_ancestors:
                    circularity_detected = True
                    errors.append(f"Circular derivation loop detected between '{q_id}' and '{parent_id}'.")
            else:
                # Parent question is not in canonical knowledge base
                parent_depths.append(1)

        derivation_depth = (1 + max(parent_depths)) if parent_depths else (1 if derived_from else 0)

        # 4. Count Disjoint Independent Evidence Roots
        unique_roots = set(evidence_roots)
        independent_count = len(unique_roots)

        # 5. Apply Derivation Depth Threshold
        if derivation_depth > self.max_depth and independent_count == 0:
            errors.append(
                f"Derivation depth {derivation_depth} exceeds maximum limit ({self.max_depth}) with 0 independent empirical evidence roots."
            )

        is_verified = (not errors and not circularity_detected)
        verdict = "VERIFIED" if is_verified else "UNGROUNDED"

        return {
            "verifier_role": "EVIDENCE_VERIFIER",
            "verdict": verdict,
            "derivation_depth": derivation_depth,
            "evidence_roots": sorted(list(unique_roots)),
            "independent_evidence_count": independent_count,
            "pre_existing_evidence": (len(req_signals) > 0 and not any("not found in pre-existing" in e for e in errors)),
            "circularity_detected": circularity_detected,
            "errors": errors,
            "passes_verification": is_verified,
        }


def verify_epistemic_provenance(
    proposal: dict[str, Any],
    knowledge_state: dict[str, Any] | None = None
) -> dict[str, Any]:
    verifier = EvidenceVerifier()
    return verifier.verify_provenance(proposal, knowledge_state)
