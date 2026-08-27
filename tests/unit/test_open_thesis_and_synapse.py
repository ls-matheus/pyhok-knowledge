from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.epistemic.synapse import SinapseBindingEngine, bind_open_thesis
from evolution.epistemic.judge import BlindEpistemicJudge
from evolution.epistemic.critic import AdversarialCritic
from evolution.epistemic.verifier import EvidenceVerifier
from evolution.epistemic.quarantine import record_quarantined_claim, check_prior_rejections
from evolution.epistemic.review_chamber import EpistemicReviewChamber

try:
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT7
    HAS_REFERENCING = True
except ImportError:
    HAS_REFERENCING = False
    from jsonschema import RefResolver
from jsonschema import Draft7Validator


FIXTURE_DIR = ROOT / "tests/fixtures"
SCHEMA_DIR = ROOT / "schemas/v2"


def _build_validator(schema_name: str) -> Draft7Validator:
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    if HAS_REFERENCING:
        resources = []
        for path in SCHEMA_DIR.glob("*.json"):
            s = json.loads(path.read_text(encoding="utf-8"))
            res = Resource.from_contents(s, default_specification=DRAFT7)
            if "$id" in s:
                resources.append((s["$id"], res))
            resources.append((path.name, res))
            resources.append((path.resolve().as_uri(), res))
        registry = Registry().with_resources(resources)
        return Draft7Validator(schema, registry=registry)
    else:
        schema_store = {}
        for path in SCHEMA_DIR.glob("*.json"):
            s = json.loads(path.read_text(encoding="utf-8"))
            if "$id" in s:
                schema_store[s["$id"]] = s
            schema_store[path.name] = s
            schema_store[path.resolve().as_uri()] = s
        resolver = RefResolver((SCHEMA_DIR / schema_name).resolve().as_uri(), schema, store=schema_store)
        return Draft7Validator(schema, resolver=resolver)


def test_open_thesis_schema_validation_on_fixtures():
    validator = _build_validator("open-thesis.schema.json")

    valid_open = json.loads((FIXTURE_DIR / "valid/open_theses/open_thesis_motor_variability.json").read_text())
    errs = list(validator.iter_errors(valid_open))
    assert errs == [], f"Validation errors on valid open thesis: {errs}"

    partially_bound = json.loads((FIXTURE_DIR / "valid/open_theses/partially_bound_thesis.json").read_text())
    errs = list(validator.iter_errors(partially_bound))
    assert errs == [], f"Validation errors on partially bound thesis: {errs}"

    fully_bound = json.loads((FIXTURE_DIR / "valid/open_theses/fully_bound_thesis.json").read_text())
    errs = list(validator.iter_errors(fully_bound))
    assert errs == [], f"Validation errors on fully bound thesis: {errs}"


def test_open_thesis_creation_with_unbound_variables():
    thesis = {
        "thesis_id": "thesis_open_test_01",
        "hypothesis_template": "Pointer variability correlates with task load, controlling for sensor noise.",
        "investigation_status": "OPEN",
        "open_variables": [
            {"id": "var_a", "role": "predictor", "type": "signal", "status": "UNBOUND", "binding": None, "binding_source": None},
            {"id": "var_b", "role": "outcome", "type": "metric", "status": "UNBOUND", "binding": None, "binding_source": None},
        ],
        "relational_hypotheses": [{"source_var": "var_a", "target_var": "var_b", "relation_type": "CORRELATED"}],
        "required_signals": [],
        "resolution": "DEFERRED_TO_SYNAPSE"
    }
    engine = SinapseBindingEngine()
    # When context is empty, variables remain cleanly UNBOUND
    res = engine.prepare_or_bind(thesis, context={})
    assert res["investigation_status"] == "OPEN"
    assert res["open_variables"][0]["status"] == "UNBOUND"
    assert res["open_variables"][0]["binding"] is None


def test_synapse_deterministic_variable_binding():
    thesis = {
        "thesis_id": "thesis_synapse_binding",
        "hypothesis_template": "Pointer velocity instability is coupled with target acquisition errors.",
        "investigation_status": "OPEN",
        "open_variables": [
            {"id": "pointer_velocity", "role": "predictor", "domain": "motor_control", "status": "UNBOUND", "binding": None, "binding_source": None}
        ],
        "relational_hypotheses": [],
        "required_signals": [],
        "resolution": "DEFERRED_TO_SYNAPSE"
    }
    context = {
        "signals": [
            {"id": "sig_test_pointer_velocity", "domain": "motor_control"}
        ]
    }
    engine = SinapseBindingEngine()
    bound = engine.prepare_or_bind(thesis, context)

    assert bound["investigation_status"] == "BOUND"
    assert bound["open_variables"][0]["status"] == "BOUND"
    assert bound["open_variables"][0]["binding"] == "sig_test_pointer_velocity"
    assert bound["open_variables"][0]["binding_source"] == "SYNAPSE"
    assert "sig_test_pointer_velocity" in bound["required_signals"]


