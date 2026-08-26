import json
import sys
from pathlib import Path
import pytest
from jsonschema import Draft7Validator, RefResolver

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA_DIR = ROOT / "schemas" / "v2"
QUESTION_SCHEMA_PATH = SCHEMA_DIR / "question.schema.json"
SIGNAL_SCHEMA_PATH = SCHEMA_DIR / "signal.schema.json"
METHODS_FILE = ROOT / "generator/methods/methods.json"
SIGNALS_DIR = ROOT / "data/signals"
QUESTIONS_DIR = ROOT / "data/questions"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_validator(schema_name: str) -> Draft7Validator:
    schema_path = SCHEMA_DIR / schema_name
    schema = load_json(schema_path)

    schema_store = {}
    for path in SCHEMA_DIR.glob("*.json"):
        s = load_json(path)
        if "$id" in s:
            schema_store[s["$id"]] = s
        schema_store[path.name] = s
        schema_store[path.resolve().as_uri()] = s

    resolver = RefResolver(
        schema_path.resolve().as_uri(),
        schema,
        store=schema_store,
    )
    return Draft7Validator(schema, resolver=resolver)


class SinapseRuntimeQuestion:
    """
    Reference Sinapse Engine Loader & Evaluator for QuestionEntity v2.
    Implements the deterministic evaluation pipeline described in
    PYHOK_MASTER_ARCHITECTURE.md (Sections 10, 11, 17, 18, 19).
    """

    OPERATORS = {
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        "==": lambda a, b: abs(a - b) < 1e-9 if isinstance(a, float) else a == b,
        "!=": lambda a, b: abs(a - b) >= 1e-9 if isinstance(a, float) else a != b,
    }

    def __init__(self, data: dict, signal_registry: dict, method_registry: dict):
        self.validator = build_validator("question.schema.json")
        errors = list(self.validator.iter_errors(data))
        if errors:
            raise ValueError(f"Invalid QuestionEntity schema: {errors[0].message}")

        self.id = data["id"]
        self.hypothesis = data["hypothesis"]
        self.required_signals = data["required_signals"]
        self.evaluation_trigger = data["evaluation_trigger"]
        self.evaluation_model = data["evaluation_model"]
        self.evidence_model = data["evidence_model"]
        self.cortex_weights = data["cortex_weights"]

        # Verify signals
        for sig_id in self.required_signals:
            if sig_id not in signal_registry:
                raise KeyError(f"Signal not registered in Sinapse runtime: {sig_id}")

        for rule in self.evaluation_trigger["rules"]:
            sig_id = rule["signal_id"]
            if sig_id not in signal_registry:
                raise KeyError(f"Trigger signal not registered: {sig_id}")
            if rule["operator"] not in self.OPERATORS:
                raise ValueError(f"Unsupported trigger operator: {rule['operator']}")

        # Verify evaluation method
        method_id = self.evaluation_model["method_id"]
        version = self.evaluation_model["version"]
        if (method_id, version) not in method_registry:
            raise KeyError(f"Evaluation method not supported: {method_id} v{version}")

        self.method_info = method_registry[(method_id, version)]

    def evaluate_trigger(self, signal_values: dict[str, float]) -> bool:
        op = self.evaluation_trigger["logical_operator"]
        rules = self.evaluation_trigger["rules"]
        results = []

        for rule in rules:
            sig_id = rule["signal_id"]
            if sig_id not in signal_values:
                results.append(False)
                continue

            current_val = signal_values[sig_id]
            threshold = rule["threshold"]
            comparator = self.OPERATORS[rule["operator"]]
            results.append(comparator(current_val, threshold))

        if op == "AND":
            return all(results)
        elif op == "OR":
            return any(results)
        return False

    def evaluate_method(self, observation: float, baseline: float = 0.0, std_dev: float = 1.0) -> float:
        """
        Executes the method calculation. For baseline_deviation, returns normalized deviation strength in [0, 1].
        """
        method_id = self.evaluation_model["method_id"]
        if method_id == "method_baseline_deviation":
            if std_dev <= 0:
                std_dev = 1.0
            z_score = abs(observation - baseline) / std_dev
            # Convert z-score to bounded evidence strength [0, 1] using sigmoid-like curve
            evidence_score = min(1.0, z_score / 3.0)
            return evidence_score
        return 0.5

    def compute_evidence(self, method_score: float, signal_quality: float = 1.0) -> float:
        """
        Computes effective evidence: E_tilde = Base_Strength * Method_Score * Signal_Quality
        Preserves the core epistemic rule: Q=0 -> E_tilde=0.
        """
        base = self.evidence_model["base_strength"]
        return max(0.0, min(1.0, base * method_score * signal_quality))

    def compute_decay(self, initial_evidence: float, elapsed_seconds: float) -> float:
        """
        Applies linear temporal decay: E(t) = max(0, E_0 - decay_rate * t)
        """
        decay_rate = self.evidence_model["decay_rate_per_sec"]
        return max(0.0, initial_evidence - (decay_rate * elapsed_seconds))

    def apply_cortex_impact(self, current_cortex: dict[str, float], evidence_strength: float) -> dict[str, float]:
        """
        Calculates cortex dimension updates based on evidence strength and cortex weights.
        """
        updated = {}
        for dim, weight in self.cortex_weights.items():
            current = current_cortex.get(dim, 0.0)
            updated[dim] = max(-1.0, min(1.0, current + (weight * evidence_strength)))
        return updated


