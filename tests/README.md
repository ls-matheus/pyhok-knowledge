# PyHok Knowledge Test Harness

The test harness validates the separation between:

1. Signal definitions
2. Feature methods
3. Questions / hypotheses
4. Relations
5. AI-generated proposals
6. Cross-entity references

## Test flow

```text
AI / Generator
      ↓
Proposal JSON
      ↓
Proposal validation
      ↓
Schema validation
      ↓
Cross-reference validation
      ↓
Conflict validation
      ↓
Release build


Depois execute:

```bash
git add .
git commit -m "feat: add AI proposal test harness"
git push

mkdir -p schemas dataset/releases dataset/signals dataset/questions dataset/relations tests/fixtures/valid tests/fixtures/invalid tests/unit tests/integration scripts .github/workflows && \
touch dataset/releases/.gitkeep dataset/signals/.gitkeep dataset/questions/.gitkeep dataset/relations/.gitkeep && \
cat > tests/fixtures/valid/signal_pointer_velocity.json <<'EOF'
{
  "id": "sig_test_pointer_velocity",
  "kind": "RAW",
  "source": "pointer",
  "data_type": "scalar",
  "unit": "pixels_per_second",
  "temporal_window_ms": 0,
  "privacy_level": "ANONYMOUS_METRIC",
  "quality_metric_id": "sig_test_pointer_quality"
}
