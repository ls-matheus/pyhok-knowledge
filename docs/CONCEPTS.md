# PyHok Knowledge Concepts

These are the canonical meanings used by the repository.

| Concept | Meaning |
| --- | --- |
| Observation | An occurrence or measurement reported by a source. |
| Signal | A structured representation of an observation, with source, unit, quality, and privacy metadata. |
| Question | A computable investigation contract that names required signals and an evaluation method. |
| Thesis | An open investigation record containing a question, hypothesis, variables, conditions, and provenance. |
| Hypothesis | A falsifiable proposed explanation or relationship; it is never a fact by default. |
| Evidence | An independently attributable result that supports or contradicts a hypothesis. |
| Binding | Assigning a candidate value to a thesis variable for evaluation; binding is not evidence. |
| Relation | A typed connection between knowledge entities. |
| Contradiction | An explicit conflict between claims, signals, or evidence. |
| Gap | A supported absence in the current knowledge structure that warrants investigation. |
| Knowledge | Persisted, versioned content with provenance and epistemic status. |
| Derived | A claim produced from existing entities through a recorded derivation. |
| Validated | A claim that passed the repository's defined validation checks; this is not universal truth. |
| Rejection | A decision not to admit a proposal into the active knowledge state. |
| Quarantine | An isolated hold for unsafe, incomplete, or unresolved material pending review. |
| Exploration Memory | Historical record used to avoid repeating rejected or exhausted investigations. |
| Knowledge Graph | Typed nodes and edges used to query relationships and provenance. |
| Ledger | Append-only, hash-chained record of evolution events. |
| Sinapse | A separate future runtime/interface that activates knowledge context; it is not this repository. |

## Canonical distinctions

- `thesis` is the investigation container; `hypothesis` is its claim.
- `signal` is the repository representation; `observation` is the source event.
- `binding` identifies a value for evaluation; `evidence` changes support.
- `quarantine` is a safety state; `rejection` is a decision.
- `knowledge` is durable state; generated output is disposable process data.
- `ACCEPTED` means admitted as a legitimate investigation, not proven true.
