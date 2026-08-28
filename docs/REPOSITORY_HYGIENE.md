# Repository Hygiene

## Version control policy

Keep in Git:

- source code, schemas, prompts, workflows, tests, and concise documentation;
- canonical synthetic fixtures under `data/`;
- the append-only evolution ledger when it is part of the audit trail;
- small reports or release manifests needed to reproduce an audit.

Do not keep in Git:

- `generator/output/` contents (audits, proposals, streams, and per-thesis
  files are regenerable run artifacts);
- Python caches, test caches, temporary files, local checkpoints, and status
  files;
- user telemetry, secrets, API responses, or unreviewed large datasets.

The output directory is intentionally retained only by a `.gitkeep`. Runtime
commands create its subdirectories as needed.

## Data classification

- **Source data:** externally supplied observations, stored outside this
  repository unless explicitly approved and documented.
- **Canonical knowledge:** reviewed entities in `data/`, with schema and
  provenance.
- **Runtime state:** checkpoints, status, and local memory used to resume a
  process.
- **Analysis:** audit and metric reports, normally generated on demand.
- **Generated output:** disposable files produced by the generator or
  continuous engine.

Checked-in examples are synthetic fixtures and must not be described as real
measurements or clinical evidence.

## Working with outputs

Generate or inspect outputs locally with the existing generator and scheduler
commands. Clean them with:

```bash
find generator/output -type f ! -name .gitkeep -delete
find generator/output -type d -empty ! -path generator/output -delete
```

For large real datasets, store them in approved external storage and commit a
manifest containing source, checksum, schema version, and retrieval
instructions. Never replace provenance with a generated filename.

## Validation

Use `bash tools/test_all.sh` for the project harness. The canonical quality
gate is `python3 scheduler/quality_gate.py`; it validates tests, dataset
references, conflicts, proposal contracts, epistemic gates, and whitespace.
