# 稳流 Release Notes

## 0.2.0 - Systematic evaluation and recovery hardening

- Added a stratified 320-task evaluation set covering five runtime scenarios, with 64 independently labelled tasks per scenario.
- Added 3 random seeds and 4 input perturbations, producing 3,840 stress runs with scenario, approval, trace, tool-ranking and Wilson confidence interval summaries.
- Added explicit safe-recovery metadata for missing CSV input. The runtime now distinguishes strict business completion from a handled state that asks the user for the missing source file.
- Improved tool ranking with keyword rarity weighting, tool-name specificity, scenario fit, historical success rate, risk and latency signals.
- Added a primary failure taxonomy (`Router`, `Retrieval`, `Tool Selection`, `Argument`, `Execution`, `Evidence`, `Approval`) with counts, rates and representative stress cases.
- Added the frozen `hard_holdout_v1` set: 150 independently authored cases, 30 per scenario, with a SHA-256 manifest and separate cases/results artifacts.
- Added a capability-aware second-stage Tool Reranker. It uses explicit tool capability cues and preserves dynamic-tool keywords as a fallback contract; the v1 regression audit improved strict pass from 68.00% to 72.67% and Tool Top@1 from 69.33% to 74.00%, without changing Core/Stress results or high-risk approval safety.
- Added the frozen unseen `hard_holdout_v2` set: 160 independently authored cases with a recorded manifest hash. A single post-freeze run reached 46.25% strict pass, 48.75% Tool Top@1, 91.87% Tool Top@3, 0/85 high-risk approval false negatives, and 100% trace completeness; the result is retained as a generalization diagnostic rather than used for tuning.
- Added rarity-weighted capability cues and explicit exclusion boundaries for similar tools. On the frozen v2 regression audit, strict pass improved to 53.12% and Tool Top@1 to 55.63%, while the 320-task Core, 3,840-run Stress, approval safety, and Trace completeness showed no regression.
- Added confidence-based abstention for low-score, small-margin, capability-conflict and missing-input decisions; the policy records a safe recovery trace instead of forcing an uncertain tool call.
- Added a fixed A/B audit on 440 public BFCL V4 cases: strict current success is 77.50% versus baseline 44.32% overall (+33.18 pp), with irrelevance handling improving from 0.00% to 63.33%. Relevant-task abstentions are counted as safe handling but not autonomous success. This is explicitly recorded as a project audit, not an official leaderboard submission.
- Re-ran the fixed systematic suite after the abstention change: Core 320/320, Stress 3,648/3,840 strict passes, 3,840/3,840 handled, 0/1,824 high-risk approval false negatives, and 100% Trace completeness.
- Persisted the systematic evaluation artifact under `docs/systematic-evaluation-results.json` for GitHub review and regression comparison.
- Current engineering gate: 9 agent tests pass; the fixed benchmark reaches 100% base pass and 95% strict stress pass, with 100% handled rate, 0 high-risk approval false negatives, and 100% trace completeness. Remaining strict failures are explicit missing-input recovery states.

## 0.1.0 - GitHub-ready baseline

- Added the employee-facing Agent workbench and task execution flow.
- Split the Runtime into routing, planning, retrieval, tool selection, execution, critique, memory, and evaluation modules.
- Added structured DAG validation, approval gates, dry-run execution, recovery records, and replayable `AgentTraceStep` records.
- Added the real `data_frame_profiler` tool for CSV profiling and anomaly hints.
- Added benchmark tasks, randomized-seed robustness evaluation, failure categories, and Release Gate metrics.
- Added Docker Compose startup, repository screenshots, and a focused GitHub CI workflow.

## Scope

This release is an enterprise Agent Runtime prototype. External writes, code execution, and customer-visible actions remain dry-run by default and require approval. Production integrations such as SSO, object storage, queues, and real connectors are intentionally left behind explicit extension points.