@pytest.fixture
def signal_registry():
    registry = {}
    for path in SIGNALS_DIR.glob("*.json"):
        sig = load_json(path)
        registry[sig["id"]] = sig
    return registry


@pytest.fixture
def method_registry():
    catalog = load_json(METHODS_FILE)
    return {
        (m["method_id"], m["version"]): m
        for m in catalog.get("methods", [])
        if m.get("status") == "SUPPORTED"
    }


def test_runtime_loads_and_executes_real_question(signal_registry, method_registry):
    """
    Tests that the real QuestionEntity file generated in data/questions/
    is successfully loaded, validated, and executed by the Sinapse runtime engine.
    """
    question_path = QUESTIONS_DIR / "q_motor_instability_pointer_velocity_deviation.json"
    assert question_path.exists(), "Published question file must exist"

    question_data = load_json(question_path)
    entity = SinapseRuntimeQuestion(question_data, signal_registry, method_registry)

    assert entity.id == "q_motor_instability_pointer_velocity_deviation"
    assert "sig_test_pointer_velocity" in entity.required_signals

    # Case 1: Signal value below threshold (0.5) -> Trigger does not fire
    assert not entity.evaluate_trigger({"sig_test_pointer_velocity": 0.2})

    # Case 2: Signal value above threshold (0.5) -> Trigger fires
    assert entity.evaluate_trigger({"sig_test_pointer_velocity": 1.8})

    # Case 3: Execute method
    score = entity.evaluate_method(observation=2.5, baseline=1.0, std_dev=0.5)
    assert 0.0 <= score <= 1.0

    # Case 4: Evidence computation with full quality (Q=1.0)
    e_full = entity.compute_evidence(method_score=score, signal_quality=1.0)
    assert e_full > 0.0

    # Case 5: Evidence computation with degraded quality (Q=0.0 -> E=0.0)
    e_zero = entity.compute_evidence(method_score=score, signal_quality=0.0)
    assert e_zero == 0.0

    # Case 6: Temporal decay after 5 seconds
    e_decayed = entity.compute_decay(initial_evidence=0.8, elapsed_seconds=5.0)
    assert e_decayed == 0.8 - (0.1 * 5.0)  # 0.3

    # Case 7: Cortex state impact
    initial_cortex = {"focus": 0.0, "stress": 0.0, "autonomy": 0.0, "fatigue": 0.0}
    updated_cortex = entity.apply_cortex_impact(initial_cortex, evidence_strength=0.8)
    assert updated_cortex["stress"] > 0.0
    assert updated_cortex["fatigue"] > 0.0


