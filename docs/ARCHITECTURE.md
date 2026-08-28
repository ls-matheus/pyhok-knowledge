# PyHok Knowledge Architecture

PyHok Knowledge is the epistemic repository: it stores observations represented
as signals, questions, relations, hypotheses, evidence, provenance, and
evolution history. It does not execute sensors, evaluation methods, policy, or
real-time interventions. Those responsibilities belong to the future Sinapse
runtime.

## System flow

```text
source data
    -> signals and questions
    -> knowledge state
    -> discovery of gaps and contradictions
    -> open thesis
    -> critic / verifier / red-team review
    -> knowledge graph and ledger
    -> exploration memory
    -> next continuous evolution cycle
```

## Repository components

- `data/`: canonical knowledge entities and their metadata. The checked-in
  examples are synthetic fixtures, not clinical or user telemetry.
- `schemas/`: JSON contracts for entities, proposals, releases, and ledger
  records.
- `evolution/discovery/`: finds gaps and opportunities from the current state.
- `evolution/epistemic/`: reviews proposals, preserves uncertainty, and
  quarantines rejected claims.
- `evolution/graph/`: represents entities and typed relationships. Provenance
  edges are acyclic.
- `evolution/ledger.py`: persists the append-only, hash-chained event history.
- `generator/`: builds context and asks an external model for proposals. Its
  files under `generator/output/` are disposable run artifacts.
- `scheduler/`: orchestrates a cycle, checkpoint, recovery, shutdown, and
  quality gates.
- `tests/`: unit and contract coverage for invariants and pipeline behavior.

The graph answers **how entities relate**. The ledger answers **what happened,
when, and with which integrity chain**. They intentionally do not replace one
another.

## Epistemic lifecycle

An observation is represented as a signal. Signals can participate in
relations and questions. Discovery may create an open thesis, which remains a
hypothesis until independent evidence and review justify a stronger status.
Binding a variable only makes an evaluation target explicit; it is not
evidence. `ACCEPT` means that a proposal is admitted for investigation, never
that it is true.

Rejected or unresolved claims remain in negative memory or quarantine so that
future cycles can avoid repeating the same unsupported exploration.

## Sinapse boundary

Sinapse will later consume a versioned knowledge release and evaluate supported
methods locally. This repository must remain interface-independent so that
future clients can query relevant subgraphs without changing the meaning of
the stored knowledge.
