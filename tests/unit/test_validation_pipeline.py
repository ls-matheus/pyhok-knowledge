import json
import sys
from pathlib import Path
import pytest
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validators.publish_proposal import build_question_entity, load_supported_methods
from validators.validate_proposal import validate_question_create
QUESTION_SCHEMA_PATH = ROOT / "schemas/v2/question.schema.json"
METHODS_FILE = ROOT / "generator/methods/methods.json"
SIGNALS_DIR = ROOT / "data/signals"
QUESTIONS_DIR = ROOT / "data/questions"
MISSION_FILE = ROOT / "mission/mission.json"
POLICY_FILE = ROOT / "evolution/evolution-policy.json"


@pytest.fixture
def question_schema():
    return json.loads(QUESTION_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def valid_question_data():
    return {
        "id": "q_motor_instability_pointer_velocity_deviation",
        "hypothesis": "Existe variação mensurável na velocidade do ponteiro em relação à linha de base individual que reflete instabilidade motora.",
        "required_signals": [
            "sig_test_pointer_velocity"
        ],
        "evaluation_trigger": {
            "logical_operator": "AND",
            "rules": [
                {
                    "signal_id": "sig_test_pointer_velocity",
                    "operator": ">",
                    "threshold": 1.5,
                    "window_ms": 1000
                }
            ]
        },
        "evaluation_model": {
            "method_id": "method_baseline_deviation",
            "version": "1.0.0",
            "parameters": {}
        },
        "evidence_model": {
            "base_strength": 0.8,
            "decay_rate_per_sec": 0.1
        },
        "cortex_weights": {
            "focus": 0.2,
            "stress": 0.3,
            "autonomy": 0.1,
            "fatigue": 0.4
        }
    }


@pytest.fixture
def valid_proposal_data():
    return {
        "proposal_id": "prop_opp_motor_instability_baseline_deviation",
        "operation": "QUESTION_CREATE",
        "opportunity_id": "opp_motor_instability_baseline_deviation",
        "domain": "motor_instability",
        "question": {
            "question_id": "q_motor_instability_pointer_velocity_deviation",
            "description": "Há desvio significativo na velocidade do ponteiro em relação à linha de base individual?",
            "signal_ids": [
                "sig_test_pointer_velocity"
            ],
            "method_ids": [
                "method_baseline_deviation"
            ],
            "id": "q_motor_instability_pointer_velocity_deviation",
            "hypothesis": "Existe variação mensurável na velocidade do ponteiro em relação à linha de base individual.",
            "required_signals": [
                "sig_test_pointer_velocity"
            ],
            "evaluation_trigger": {
                "logical_operator": "AND",
                "rules": [
                    {
                        "signal_id": "sig_test_pointer_velocity",
                        "operator": ">",
                        "threshold": 1.5,
                        "window_ms": 1000
                    }
                ]
            },
            "evaluation_model": {
                "method_id": "method_baseline_deviation",
                "version": "1.0.0",
                "parameters": {}
            },
            "evidence_model": {
                "base_strength": 0.8,
                "decay_rate_per_sec": 0.1
            },
            "cortex_weights": {
                "focus": 0.2,
                "stress": 0.3,
                "autonomy": 0.1,
                "fatigue": 0.4
            }
        },
        "rationale": "A oportunidade permite expandir a cobertura no domínio motor sem hipóteses clínicas.",
        "novelty_justification": "Representa a primeira hipótese observacional no domínio motor_instability.",
        "computability_justification": "Utiliza estritamente o sinal e método suportados no repositório.",
        "individuality_justification": "Prioriza desvio relativo à linha de base individual.",
        "uncertainty_justification": "Preserva a incerteza probabilística da observação.",
        "evidence_basis": {
            "signals": [
                "sig_test_pointer_velocity"
            ],
            "methods": [
                "method_baseline_deviation"
            ]
        },
        "confidence": 0.9
    }


def test_question_schema_validates_canonical_question(question_schema, valid_question_data):
    errors = list(Draft7Validator(question_schema).iter_errors(valid_question_data))
    assert errors == []


def test_question_schema_rejects_domain(question_schema, valid_question_data):
    invalid = dict(valid_question_data)
    invalid["domain"] = "motor_instability"
    errors = list(Draft7Validator(question_schema).iter_errors(invalid))
    assert len(errors) > 0
    assert any("domain" in str(e.message) for e in errors)


def test_question_schema_rejects_description(question_schema, valid_question_data):
    invalid = dict(valid_question_data)
    invalid["description"] = "Texto de proposta"
    errors = list(Draft7Validator(question_schema).iter_errors(invalid))
    assert len(errors) > 0
    assert any("description" in str(e.message) for e in errors)


def test_question_schema_rejects_invalid_operator(question_schema, valid_question_data):
    invalid = json.loads(json.dumps(valid_question_data))
    invalid["evaluation_trigger"]["rules"][0]["operator"] = "GREATER_THAN"
    errors = list(Draft7Validator(question_schema).iter_errors(invalid))
    assert len(errors) > 0
    assert any("GREATER_THAN" in str(e.message) for e in errors)


def test_question_schema_rejects_missing_evaluation_model(question_schema, valid_question_data):
    invalid = dict(valid_question_data)
    del invalid["evaluation_model"]
    errors = list(Draft7Validator(question_schema).iter_errors(invalid))
    assert len(errors) > 0


def test_question_schema_rejects_out_of_range_cortex_weights(question_schema, valid_question_data):
    invalid = json.loads(json.dumps(valid_question_data))
    invalid["cortex_weights"]["stress"] = 1.5
    errors = list(Draft7Validator(question_schema).iter_errors(invalid))
    assert len(errors) > 0


def test_publish_proposal_materializes_canonical_question(valid_proposal_data):
    supported = load_supported_methods()
    question_entity = build_question_entity(valid_proposal_data, supported)

    assert "domain" not in question_entity
    assert "description" not in question_entity
    assert "rationale" not in question_entity
    assert "evidence_basis" not in question_entity
    assert "confidence" not in question_entity

    assert question_entity["id"] == "q_motor_instability_pointer_velocity_deviation"
    assert question_entity["hypothesis"] == valid_proposal_data["question"]["hypothesis"]
    assert question_entity["required_signals"] == ["sig_test_pointer_velocity"]
    assert question_entity["evaluation_model"]["method_id"] == "method_baseline_deviation"
    assert question_entity["evaluation_model"]["version"] == "1.0.0"


def test_publish_proposal_normalizes_operator(valid_proposal_data):
    proposal = json.loads(json.dumps(valid_proposal_data))
    proposal["question"]["evaluation_trigger"]["rules"][0]["operator"] = "GREATER_THAN"

    supported = load_supported_methods()
    question_entity = build_question_entity(proposal, supported)
    assert question_entity["evaluation_trigger"]["rules"][0]["operator"] == ">"


def test_publish_proposal_rejects_evidence_mismatch(valid_proposal_data):
    proposal = json.loads(json.dumps(valid_proposal_data))
    proposal["evidence_basis"]["signals"] = ["sig_other_signal"]

    supported = load_supported_methods()
    with pytest.raises(SystemExit) as exc:
        build_question_entity(proposal, supported)
    assert "Evidence signals do not match" in str(exc.value)


def test_validate_proposal_approves_valid(valid_proposal_data):
    mission = json.loads(MISSION_FILE.read_text(encoding="utf-8"))
    policy = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    methods = json.loads(METHODS_FILE.read_text(encoding="utf-8"))
    known_signals = {"sig_test_pointer_velocity"}
    known_questions = set()

    errors = validate_question_create(
        proposal=valid_proposal_data,
        mission=mission,
        policy=policy,
        methods=methods,
        known_signals=known_signals,
        known_questions=known_questions,
    )
    assert errors == []


def test_validate_proposal_rejects_diagnostic_language(valid_proposal_data):
    proposal = json.loads(json.dumps(valid_proposal_data))
    proposal["question"]["hypothesis"] = "A criança tem clinical diagnosis de instabilidade."

    mission = json.loads(MISSION_FILE.read_text(encoding="utf-8"))
    policy = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    methods = json.loads(METHODS_FILE.read_text(encoding="utf-8"))
    known_signals = {"sig_test_pointer_velocity"}
    known_questions = set()

    errors = validate_question_create(
        proposal=proposal,
        mission=mission,
        policy=policy,
        methods=methods,
        known_signals=known_signals,
        known_questions=known_questions,
    )
    assert len(errors) > 0
    assert any("Forbidden diagnostic language" in e for e in errors)