def test_synapse_leaves_variables_unbound_when_evidence_is_insufficient():
    thesis = {
        "thesis_id": "thesis_insufficient_context",
        "hypothesis_template": "Galvanic skin resistance predicts stress in VR environment.",
        "investigation_status": "OPEN",
        "open_variables": [
            {"id": "gsr_sensor", "role": "predictor", "domain": "electrodermal", "status": "UNBOUND", "binding": None, "binding_source": None}
        ],
        "relational_hypotheses": [],
        "required_signals": [],
        "resolution": "DEFERRED_TO_SYNAPSE"
    }
    context = {
        "signals": [
            {"id": "sig_test_pointer_velocity", "domain": "motor_control"}
        ]
    }
    engine = SinapseBindingEngine()
    bound = engine.prepare_or_bind(thesis, context)

    # Must preserve UNBOUND state honestly, without hallucinating a binding
    assert bound["investigation_status"] == "OPEN"
    assert bound["open_variables"][0]["status"] == "UNBOUND"
    assert bound["open_variables"][0]["binding"] is None
    assert bound["open_variables"][0]["binding_source"] is None


def test_synapse_does_not_fabricate_evidence_roots():
    verifier = EvidenceVerifier()
    # A bound thesis with binding_source = "SYNAPSE" has depth > 0, but no empirical derivation roots
    bound_thesis = {
        "question": {
            "id": "q_bound_no_roots",
            "hypothesis": "Pointer velocity variance increases under sustained cognitive load.",
            "required_signals": ["sig_test_pointer_velocity"],
            "open_variables": [
                {"id": "pointer_velocity", "role": "predictor", "status": "BOUND", "binding": "sig_test_pointer_velocity", "binding_source": "SYNAPSE"}
            ],
            "provenance": {
                "derived_from": ["q_parent"],
                "evidence_roots": [], # Zero empirical roots
                "binding_source": "SYNAPSE"
            }
        }
    }
    res = verifier.verify_provenance(bound_thesis)
    # Fundamental rule: BINDING != EVIDENCE. It cannot be certified as DERIVED.
    assert res["eligible_for_derived_status"] is False


def test_epistemic_judge_handles_open_vs_bound_vs_malformed_theses():
    judge = BlindEpistemicJudge()

    # 1. Valid Open Thesis Proposal
    open_prop = {
        "question": {
            "id": "q_open_valid",
            "hypothesis": "Exploring relational space between pointer instability and workload.",
            "investigation_status": "OPEN",
            "open_variables": [{"id": "var_a", "role": "predictor", "status": "UNBOUND"}],
            "required_signals": []
        }
    }
    critic_rev = {"passes_adversarial_check": True, "severity_score": 0.0, "challenges": [], "contradictions": []}
    verifier_rev = {"passes_verification": True, "derivation_depth": 0, "independent_evidence_count": 0, "errors": [], "circularity_detected": False}
    red_rev = {"passes_red_team_check": True, "resistance_to_alternatives": 0.9, "parsimony_score": 1.0, "alternative_hypotheses": []}

    ruling = judge.judge(open_prop, critic_rev, verifier_rev, red_rev)
    assert ruling["decision"] == "ACCEPT"
    assert ruling["assigned_epistemic_status"] == "HYPOTHESIS"
    assert ruling["assigned_epistemic_status"] != "DERIVED"

    # 2. Malformed / Hostile Proposal (Fail-Closed)
    malformed_ruling = judge.judge(None, None, None)
    assert malformed_ruling["decision"] == "REJECT"
    assert malformed_ruling["assigned_epistemic_status"] == "SPECULATION"


def test_dogmatic_pseudo_open_thesis_is_rejected_by_critic():
    engine = SinapseBindingEngine()
    dogmatic_thesis = {
        "thesis_id": "thesis_dogmatic_claim",
        "hypothesis_template": "Testing overreach in open variable.",
        "open_variables": [
            {"id": "var_definitive_cause", "role": "predictor", "description": "This variable is the definitive cause and confirms disorder.", "status": "UNBOUND"}
        ]
    }
    bound = engine.prepare_or_bind(dogmatic_thesis)
    assert bound["investigation_status"] == "REJECTED"
    assert "Dogmatic/overreach" in str(bound.get("binding_error"))


def test_negative_memory_retains_rejected_open_thesis_structures(tmp_path):
    rej_file = tmp_path / "rejected_open_theses.jsonl"
    open_thesis = {
        "proposal_id": "prop_rejected_open_01",
        "question": {
            "hypothesis_template": "Investigation of mouse micro-jitter as a definitive proof of attention deficit.",
            "investigation_status": "OPEN",
            "open_variables": [{"id": "micro_jitter", "role": "predictor", "status": "UNBOUND"}]
        }
    }
    ruling = {"decision": "REJECT", "quarantine_reason": "DIAGNOSTIC_OVERREACH", "epistemic_score": 0.0}
    record_quarantined_claim(open_thesis, ruling, file_path=rej_file)

    # Attempt to re-propose identical or paraphrased open thesis
    repeat_thesis = {
        "proposal_id": "prop_repeat_attempt_02",
        "question": {
            "hypothesis_template": "Investigation of mouse micro-jitter as a definitive proof of attention deficit.",
            "investigation_status": "OPEN",
            "open_variables": [{"id": "micro_jitter", "role": "predictor", "status": "UNBOUND"}]
        }
    }
    res = check_prior_rejections(repeat_thesis, file_path=rej_file)
    assert res["has_prior_rejection"] is True
    assert res["match_type"] == "EXACT_MATCH"
