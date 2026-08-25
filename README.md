# PyHok Knowledge

Declarative, versioned, hypothesis-driven knowledge repository for PyHok / Sinapse.

## Responsibility Boundary

### PyHok Knowledge

Defines:

- SignalDefinitions
- QuestionEntities
- Relations
- EvaluationMethod contracts
- Dataset releases
- Agent proposals
- Validation and publication rules

### Sinapse

Implements:

- signal acquisition
- normalization
- feature extraction
- evaluation methods
- baseline calculation
- evidence calculation
- evidence fusion
- state estimation
- confidence / uncertainty
- geometric projection
- policy execution

The Knowledge Repository NEVER executes evaluation methods.

It only references methods by stable identifiers and versions.

## Agent Authority

The Agent Generator may:

- propose new questions
- propose relations
- propose signal requirements

The Agent may NOT:

- execute native capabilities
- modify the Sinapse implementation
- modify Policy logic
- publish without validation

## Publication Pipeline

Agent
→ Proposal
→ Schema Validation
→ Reference Validation
→ Method Compatibility Check
→ Duplicate Check
→ Conflict Check
→ Release
→ Git

## Evolution

The Knowledge Dataset may evolve independently from the Sinapse engine.

A new method can only be used by a QuestionEntity when the target
Sinapse release declares that method/version as supported.
