# PYHOK KNOWLEDGE — CURRENT KNOWLEDGE CONTEXT

Version: 1.0.0
Status: GENERATED
Role: Authoritative snapshot of the current repository knowledge state

## 1. PURPOSE

The Current Knowledge Context answers exactly one question:

What knowledge and computational capabilities exist in the repository right now?

It is the factual snapshot consumed by the PyHok Knowledge Evolution Agent.

It does NOT define:

- what PyHok is;
- how the agent should reason;
- what the agent is authorized to change;
- what the product should become;
- what knowledge exists outside the repository.

Those responsibilities belong to the other architectural layers.

The four layers are strictly separated:

1. MASTER DOCUMENT
   What PyHok is.

2. AGENT CONSTITUTION
   How the agent must think.

3. CURRENT KNOWLEDGE CONTEXT
   What actually exists now.

4. EVOLUTION POLICY
   What the agent is authorized to do.

These layers MUST NOT be conflated.

## 2. SOURCE OF TRUTH

The Current Knowledge Context MUST be generated from the actual repository state.

It MUST NOT be invented by the LLM.

Authoritative sources include, when present:

- MissionDefinition;
- SignalDefinition catalog;
- QuestionEntity catalog;
- RelationGraph;
- EvaluationMethod catalog;
- applicable schemas;
- repository metadata;
- released knowledge datasets.

The context must represent the repository as it actually exists.

## 3. UNKNOWN RULE

Anything not explicitly present in the Current Knowledge Context MUST be treated as UNKNOWN.

UNKNOWN does not mean:

- probably exists;
- implied by the Master Document;
- common in similar systems;
- supported by external knowledge;
- available in the runtime;
- safe to assume.

The agent MUST NOT invent missing entities.

Missing signal = UNKNOWN.
Missing question = UNKNOWN.
Missing relation = UNKNOWN.
Missing method = UNKNOWN.
Missing runtime capability = UNKNOWN.

UNKNOWN MUST NOT be converted into a proposal.

## 4. REPOSITORY SNAPSHOT

Every generated context SHOULD identify the repository state from which it was produced.

Recommended fields:

- repository;
- commit;
- generated_at;
- context_version.

The commit identifies the exact repository state analyzed.

The context MUST NOT claim to represent another commit.

## 5. MISSION REFERENCE

The context MAY include the active machine-readable MissionDefinition.

This is a factual reference to the mission currently configured in the repository.

It must not replace the Master Document.

The Master Document provides the conceptual and architectural understanding of PyHok.

The Current Knowledge Context provides the concrete repository state.

If the repository state differs from an older document, the current repository state is authoritative for machine-readable evolution analysis.

## 6. SIGNAL CATALOG

The context MUST contain every signal currently available to the knowledge graph.

When defined by the repository, preserve:

- signal ID;
- signal kind;
- source;
- data type;
- unit;
- temporal window;
- quality metric;
- minimum acceptable quality;
- privacy classification;
- retention policy;
- raw/derived classification.

The existence of a signal does NOT imply a psychological, neurological or clinical interpretation.

Do not add interpretations that are not explicitly defined by the repository.

## 7. QUESTION CATALOG

The context MUST contain every QuestionEntity currently present.

When available, preserve:

- question ID;
- status;
- version;
- domain;
- conceptual target;
- required signals;
- evaluation method;
- temporal requirements;
- baseline relationship;
- evidence role;
- confidence requirements;
- existing relations;
- structured metadata.

The complete question catalog MUST be available to the reasoning process.

A candidate question cannot be considered novel merely because it has:

- different wording;
- a different identifier;
- a slightly different threshold;
- a slightly different temporal window.

Novelty must be evaluated against the actual existing question semantics.

## 8. RELATION GRAPH

The context MUST contain the current relation graph.

Each relation SHOULD preserve:

- source entity;
- target entity;
- relation type;
- status;
- justification or metadata when available.

Supported relation types are determined by the actual repository schema and policy.

The agent must reason over the graph as a structure.

It should inspect:

- missing meaningful relations;
- reinforcement;
- contradiction;
- prerequisite relationships;
- supersession;
- isolated nodes;
- weakly connected regions;
- redundant structures.

A relation MUST NOT be assumed merely because two entities belong to the same domain.

## 9. EVALUATION METHOD CATALOG

The context MUST contain the complete currently supported evaluation method catalog.

When available, preserve:

- method ID;
- version;
- status;
- description;
- engine contract;
- required parameters;
- supported input types.

Only methods explicitly supported by the repository may be used when proposing new computational questions.

If a method is absent or unsupported:

DO NOT USE IT.

The agent MUST NOT invent a new evaluation method.

## 10. SCHEMA STATE

The context SHOULD expose the relevant schema versions governing:

