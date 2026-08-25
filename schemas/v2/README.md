# PyHok Dataset Schema v2

Schema version: 2.0.0

## Design Principles

The schema layer is intentionally extensible.

The repository does not assume a fixed future catalog of sensors,
input devices, feature-extraction methods, or observation sources.

### Core contracts

- `SignalDefinition` — describes an observable.
- `FeatureMethod` — describes a transformation/feature-extraction method.
- `QuestionEntity` — describes an observational hypothesis.
- `Relation` — describes graph relationships between hypotheses.
- `SignalValue` — describes a runtime observation and its quality state.
- `DatasetRelease` — describes an immutable versioned release.

### Extensibility rule

New sensor types, sources, data types, feature methods, and derived
signals should be introduced through new definitions rather than by
changing the core architecture whenever possible.

### Responsibility boundaries

Dataset:
- describes observables;
- describes hypotheses;
- describes relationships;
- declares algorithm identifiers and parameters.

Sinapse:
- implements transformations;
- evaluates signals;
- calculates evidence;
- performs fusion;
- executes policy.

The Dataset never directly executes native behavior.
