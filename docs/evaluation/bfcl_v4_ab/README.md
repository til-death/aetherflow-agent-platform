# BFCL V4 Public A/B Audit

This directory records a fixed A/B audit on the public Berkeley Function Calling Leaderboard data. It is separate from the project-maintained Core, Stress, and Hard development sets.

## Scope

| Category | Cases | What it measures |
| --- | ---: | --- |
| `multiple` | 200 | Select the relevant function from multiple candidates |
| `irrelevance` | 240 | Refuse to call when all provided functions are irrelevant |
| **Total** | **440** | Fixed public cases |

The data and evaluator are provided by `bfcl-eval==2025.12.17`, sourced from the [official BFCL repository](https://github.com/EnlightenedAI/BFCL). The full BFCL V4 benchmark also contains live, multi-turn, agentic, memory, and format-sensitivity categories; this first integration deliberately selects the two categories that can be evaluated fairly by the current deterministic Tool Router without an external model or live connector.

## A/B contract

Both variants receive the same official question and function documents. The only ranking change is:

- **Baseline:** lexical function-document matching with capability cues disabled.
- **Current:** capability-aware reranking plus the fixed confidence/abstention policy.

For `multiple`, the official `possible_answer` function name is used as ground truth. For `irrelevance`, a correct result is an abstention rather than a function call. No BFCL case is added to the project rules.

## Results

| Category | Cases | Baseline | Current | Change | Wrong -> Correct | Correct -> Wrong |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `multiple` | 200 | 97.50% | 94.50% | -3.00 pp | 1 | 7 |
| `irrelevance` | 240 | 0.00% | 63.33% | +63.33 pp | 152 | 0 |
| **Overall** | **440** | **44.32%** | **77.50%** | **+33.18 pp** | **153** | **7** |

Selective metrics for the current policy across all 440 cases:

| Metric | Result |
| --- | ---: |
| Autonomous coverage | 63.41% |
| Selective accuracy | 67.74% |
| Abstain rate | 36.59% |
| Safe handling rate | 79.55% |

Interpretation: the abstention policy substantially improves irrelevance handling, but it also converts 13 otherwise correct low-margin `multiple` selections into safe non-execution. That trade-off is now counted strictly: a relevant task succeeds only when the right tool is selected and execution is allowed. This supports reporting autonomous success together with coverage, selective accuracy and safe handling instead of hiding the safety/coverage trade-off. It does not establish a leaderboard score or prove general Agent capability.

## Reproduce

```powershell
uv run --directory backend --with bfcl-eval==2025.12.17 `
  python scripts/run_bfcl_ab.py `
  --output docs/evaluation/bfcl_v4_ab/results.json
```

The machine-readable report includes the package version, official case IDs, both predictions, abstention reasons, and paired transitions. The BFCL data is not vendored into this repository.
