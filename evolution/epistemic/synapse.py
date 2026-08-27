from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any


DOGMATIC_OPEN_VAR_TERMS = [
    "definitive cause",
    "absolute proof",
    "confirms disorder",
    "diagnose",
    "diagnosis",
    "pathology",
    "guaranteed trigger",
]


class SinapseBindingEngine:
    """
    Sinapse Binding Engine (v2.0):
    Role: Deterministically binds open variables in investigative theses against
    the active observational context and runtime signals without fabricating evidence.
    Enforces the fundamental constitutional principles:
    1. BINDING != EVIDENCE (Synapse instantiates variables; it does not certify empirical roots).
    2. CLOSED-WORLD HONESTY (Preserves UNBOUND/CANDIDATE state when evidence is insufficient).
    3. TAXONOMY INTEGRITY (UNBOUND -> CANDIDATE -> BOUND / INVALID).
    """

    def __init__(self, strict_neutrality: bool = True):
        self.strict_neutrality = strict_neutrality

    def validate_variable_neutrality(self, variable: dict[str, Any]) -> tuple[bool, str | None]:
        if not isinstance(variable, dict):
            return False, "Variable is not a dictionary object."

        var_id = str(variable.get("id", "") or variable.get("variable_id", "") or "").lower()
        role = str(variable.get("role", "") or "").lower()
        desc = str(variable.get("description", "") or "").lower()

        combined_text = f"{var_id} {role} {desc}"
        for term in DOGMATIC_OPEN_VAR_TERMS:
            if term in combined_text:
                return False, f"Dogmatic/overreach term '{term}' detected in open variable specification."

        return True, None

    def prepare_or_bind(
        self,
        thesis_or_proposal: dict[str, Any] | None,
        context: dict[str, Any] | None = None,
        cycle_id: str | None = None
    ) -> dict[str, Any]:
        if not thesis_or_proposal or not isinstance(thesis_or_proposal, dict):
            return {"status": "INVALID", "error": "Null or malformed proposal/thesis payload."}

        enriched = copy.deepcopy(thesis_or_proposal)

        target = enriched
        if "thesis" in enriched and isinstance(enriched["thesis"], dict):
            target = enriched["thesis"]
        elif "question" in enriched and isinstance(enriched["question"], dict):
            target = enriched["question"]
        elif "payload" in enriched and isinstance(enriched["payload"], dict):
            target = enriched["payload"]

        open_vars = target.get("open_variables")
        if not open_vars or not isinstance(open_vars, list):
            return enriched

        available_signals: dict[str, dict[str, Any]] = {}
        if context and isinstance(context, dict):
            if "signals" in context and isinstance(context["signals"], list):
                for s in context["signals"]:
                    if isinstance(s, dict) and "id" in s:
                        available_signals[s["id"]] = s
            elif "available_signals" in context and isinstance(context["available_signals"], list):
                for sid in context["available_signals"]:
                    if isinstance(sid, str):
                        available_signals[sid] = {"id": sid}

        bound_count = 0
        candidate_count = 0
        total_vars = len(open_vars)
        variable_bindings: dict[str, Any] = {}

        for var in open_vars:
            if not isinstance(var, dict):
                continue

            is_neutral, err = self.validate_variable_neutrality(var)
            if not is_neutral:
                target["investigation_status"] = "REJECTED"
                target["binding_error"] = err
                var["status"] = "INVALID"
                return enriched

            status = var.get("status", "UNBOUND")
            var_id = var.get("id") or var.get("variable_id")
            role = var.get("role", "unspecified")
            domain = var.get("domain")
            candidates = var.get("candidate_values", [])

            if status == "BOUND" and var.get("binding"):
                bound_count += 1
                variable_bindings[var_id] = {
                    "binding": var.get("binding"),
                    "binding_source": var.get("binding_source", "SYNAPSE"),
                    "status": "BOUND",
                }
                continue

            # Attempt deterministic binding from available context
            matched_signal_id = None
            for sig_id, sig_info in available_signals.items():
                sig_domain = sig_info.get("domain")
                if candidates and sig_id in candidates:
                    matched_signal_id = sig_id
                    break
                elif domain and sig_domain and domain == sig_domain:
                    matched_signal_id = sig_id
                    break
                elif var_id and (var_id in sig_id or sig_id.replace("sig_", "") in var_id):
                    matched_signal_id = sig_id
                    break

            if matched_signal_id:
                var["status"] = "BOUND"
                var["binding"] = matched_signal_id
                var["value"] = matched_signal_id
                var["binding_source"] = "SYNAPSE"
                var["bound_at"] = datetime.now(timezone.utc).isoformat()
                bound_count += 1
                variable_bindings[var_id] = {
                    "binding": matched_signal_id,
                    "binding_source": "SYNAPSE",
                    "status": "BOUND",
                }
                req_signals = target.get("required_signals", [])
                if isinstance(req_signals, list) and matched_signal_id not in req_signals:
                    req_signals.append(matched_signal_id)
                    target["required_signals"] = req_signals
            elif candidates:
                # Plausible candidates exist, but none present in context
                var["status"] = "CANDIDATE"
                var["binding"] = None
                var["binding_source"] = None
                candidate_count += 1
                variable_bindings[var_id] = {
                    "binding": None,
                    "binding_source": None,
                    "status": "CANDIDATE",
                }
            else:
                # Honestly preserve UNBOUND state
                var["status"] = "UNBOUND"
                var["binding"] = None
                var["binding_source"] = None
                variable_bindings[var_id] = {
                    "binding": None,
                    "binding_source": None,
                    "status": "UNBOUND",
                }

        # Update overall investigation status
        if bound_count == total_vars and total_vars > 0:
            target["investigation_status"] = "BOUND"
            target["resolution"] = "BOUND_FOR_EVALUATION"
        elif bound_count > 0:
            target["investigation_status"] = "PARTIALLY_BOUND"
            target["resolution"] = "DEFERRED_TO_SYNAPSE"
        else:
            target["investigation_status"] = "OPEN"
            target["resolution"] = "DEFERRED_TO_SYNAPSE"

        if "provenance" not in target or not isinstance(target["provenance"], dict):
            target["provenance"] = {}

        target["provenance"]["variable_bindings"] = variable_bindings
        target["provenance"]["binding_source"] = "SYNAPSE" if bound_count > 0 else None
        if not available_signals and bound_count == 0:
            target["provenance"]["binding_verdict"] = "NO_NEW_EVIDENCE"

        return enriched


def bind_open_thesis(
    thesis_or_proposal: dict[str, Any] | None,
    context: dict[str, Any] | None = None,
    cycle_id: str | None = None
) -> dict[str, Any]:
    engine = SinapseBindingEngine()
    return engine.prepare_or_bind(thesis_or_proposal, context, cycle_id)
