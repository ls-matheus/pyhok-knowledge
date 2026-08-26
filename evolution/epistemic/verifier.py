from __future__ import annotations

from typing import Any


class EvidenceVerifier:
    """
    Evidence and Provenance Verifier (v2.1):
    Role: Verify topological provenance, prevent circular reasoning via transitive DAG traversal, compute derivation depth, and enforce strict epistemic status derivation.
    """

    MAX_DERIVATION_DEPTH = 3

    def __init__(self, max_depth: int = MAX_DERIVATION_DEPTH):
        self.max_depth = max_depth

    def verify_provenance(
        self,
        proposal: dict[str, Any] | None,
        knowledge_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        circularity_detected = False

        if not proposal or not isinstance(proposal, dict):
            return {
                "verifier_role": "EVIDENCE_VERIFIER",
                "verdict": "UNGROUNDED",
                "derivation_depth": 0,
                "evidence_roots": [],
                "independent_evidence_count": 0,
                "pre_existing_evidence": False,
                "circularity_detected": False,
                "evidence_strength_score": 0.0,
                "independence_score": 0.0,
                "provenance_integrity_score": 0.0,
                "eligible_for_derived_status": False,
                "errors": ["Proposal is null or not a dictionary."],
                "warnings": [],
                "passes_verification": False,
            }

        q_data = proposal.get("question") if isinstance(proposal.get("question"), dict) else proposal
        if not isinstance(q_data, dict):
            q_data = {}

        q_id = q_data.get("id")
        req_signals = q_data.get("required_signals", [])
        if not isinstance(req_signals, list):
            req_signals = []

        prov = q_data.get("provenance", {})
        if not isinstance(prov, dict):
            prov = {}

        derived_from = prov.get("derived_from", [])
        if not isinstance(derived_from, list):
            derived_from = []

        evidence_roots = prov.get("evidence_roots", [])
        if not isinstance(evidence_roots, list):
            evidence_roots = []

        # 1. Verify Pre-Existing Evidence against canonical dataset
        canonical_signals = set()
        existing_questions_map: dict[str, dict[str, Any]] = {}

        if knowledge_state and isinstance(knowledge_state, dict):
            if "signals" in knowledge_state and isinstance(knowledge_state["signals"], list):
                canonical_signals = {
                    s.get("id") for s in knowledge_state["signals"]
                    if isinstance(s, dict) and s.get("id")
                }
            if "questions" in knowledge_state and isinstance(knowledge_state["questions"], list):
                for q in knowledge_state["questions"]:
                    if isinstance(q, dict) and q.get("id"):
                        existing_questions_map[q.get("id")] = q

        # Default evidence roots to declared signals if not provided
        if not evidence_roots:
            evidence_roots = [s for s in req_signals if isinstance(s, str)]

        # Check for missing signals
        if canonical_signals:
            missing_signals = [s for s in req_signals if s not in canonical_signals]
            if missing_signals:
                errors.append(f"Required signals not found in pre-existing canonical signals: {missing_signals}")
        elif len(req_signals) == 0:
            errors.append("Proposal declares zero required signals.")

        # 2. Check for Direct Self-Derivation / Self-Loops
        if q_id and q_id in derived_from:
            circularity_detected = True
            errors.append(f"Self-referential derivation detected: question '{q_id}' derives from itself.")

        if q_id and q_id in evidence_roots:
            circularity_detected = True
            errors.append(f"Self-evident circularity detected: question '{q_id}' is listed as its own evidence root.")

        # 3. Transitive Cycle Detection (BFS across entire ancestry graph)
        visited = set()
        queue = list(derived_from)

        while queue:
            curr_ancestor_id = queue.pop(0)
            if not isinstance(curr_ancestor_id, str):
                continue
            if curr_ancestor_id == q_id:
                circularity_detected = True
                errors.append(f"Circular derivation loop detected: '{q_id}' is in its own ancestry chain.")
                break
            if curr_ancestor_id in visited:
                continue
            visited.add(curr_ancestor_id)

            anc_q = existing_questions_map.get(curr_ancestor_id)
            if anc_q:
                anc_prov = anc_q.get("provenance", {}) if isinstance(anc_q.get("provenance"), dict) else {}
                anc_parents = anc_prov.get("derived_from", [])
                if isinstance(anc_parents, list):
                    queue.extend(anc_parents)

        # 4. Compute Derivation Depth
        parent_depths: list[int] = []
        for parent_id in derived_from:
            if not isinstance(parent_id, str):
                continue
            parent_q = existing_questions_map.get(parent_id)
            if parent_q:
                p_prov = parent_q.get("provenance", {}) if isinstance(parent_q.get("provenance"), dict) else {}
                p_depth = p_prov.get("derivation_depth", 0)
                if isinstance(p_depth, int):
                    parent_depths.append(p_depth)
            else:
                warnings.append(f"Parent question '{parent_id}' not found in canonical dataset (assuming depth=1).")
                parent_depths.append(1)

        derivation_depth = (1 + max(parent_depths)) if parent_depths else (1 if derived_from else 0)

        # 5. Count Disjoint Independent Evidence Roots
        unique_roots = set(r for r in evidence_roots if isinstance(r, str))
        independent_count = len(unique_roots)

        # 6. Apply Derivation Depth Ceilings
        if derivation_depth > self.max_depth and independent_count == 0:
            errors.append(
                f"Derivation depth {derivation_depth} exceeds maximum limit ({self.max_depth}) with 0 independent empirical roots."
            )

        # 7. Strict Eligibility for DERIVED status
        eligible_for_derived = (
            derivation_depth > 0
            and len(derived_from) > 0
            and independent_count >= 1
            and not circularity_detected
            and not errors
        )

        # Mathematical score bounds [0.0, 1.0]
        evidence_strength_score = 1.0 if (req_signals and not errors) else max(0.0, 1.0 - (len(errors) * 0.35))
        independence_score = min(1.0, max(0.0, round(independent_count / max(1, derivation_depth), 4)))
        provenance_integrity_score = 0.0 if circularity_detected else (0.5 if warnings else 1.0)
        if errors and not circularity_detected:
            provenance_integrity_score = max(0.0, provenance_integrity_score - 0.4)

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
            "evidence_strength_score": round(evidence_strength_score, 4),
            "independence_score": round(independence_score, 4),
            "provenance_integrity_score": round(provenance_integrity_score, 4),
            "eligible_for_derived_status": eligible_for_derived,
            "errors": errors,
            "warnings": warnings,
            "passes_verification": is_verified,
        }


def validate_provenance(
    proposal: dict[str, Any] | None,
    knowledge_state: dict[str, Any] | None = None
) -> dict[str, Any]:
    verifier = EvidenceVerifier()
    return verifier.verify_provenance(proposal, knowledge_state)


def verify_epistemic_provenance(
    proposal: dict[str, Any] | None,
    knowledge_state: dict[str, Any] | None = None
) -> dict[str, Any]:
    return validate_provenance(proposal, knowledge_state)
