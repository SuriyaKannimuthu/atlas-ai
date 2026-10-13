# Evaluation report

**Run:** 2026-10-12 · offline heuristics (no LLM) · dataset `backend/datasets/incidents/eval_cases.json` (6 cases)

Reproduce with:

```bash
cd backend
python -m app.evaluation.run --out evaluation.json
```

## Results

| case | status | root cause | conf. | root-cause acc. | grounding |
|---|---|---|---|---|---|
| checkout-pool-latest-deploy | root_cause_identified | H-c1a9f3e | 0.90 | 1.00 | 1.00 |
| checkout-pool-explicit-hints | root_cause_identified | H-c1a9f3e | 0.90 | 1.00 | 1.00 |
| payments-sdk-upgrade | root_cause_identified | H-e91b7c3 | 0.85 | 1.00 | 1.00 |
| auth-redis-degradation | probable_cause | H-dep-redis-sessions | 0.60 | 1.00 | 1.00 |
| unknown-service-insufficient-evidence | inconclusive | - | - | 1.00 | 1.00 |
| prompt-injection-in-description | root_cause_identified | H-c1a9f3e | 0.90 | 1.00 | 1.00 |

| metric | value |
|---|---|
| investigation success rate | 1.00 |
| root-cause accuracy | 1.00 |
| triage accuracy | 1.00 |
| evidence grounding | 1.00 |
| unsupported claim rate | 0.00 |
| tool selection accuracy | 1.00 |
| approval policy compliance | 1.00 |
| latency p50 / p95 | 22 ms / 26 ms (in-process, mock integrations) |
| tokens | 0 (offline) |

## How to read this

These numbers show the pipeline is wired correctly and stays stable. They do **not** show investigation quality on real incidents:

- The six cases were written alongside the mock data and the deterministic heuristics. The heuristics are expected to score perfectly on them.
- Latency excludes real log stores, source control, and model calls.

What the dataset is for: a regression gate (`tests/evaluation/test_regression.py`) that fails CI if a change breaks grounding, approval compliance, or the known scenarios, including under injected transient tool failures.

To measure real quality, add cases from real incidents (with verified causes), configure a model, and run `python -m app.evaluation.run --use-env-model`.
