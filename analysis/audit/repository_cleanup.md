# Repository Cleanup Audit

## 1. State before cleanup

The repository was a Python knowledge/evolution core with 55 tracked Python,
schema, documentation, workflow, and test files, plus more than 5,400 tracked
files under `generator/output/`. The largest generated artifacts were
`evolution/rejected_claims.jsonl` (about 20 MB), thesis streams (about 10 MB
each), and per-thesis JSON files. The source architecture already separated
data, discovery, epistemic review, graph, ledger, generator, scheduler, and
tests.

## 2. Problems found

- Regenerable generator outputs were versioned as thousands of individual
  files and multi-megabyte streams.
- The output policy was implicit and inconsistent with the repository's
  source/data boundary.
- `load_knowledge_state()` omitted the `open_theses` collection, then silently
  swallowed the resulting `KeyError`; persisted theses were therefore invisible
  to discovery and state hashing.
- Documentation described the broad boundary but did not provide a concise
  canonical architecture, concept glossary, or hygiene policy.
- Existing synthetic examples were not clearly labelled in onboarding
  documentation.

## 3. Files removed

All tracked contents of `generator/output/` were removed because they are
regenerable process artifacts, not canonical knowledge or audit history. No
files under `data/`, `schemas/`, `evolution/`, `scheduler/`, or `tests/` were
discarded.

## 4. Files moved

None. The current source layout already follows responsibility boundaries; a
large directory move would add churn without improving imports or ownership.

## 5. Files consolidated

Output storage is consolidated conceptually under the ignored
`generator/output/` runtime directory. The durable distinction is now:
canonical data in `data/`, runtime state in scheduler/evolution state files,
and generated analysis/output outside Git.

## 6. Concepts corrected

The canonical glossary now distinguishes thesis/hypothesis, signal/observation,
binding/evidence, rejection/quarantine, graph/ledger, and knowledge/generated
output. Acceptance is explicitly not truth.

## 7. Legacy identified

The generated thesis snapshots and per-thesis filename history are legacy
artifacts of an earlier publication strategy. They are not source modules and
are safe to regenerate. No source module was classified as safely deletable
without stronger evidence.

## 8. Code maintained and why

The discovery engine, epistemic firewall, graph, ledger, scheduler, validators,
schemas, prompts, workflows, and tests remain because they implement or guard
the current pipeline. The ledger and rejected-claim memory remain because they
provide auditability and anti-repetition behavior.

## 9. Data preserved

Canonical signals, questions, relations, schemas, mission policy, ledger, and
rejected-claim history were preserved. They are structured knowledge or
provenance, not disposable output.

## 10. Data discarded

Only regenerable generator outputs were discarded. They can be recreated from
the checked-in source data, prompts, and runtime configuration. No user
telemetry or real-world evidence is present in the checked-in examples.

## 11. Architecture changes

`evolution/ledger.py` now initializes `open_theses` before loading thesis
files, preventing silent loss of thesis state. `.gitignore` marks generator
outputs as ephemeral while retaining the directory placeholder.

## 12. Tests executed

The targeted ledger regression covers thesis loading. The full suite and
quality gate are run during validation of this change.

## 13. Quality gates

Required gates: pytest, dataset validation, conflict validation, proposal
validation, measurement and epistemic gates, continuous-discovery gate, and
`git diff --check`.

## 14. Remaining risks

The continuous workflow intentionally publishes runtime state from CI; its
retention policy should be reviewed separately if long-term history becomes
large. Some legacy naming remains in compatibility APIs and should only be
renamed with a migration plan.

## 15. Next steps

Add a reviewed release manifest for any future external dataset, monitor output
size in CI, and keep the Sinapse implementation in its separate repository.
