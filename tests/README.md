# Test Harness

The tests protect the repository's epistemic and operational invariants:

- signal, question, relation, and proposal schemas;
- cross-entity references and conflict detection;
- fail-closed epistemic review and quarantine;
- acyclic provenance in the knowledge graph;
- hash-chained ledger integrity;
- negative/exploration memory;
- checkpoint recovery and graceful shutdown;
- the end-to-end validation pipeline.

Run the complete local harness with:

```bash
bash tools/test_all.sh
```

The suite uses synthetic fixtures only. Passing tests prove that the contracts
and code paths behave as specified; they do not prove that a hypothesis is
true or that synthetic observations represent real people.