- signals;
- questions;
- relations;
- proposals;
- releases.

The schemas define structural validity.

The agent MUST NOT assume fields or structures that are unsupported by the current schema.

## 11. RELEASE STATE

If releases exist, the context MAY include factual release information such as:

- latest release identifier;
- latest dataset version;
- release timestamp;
- included knowledge version;
- checksum or integrity metadata.

Released knowledge and working-tree knowledge MUST NOT be confused.

## 12. GRAPH SUMMARY

The generator SHOULD produce factual structural summaries such as:

- signal_count;
- question_count;
- relation_count;
- supported_method_count;
- domains_with_questions;
- domains_without_questions;
- isolated_nodes;
- connected_components.

These summaries are convenience information only.

The underlying catalogs remain authoritative.

A summary MUST NOT override the actual entity lists.

## 13. DERIVED STRUCTURAL INFORMATION

The context generator MAY calculate structural facts such as:

- questions per domain;
- questions per signal;
- questions per method;
- isolated graph nodes;
- connected components;
- relation density;
- unsupported references;
- duplicate identifiers;
- orphaned entities.

Derived structural information MUST be calculated programmatically.

The LLM MUST NOT fabricate these statistics.

## 14. FACTS VS INTERPRETATION

The Current Knowledge Context must remain factual.

VALID:

A signal exists with a defined source, type and unit.

INVALID:

A signal represents anxiety.

The second statement is an interpretation and must not be inserted unless the repository explicitly defines that relationship.

The context is the factual substrate on which reasoning occurs.

## 15. NO EXTERNAL KNOWLEDGE

The Current Knowledge Context MUST NOT silently incorporate:

- internet research;
- clinical literature;
- assumptions about neurodevelopment;
- assumptions about human behavior;
- assumptions about sensors;
- assumptions about hardware;
- assumptions about runtime capabilities.

External information is not part of the current repository state unless it is explicitly incorporated through an authorized repository change.

## 16. SNAPSHOT CONSISTENCY

All entities in a context snapshot SHOULD correspond to one coherent repository state.

The generator MUST avoid mixing:

- questions from one commit;
- methods from another state;
- relations from another state;
- mission definitions from an unrelated version.

A context represents one analyzable repository state.

## 17. GENERATION PIPELINE

The recommended generation sequence is:

REPOSITORY
    ->
READ AUTHORITATIVE FILES
    ->
VALIDATE STRUCTURE
    ->
BUILD CURRENT KNOWLEDGE CONTEXT
    ->
CALCULATE STRUCTURAL SUMMARY
    ->
WRITE agent_context.json
    ->
AGENT AUDITOR
    ->
PROPOSAL GENERATOR
    ->
VALIDATION

The LLM consumes the generated context.

The LLM is NOT responsible for discovering repository structure manually.

## 18. IMMUTABILITY DURING ANALYSIS

Once generated for an agent run, the Current Knowledge Context represents the input state for that run.

The agent MUST NOT modify the context while reasoning.

If the repository changes, a new context snapshot should be generated before the next analysis.

## 19. VALIDATION

The Current Knowledge Context assists reasoning.

It does NOT replace validation.

Every generated proposal MUST be independently validated against the actual repository.

Validation MUST verify, as applicable:

- referenced signals exist;
- referenced methods exist;
- referenced questions exist when required;
- identifiers satisfy schemas;
- relations reference valid entities;
- proposal type is allowed;
- mission alignment is preserved;
- graph consistency is preserved;
- structured justification is present.

The validator is authoritative for acceptance.

## 20. SEPARATION OF THE FOUR LAYERS

The architecture MUST preserve the following separation:

MASTER DOCUMENT
=
WHAT PYHOK IS

AGENT CONSTITUTION
=
HOW THE AGENT MUST THINK

CURRENT KNOWLEDGE CONTEXT
=
WHAT ACTUALLY EXISTS NOW

EVOLUTION POLICY
=
WHAT THE AGENT IS AUTHORIZED TO DO

No layer may silently replace another.

## 21. CORE PRINCIPLE

The Current Knowledge Context is a mirror of the repository.

It must describe the repository:

- as it is;
- with its current entities;
- with its current methods;
- with its current relations;
- with its current schemas;
- with its current limitations.

Not as it should be.

Not as the agent wishes it to be.

Not as the Master Document imagines it to be.

Not as external knowledge suggests it could be.

The agent reasons over the mirror.

The validators determine whether a proposed evolution is actually valid.

## 22. FINAL RULE

If the agent cannot find factual support for a claim inside the Current Knowledge Context, it MUST treat that claim as UNKNOWN.

UNKNOWN MUST NOT become a proposal.

A proposal requires factual support in the current repository state.
