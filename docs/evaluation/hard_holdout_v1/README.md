# hard_holdout_v1

This is the frozen holdout set for AetherFlow Runtime reliability evaluation.

## Freeze policy

- 150 independently authored tasks, 30 per scenario.
- Created after the current Runtime routing and tool-ranking logic was frozen.
- Holdout failures must not be used to tune the current rules.
- The task manifest is identified by `manifest_sha256` in `results.json`.
- A later version may promote reviewed failures into `benchmark_v2`, but this set remains unchanged.

## Coverage

- Similar tool interference
- Partial or ambiguous input
- Cross-scenario routing
- Multi-step dependencies
- Unseen mixed-language, shorthand and business phrasing

## Files

- `cases.json`: complete task definitions and expected contracts
- `results.json`: frozen-run metrics and representative failures

## Reproduce

```powershell
uv run --cache-dir .uv-cache python backend/scripts/run_hard_holdout.py `
  --output docs/evaluation/hard_holdout_v1/results.json `
  --cases-output docs/evaluation/hard_holdout_v1/cases.json
```

The current result is a generalization baseline, not a tuned score.
