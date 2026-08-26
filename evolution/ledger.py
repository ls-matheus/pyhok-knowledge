from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[1]
LEDGER_SCHEMA_FILE = ROOT / "evolution/ledger.schema.json"
LEDGER_FILE = ROOT / "evolution/ledger.jsonl"
DATA_DIR = ROOT / "data"

_schema_cache: dict[str, Any] | None = None


def get_ledger_schema() -> dict[str, Any]:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(LEDGER_SCHEMA_FILE.read_text(encoding="utf-8"))
    return _schema_cache


def canonical_json_dumps(obj: Any) -> str:
    """
    Produces deterministic, canonical JSON string with sorted keys and compact separators.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_sha256(data: Any) -> str:
    """
    Computes deterministic SHA-256 hash for any serializable Python structure or string.
    Returns format: 'sha256:<hex>'
    """
    if isinstance(data, str):
        payload = data.encode("utf-8")
    elif isinstance(data, bytes):
        payload = data
    else:
        payload = canonical_json_dumps(data).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"sha256:{digest}"


def load_knowledge_state(data_dir: Path = DATA_DIR) -> dict[str, Any]:
    """
    Loads full structured knowledge state from data directory.
    """
    extracted_state: dict[str, Any] = {
        "signals": [],
        "questions": [],
        "relations": []
    }

    signals_dir = data_dir / "signals"
    if signals_dir.exists():
        for path in sorted(signals_dir.glob("*.json")):
            try:
                extracted_state["signals"].append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass

    questions_dir = data_dir / "questions"
    if questions_dir.exists():
        for path in sorted(questions_dir.glob("*.json")):
            try:
                extracted_state["questions"].append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass

    relations_dir = data_dir / "relations"
    if relations_dir.exists():
        for path in sorted(relations_dir.glob("*.json")):
            try:
                extracted_state["relations"].append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass

    return extracted_state


def hash_knowledge_state(state_data: dict[str, Any] | None = None, data_dir: Path = DATA_DIR) -> str:
    """
    Computes a canonical SHA-256 hash of the entire knowledge dataset state.
    """
    if state_data is not None:
        return compute_sha256(state_data)

    extracted_state = load_knowledge_state(data_dir)
    return compute_sha256(extracted_state)


def hash_proposal(proposal_data: dict[str, Any]) -> str:
    """
    Computes a canonical SHA-256 hash of a proposal.
    """
    return compute_sha256(proposal_data)


def read_ledger_events(ledger_path: Path = LEDGER_FILE) -> list[dict[str, Any]]:
    """
    Reads all events from the append-only ledger JSONL file.
    """
    if not ledger_path.exists():
        return []
    events = []
    for line in ledger_path.read_text(encoding="utf-8").strip().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def append_ledger_event(
    event_data: dict[str, Any],
    ledger_path: Path = LEDGER_FILE
) -> dict[str, Any]:
    """
    Appends an immutable event to the Evolution Ledger after chaining previous hash and validating schema.
    """
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    existing_events = read_ledger_events(ledger_path)

    # 1. Check for duplicate cycle_id
    cycle_id = event_data.get("cycle_id")
    for prev in existing_events:
        if prev.get("cycle_id") == cycle_id:
            raise ValueError(f"Duplicate cycle_id '{cycle_id}' in ledger")

    # 2. Hash chaining: set previous_event_hash
    event_copy = dict(event_data)
    if existing_events:
        event_copy["previous_event_hash"] = compute_sha256(existing_events[-1])
    else:
        event_copy["previous_event_hash"] = None

    # 3. Validate against canonical ledger schema
    schema = get_ledger_schema()
    validator = Draft7Validator(schema)
    errors = list(validator.iter_errors(event_copy))
    if errors:
        msg = "; ".join(e.message for e in errors)
        raise ValueError(f"Ledger event failed schema validation: {msg}")

    # 4. Atomic append to JSONL file
    line_str = canonical_json_dumps(event_copy) + "\n"
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(line_str)

    return event_copy


def verify_ledger_integrity(ledger_path: Path = LEDGER_FILE) -> tuple[bool, list[str]]:
    """
    Verifies cryptographic hash chaining and schema compliance across all events in the ledger.
    """
    if not ledger_path.exists():
        return True, []

    events = read_ledger_events(ledger_path)
    if not events:
        return True, []

    schema = get_ledger_schema()
    validator = Draft7Validator(schema)
    errors: list[str] = []
    seen_cycle_ids: set[str] = set()

    for idx, event in enumerate(events):
        # 1. Schema check
        schema_errors = list(validator.iter_errors(event))
        if schema_errors:
            errors.append(f"Event {idx} schema error: {schema_errors[0].message}")

        # 2. Duplicate cycle_id check
        cid = event.get("cycle_id")
        if cid in seen_cycle_ids:
            errors.append(f"Event {idx} duplicate cycle_id: {cid}")
        seen_cycle_ids.add(cid)

        # 3. Hash chain verification
        if idx == 0:
            if event.get("previous_event_hash") is not None:
                errors.append(f"First event must have previous_event_hash=null, got {event.get('previous_event_hash')}")
        else:
            prev_event = events[idx - 1]
            expected_hash = compute_sha256(prev_event)
            actual_prev_hash = event.get("previous_event_hash")
            if actual_prev_hash != expected_hash:
                errors.append(
                    f"Hash chain broken at event {idx} ({cid}): "
                    f"expected previous_event_hash={expected_hash}, got {actual_prev_hash}"
                )

    return len(errors) == 0, errors
