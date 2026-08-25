# Alert Noise Analyzer

A synthetic data generator for creating realistic alert datasets with seeded noise patterns (recurring alerts, correlated clusters, bad thresholds, alert storms) to test alert noise detection and analysis algorithms.

## Usage

```bash
# Generate data with default seed (42) into data/
python -m generator.synthetic_data

# Generate with custom seed and output directory
python -m generator.synthetic_data --seed 123 --output-dir ./mydata
```

Outputs:
- `data/alerts.json` — 400-600 alerts with seeded patterns
- `data/runbooks.json` — Runbook URLs for ~70% of policies