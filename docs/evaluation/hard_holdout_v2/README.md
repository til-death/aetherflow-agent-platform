# Hard Holdout v2

`hard_holdout_v2` is the first unseen evaluation set created after the capability-aware Tool Reranker was frozen. It is a project-authored generalization set, not an official HELM, ToolBench, or tau-bench dataset.

## Protocol

- 160 independently authored tasks, 32 per scenario
- Same 23-tool pool and scoring contract as `hard_holdout_v1`
- Chinese, English, and mixed-language business phrasing
- Similar-tool interference and explicit tool-boundary cases
- Missing identifiers, missing files, ambiguous files, schema gaps, and missing permissions
- Cross-scenario requests and multi-step dependencies
- High-risk external writes, destructive workflow changes, and sandbox execution
- Created after the Runtime and Reranker freeze; the result was not used for tuning

Manifest SHA-256:

`d4bae600adeca4e76552538a43264e89326bffba273158bdddb118a84b7f1b50`

## Result

| Metric | Result |
| --- | ---: |
| Strict business pass | 46.25% (74/160) |
| Handled rate | 46.25% (74/160) |
| Scenario accuracy | 93.13% |
| Tool Top@1 | 48.75% |
| Tool Top@3 | 91.87% |
| Approval accuracy | 91.25% |
| High-risk cases | 85 |
| High-risk approval false negatives | 0 |
| Trace completeness | 100% |

The 43.12 percentage-point gap between Tool Top@3 and Tool Top@1 confirms that candidate recall is materially better than final reranking on this unseen set. The current bottleneck is fine-grained tool discrimination, especially for analysis and external API requests.

## Scenario slices

| Scenario | Strict pass | Tool Top@1 | Tool Top@3 |
| --- | ---: | ---: | ---: |
| knowledge | 37.50% (12/32) | 43.75% | 75.00% |
| workflow | 50.00% (16/32) | 56.25% | 93.75% |
| code | 87.50% (28/32) | 87.50% | 100.00% |
| analysis | 34.38% (11/32) | 34.38% | 100.00% |
| external_api | 21.88% (7/32) | 21.88% | 90.62% |

## Failure taxonomy

| Taxonomy | Count |
| --- | ---: |
| Router | 11 |
| Retrieval | 0 |
| Tool Selection | 71 |
| Argument | 0 |
| Execution | 0 |
| Evidence | 0 |
| Approval | 4 |

The result is intentionally not presented as a product accuracy claim. It is a frozen diagnostic baseline for the next general engineering iteration. The raw cases are in [`cases.json`](cases.json), and the machine-readable report is in [`results.json`](results.json).

## Capability-boundary regression

Using the v2 taxonomy, the Runtime received a general capability-boundary update: capability cues now use rarity weighting, and similar tools can declare explicit exclusion cues. This is a regression on the same frozen v2 cases, not a new unseen benchmark.

| Metric | Frozen v2 | Regression audit | Change |
| --- | ---: | ---: | ---: |
| Strict business pass | 46.25% (74/160) | 53.12% (85/160) | +6.87 pp |
| Tool Top@1 | 48.75% | 55.63% | +6.88 pp |
| Tool Top@3 | 91.87% | 92.50% | +0.63 pp |
| Scenario accuracy | 93.13% | 93.13% | no regression |
| High-risk false negatives | 0/85 | 0/85 | no regression |
| Trace completeness | 100% | 100% | no regression |

The regression artifact is [`results-reranker-audit.json`](results-reranker-audit.json), and the same task manifest is preserved in [`cases-reranker-audit.json`](cases-reranker-audit.json). The result does not replace the frozen v2 baseline; a future v3 unseen set is still required before claiming generalization for this second optimization.
