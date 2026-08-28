# PyHok Knowledge

PyHok Knowledge is the versioned, hypothesis-driven **brain** of the PyHok
ecosystem. It stores structured signals, questions, relations, open theses,
evidence, provenance, and evolution history.

It is not a diagnostic system, a telemetry store, a chatbot, or a real-time
runtime. The future **Sinapse** application will be a separate interface and
deterministic engine that queries this repository and evaluates supported
methods locally.

## How knowledge evolves

```text
data -> signals -> knowledge state -> discovery -> open thesis
     -> epistemic review -> graph + ledger + memory -> next cycle
```

- A **thesis** is an investigation container, not an answer.
- A **hypothesis** remains a hypothesis until evidence and review justify a
  stronger status.
- **Binding** a variable selects an evaluation target; it is not evidence.
- `ACCEPTED` means admitted for investigation, never proven true.

The agent may propose questions, relations, and signal requirements. It cannot
execute runtime capabilities, alter policy, or publish without validation.

## Where things live

- `data/` — canonical synthetic examples of signals, questions, and relations.
- `schemas/` — JSON contracts.
- `evolution/` — discovery, epistemic review, graph, ledger, and memory.
- `generator/` — context building and proposal generation.
- `scheduler/` — continuous orchestration, checkpoints, and quality gates.
- `tests/` — unit and contract tests.
- `docs/` — [architecture](docs/ARCHITECTURE.md), [concepts](docs/CONCEPTS.md),
  and [hygiene](docs/REPOSITORY_HYGIENE.md).
- `generator/output/` — local, ignored, regenerable run artifacts.

The graph answers how entities relate. The hash-chained ledger answers what
happened and when.

## Run and test

Requires Python 3.10+ and dependencies from `requirements-dev.txt`.

```bash
python3 -m pytest -v
python3 scheduler/quality_gate.py
bash tools/test_all.sh
```

Generator and continuous-engine commands write to the ignored
`generator/output/` directory. Do not interpret generated volume as learned
knowledge; inspect epistemic status, evidence, provenance, and validation
results instead.

## Sinapse boundary

Sinapse will later acquire signals, execute evaluation methods, calculate
evidence and uncertainty, and present contextual support. This repository only
defines the knowledge and contracts it may consume; it never executes those
methods.