# ----------------------------------------------------------------------
# Rigorous Negative Tests (FASE 6: 10 distinct negative integration cases)
# ----------------------------------------------------------------------

def test_runtime_rejects_domain_in_question(signal_registry, method_registry):
    data = load_json(QUESTIONS_DIR / "q_motor_instability_pointer_velocity_deviation.json")
    data["domain"] = "motor_instability"
    with pytest.raises(ValueError, match="domain"):
        SinapseRuntimeQuestion(data, signal_registry, method_registry)


def test_runtime_rejects_description_in_question(signal_registry, method_registry):
    data = load_json(QUESTIONS_DIR / "q_motor_instability_pointer_velocity_deviation.json")
    data["description"] = "Test description"
    with pytest.raises(ValueError, match="description"):
        SinapseRuntimeQuestion(data, signal_registry, method_registry)


def test_runtime_rejects_invalid_operator(signal_registry, method_registry):
    data = load_json(QUESTIONS_DIR / "q_motor_instability_pointer_velocity_deviation.json")
    data["evaluation_trigger"]["rules"][0]["operator"] = "GREATER_THAN"
    with pytest.raises(ValueError):
        SinapseRuntimeQuestion(data, signal_registry, method_registry)


def test_runtime_rejects_unknown_method(signal_registry, method_registry):
    data = load_json(QUESTIONS_DIR / "q_motor_instability_pointer_velocity_deviation.json")
    data["evaluation_model"]["method_id"] = "method_nonexistent"
    with pytest.raises(KeyError, match="Evaluation method not supported"):
        SinapseRuntimeQuestion(data, signal_registry, method_registry)


def test_runtime_rejects_unknown_method_version(signal_registry, method_registry):
    data = load_json(QUESTIONS_DIR / "q_motor_instability_pointer_velocity_deviation.json")
    data["evaluation_model"]["version"] = "99.9.9"
    with pytest.raises(KeyError, match="Evaluation method not supported"):
        SinapseRuntimeQuestion(data, signal_registry, method_registry)


def test_runtime_rejects_unknown_signal(signal_registry, method_registry):
    data = load_json(QUESTIONS_DIR / "q_motor_instability_pointer_velocity_deviation.json")
    data["required_signals"] = ["sig_unknown_test_signal"]
    with pytest.raises(KeyError, match="Signal not registered"):
        SinapseRuntimeQuestion(data, signal_registry, method_registry)


def test_runtime_rejects_invalid_window_ms(signal_registry, method_registry):
    data = load_json(QUESTIONS_DIR / "q_motor_instability_pointer_velocity_deviation.json")
    data["evaluation_trigger"]["rules"][0]["window_ms"] = 0
    with pytest.raises(ValueError):
        SinapseRuntimeQuestion(data, signal_registry, method_registry)


def test_runtime_rejects_out_of_range_cortex_weights(signal_registry, method_registry):
    data = load_json(QUESTIONS_DIR / "q_motor_instability_pointer_velocity_deviation.json")
    data["cortex_weights"]["stress"] = 2.5
    with pytest.raises(ValueError):
        SinapseRuntimeQuestion(data, signal_registry, method_registry)


def test_runtime_rejects_missing_required_field(signal_registry, method_registry):
    data = load_json(QUESTIONS_DIR / "q_motor_instability_pointer_velocity_deviation.json")
    del data["evaluation_model"]
    with pytest.raises(ValueError):
        SinapseRuntimeQuestion(data, signal_registry, method_registry)


def test_runtime_rejects_unknown_unexpected_properties(signal_registry, method_registry):
    data = load_json(QUESTIONS_DIR / "q_motor_instability_pointer_velocity_deviation.json")
    data["unexpected_property_xyz"] = 123
    with pytest.raises(ValueError, match="unexpected_property_xyz"):
        SinapseRuntimeQuestion(data, signal_registry, method_registry)
