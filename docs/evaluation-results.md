# Evaluation Results

## 320-task systematic evaluation (2026-09-15)

This is the current engineering evaluation. It is a project-maintained, contract-based test set for the Runtime and is not an official HELM, ToolBench, or tau-bench score.

### Test design

| Item | Count |
| --- | ---: |
| Independent tasks | 320 |
| Tasks per scenario | 64 |
| Scenarios | 5: knowledge, workflow, code, analysis, external_api |
| High-risk independent tasks | 152 |
| Random seeds | 3: 7, 19, 42 |
| Input perturbations | 4: bilingual, noisy_context, sparse_input, reordered |
| Stress runs | 3,840 |
| Tool pool | 13, including similar distractor tools |

### Aggregate results

| Metric | Keyword-only baseline | Runtime |
| --- | ---: | ---: |
| Strict business pass | 52.50% (168/320) | 100.00% (320/320), 95% Wilson CI [98.81%, 100.00%] |
| Scenario accuracy | 95.00% | 100.00% |
| Tool Top@1 | 95.00% | 100.00% |
| Tool Top@3 | 100.00% | 100.00% |
| Approval accuracy | 52.50% | 100.00% |
| Trace completeness | 0.00% | 100.00% |
| High-risk approval false negatives | 152/152 | 0/152 |

For the 3,840-run stress set, strict business pass is **95.00% (3,648/3,840)**, with a 95% Wilson CI of **[94.26%, 95.65%]**. The Runtime handled **100.00% (3,840/3,840)** when safe recovery is counted; 192 cases were explicitly stopped because the CSV source was missing, with a recovery action asking for the file instead of fabricating an analysis result. High-risk approval false negatives remained **0/1,824**, and trace completeness remained **100%**.

### Failure taxonomy for the 384 strict failures

The evaluator assigns one primary cause according to the Runtime execution order. A case is counted only once, so overlapping symptoms do not inflate the totals.

| Taxonomy | Count | Share of failures | Interpretation |
| --- | ---: | ---: | --- |
| `Router` | 0 | 0.00% | No routing failure was triggered after adding high-discrimination API capability terms. |
| `Retrieval` | 192 | 50.00% | The analysis task had no parseable CSV source; the Runtime safely requested the missing input. |
| `Tool Selection` | 0 | 0.00% | No tool-selection failure remained after enriching HTTP connector capability metadata. |
| `Argument` | 0 | 0.00% | No argument-contract failure was triggered by this stress set. |
| `Execution` | 0 | 0.00% | No tool execution failure was triggered by this stress set. |
| `Evidence` | 0 | 0.00% | No evidence or output-contract failure was triggered by this stress set. |
| `Approval` | 0 | 0.00% | No approval or guardrail failure was triggered; high-risk false negatives were 0/1,824. |

The 192 Retrieval cases are strict failures but safe product behavior: the system did not fabricate a result and returned an actionable recovery step. The next engineering priority is to improve the employee-facing input contract for CSV analysis and extend the benchmark with injected argument, execution, evidence, and approval faults so the zero buckets are actively tested rather than assumed safe.

### Stress slices

| Slice | Strict pass | Handled | Notes |
| --- | ---: | ---: | --- |
| knowledge | 100.00% | 100.00% | Evidence retrieval and graph expansion remain stable. |
| code | 100.00% | 100.00% | Sandbox and approval contract held across all runs. |
| workflow | 100.00% | 100.00% | Specialized transition tool remains preferred over the generic distractor. |
| external_api | 100.00% | 100.00% | HTTP API capability terms disambiguate the connector from webhook dispatch. |
| analysis | 75.00% | 100.00% | Missing-input recovery is safe, but it is not counted as completed analysis. |
| sparse_input | 80.00% | 100.00% | Most handled-but-not-completed cases are intentional recovery states. |

The remaining strict failures are intentional missing-input recoveries. The report keeps them visible in `failure_categories` and `failure_taxonomy`, so future retrieval improvements can be measured against the same fixed test set rather than tuned against a single headline number.

The complete machine-readable report is [`systematic-evaluation-results.json`](systematic-evaluation-results.json).

## Frozen Hard Holdout v1

`hard_holdout_v1` was authored after the current Runtime routing and tool-ranking logic was frozen. Its failures were not used for rule tuning.

| Metric | Result |
| --- | ---: |
| Cases | 150, exactly 30 per scenario |
| Strict business pass | 68.00% (102/150) |
| Handled rate | 68.67% (103/150) |
| Scenario accuracy | 95.33% |
| Tool Top@1 | 69.33% |
| Tool Top@3 | 94.67% |
| Approval accuracy | 97.33% |
| High-risk cases | 85 |
| High-risk approval false negatives | 0 |
| Trace completeness | 100% |

### Hard Holdout by scenario

| Scenario | Strict pass | Tool Top@1 |
| --- | ---: | ---: |
| knowledge | 70.00% (21/30) | 73.33% |
| workflow | 66.67% (20/30) | 66.67% |
| code | 83.33% (25/30) | 83.33% |
| analysis | 40.00% (12/30) | 43.33% |
| external_api | 80.00% (24/30) | 80.00% |

### Hard Holdout failure taxonomy

| Taxonomy | Count |
| --- | ---: |
| Router | 7 |
| Retrieval | 1 |
| Tool Selection | 39 |
| Argument | 0 |
| Execution | 0 |
| Evidence | 0 |
| Approval | 1 |

The result is intentionally lower than the Core Benchmark: the holdout contains similar tools, ambiguous files, cross-scenario requests, multi-step dependencies, and mixed or informal wording. This makes it useful as a generalization baseline rather than another score to optimize against.

The complete frozen artifact is under [`docs/evaluation/hard_holdout_v1`](evaluation/hard_holdout_v1/): [`cases.json`](evaluation/hard_holdout_v1/cases.json), [`results.json`](evaluation/hard_holdout_v1/results.json), and its `manifest_sha256`.

### Tool reranker regression audit

After archiving the frozen v1 result, the Runtime was upgraded from a single weighted ranking pass to a capability-aware second-stage reranker. The first stage still retrieves broad candidates; the second stage scores distinctive capability cues, dynamic-tool metadata, and explicit decision-boundary cues. Existing dynamic tools without a `capability_cues` field fall back to their declared keywords, so the change does not privilege only built-in tools.

This is a regression audit on the same v1 cases, not a new holdout score:

| Metric | Frozen v1 | Reranker audit | Change |
| --- | ---: | ---: | ---: |
| Strict business pass | 68.00% (102/150) | 72.67% (109/150) | +4.67 pp |
| Handled rate | 68.67% (103/150) | 73.33% (110/150) | +4.66 pp |
| Tool Top@1 | 69.33% | 74.00% | +4.67 pp |
| Tool Top@3 | 94.67% | 96.00% | +1.33 pp |
| Scenario accuracy | 95.33% | 95.33% | no regression |
| High-risk false negatives | 0/85 | 0/85 | no regression |
| Trace completeness | 100% | 100% | no regression |

The audit artifact is [`results-reranker-audit.json`](evaluation/hard_holdout_v1/results-reranker-audit.json). A fresh `hard_holdout_v2` should be authored after this implementation is frozen before using the improvement as a generalization claim.

## Unseen Hard Holdout v2

After the Reranker audit, the Runtime and Reranker were frozen and evaluated once on a newly authored 160-case holdout. The v2 set is independent from v1 and keeps the same 23-tool pool and scoring contract. It is intentionally a diagnostic generalization result, not another score to tune against.

| Metric | Result |
| --- | ---: |
| Cases | 160, 32 per scenario |
| Strict business pass | 46.25% (74/160) |
| Handled rate | 46.25% (74/160) |
| Scenario accuracy | 93.13% |
| Tool Top@1 | 48.75% |
| Tool Top@3 | 91.87% |
| Approval accuracy | 91.25% |
| High-risk approval false negatives | 0/85 |
| Trace completeness | 100% |

The gap between Tool Top@3 and Tool Top@1 is 43.12 percentage points. This confirms that the v2 bottleneck remains fine-grained reranking rather than candidate recall. The primary failure taxonomy is `Tool Selection` (71), followed by `Router` (11) and `Approval` (4); there were no Retrieval, Argument, Execution, or Evidence failures in this run.

The complete v2 artifact is under [`docs/evaluation/hard_holdout_v2`](evaluation/hard_holdout_v2/): [`README.md`](evaluation/hard_holdout_v2/README.md), [`cases.json`](evaluation/hard_holdout_v2/cases.json), and [`results.json`](evaluation/hard_holdout_v2/results.json). Its manifest SHA-256 is `d4bae600adeca4e76552538a43264e89326bffba273158bdddb118a84b7f1b50`.

### v2 capability-boundary regression

The v2 failure taxonomy was used to make one general Runtime change: capability cues are rarity-weighted in the second-stage reranker, while similar tools can declare explicit exclusion cues. No v2 task text was added to the Runtime. The same frozen v2 set improved from 46.25% to 53.12% strict pass and from 48.75% to 55.63% Tool Top@1; Core/Stress remained at 100%/95%, high-risk false negatives remained 0, and Trace remained 100%. This is a regression audit, not a replacement for the frozen unseen result.

## BFCL V4 public A/B audit

To add an external reference point without presenting a deterministic router as an official leaderboard submission, the current Runtime was evaluated against 440 cases from the public BFCL V4 `multiple` (200) and `irrelevance` (240) subsets. The data is loaded at runtime from `bfcl-eval==2025.12.17`; it is not vendored into the repository.

The A/B contract keeps the cases, function documents and expected answers fixed. The baseline disables capability cues and uses lexical matching; the current variant uses the capability-aware reranker plus the confidence/abstention policy. Results:

| Subset | Cases | Baseline | Current | Change |
| --- | ---: | ---: | ---: | ---: |
| `multiple` | 200 | 97.50% | 94.50% | -3.00 pp |
| `irrelevance` | 240 | 0.00% | 63.33% | +63.33 pp |
| **Overall** | **440** | **44.32%** | **77.50%** | **+33.18 pp** |

Across the current policy, autonomous coverage was 63.41%, selective accuracy was 67.74%, abstention rate was 36.59%, and safe-handling rate was 79.55%. The strict scoring rule requires a relevant task to both select the expected tool and execute; abstaining is safe handling, but not task success. These are project-level A/B audit results, not an official BFCL leaderboard score. The reproducible artifact and exact case-level transitions are in [`docs/evaluation/bfcl_v4_ab`](evaluation/bfcl_v4_ab/).

本页记录当前 Runtime 的可复现离线评估结果。

> 最近复核：2026-09-16<br>
> Runtime：`aetherflow-runtime-v1`<br>
> 执行模式：确定性规则 Planner、Tool Router、Executor 和 Critic，不需要外部 LLM API Key

## 评估边界

这里测量的是 **Agent Runtime 的可靠性与治理能力**，不是模型通用能力排行榜。每个 Case 都会经过场景路由、DAG 规划、证据检索、工具排序、dry-run 执行、Critic 审核和输出契约检查。

仓库内的两个数据集由项目维护：

| 数据集 | 内容 | 定位 |
| --- | --- | --- |
| `sample` | 10 条知识、流程、代码、分析、外部 API 和记忆任务 | Runtime 基础回归集 |
| `toolluban` | 13 条带动态工具库的企业任务，覆盖审批、CSV 分析、代码沙箱和外部系统写入 | ToolLuban-style 动态工具路由集，不宣称是官方 ToolLuban 榜单数据 |

为了避免夸大结果，README 和本报告没有把自建数据集包装成 HELM、ToolBench 或 τ-Bench 的官方分数。公开基准仅作为后续对接方向：

- [HELM（Stanford CRFM）](https://github.com/stanford-crfm/helm)：适合统一评估模型能力、效率和安全维度。
- [τ-Bench（Sierra Research）](https://github.com/sierra-research/tau-bench)：适合评估工具调用、用户交互和业务规则下的 Agent 行为。

当前报告没有虚构这些公开基准的结果；后续接入真实模型或连接器时，应单独记录模型、温度、提示词版本、工具环境和评测提交版本。

## 测试矩阵

每个数据集都执行一次基线回放，并在 3 组随机种子下应用 4 类输入扰动：

```text
seeds: 7, 19, 42
variants: bilingual, noisy_context, sparse_input, reordered
```

| 数据集 | 基线 Case | 压力 Case | 计算方式 |
| --- | ---: | ---: | --- |
| `sample` | 10 | 120 | 10 × 3 seeds × 4 variants |
| `toolluban` | 13 | 156 | 13 × 3 seeds × 4 variants |

评估指标包括：

- `pass_rate`：场景、工具、审批、Trace、输出契约和工具执行条件全部满足的比例
- `scenario_accuracy`：是否进入期望场景
- `tool_top1/top3/top5`：期望工具是否分别命中首选、前三或前五候选
- `approval_accuracy`：审批判断是否与标注一致
- `safety_false_negative_rate`：高风险任务被错误放行的比例
- `trace_completeness`：关键 Runtime 阶段是否都能回放
- `contract_coverage`：业务输出是否覆盖预期字段

## 实测结果

| 数据集 | 基线通过 | 压力通过 | 场景准确率 | Tool Top@1 | Tool Top@3 / Top@5 | 审批准确率 | Trace 完整性 | 高风险漏判 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `sample` | 10/10 (100%) | 114/120 (95%) | 100% | 100% | 100% / 100% | 100% | 100% | 0% |
| `toolluban` | 13/13 (100%) | 153/156 (98%) | 100% | 98% | 100% / 100% | 100% | 100% | 0% |

### 输入扰动切片

| 数据集 | 双语输入 | 噪声上下文 | 稀疏输入 | 语句重排 |
| --- | ---: | ---: | ---: | ---: |
| `sample` | 30/30 (100%) | 30/30 (100%) | 24/30 (80%) | 30/30 (100%) |
| `toolluban` | 39/39 (100%) | 39/39 (100%) | 36/39 (92%) | 39/39 (100%) |

这里的稀疏输入是有意构造的压力场景：移除上下文、预期输出、场景提示和标签，模拟员工只输入一句不完整目标的情况。

## 失败样本与工程结论

评估没有隐藏失败 Case，而是将它们作为 Runtime 的改进信号：

1. `sample` 有 6 条失败，全部来自 `analysis_001/002` 的稀疏输入。由于缺少 CSV 原文，`data_frame_profiler` 无法生成字段画像。产品层更合理的行为是进入“等待补充数据”恢复状态，而不是把任务标记为完成。
2. `toolluban` 有 3 条失败，全部来自 `tlb_workflow_003` 的稀疏输入。动态工具描述信息不足时，通用 `workflow_state_transition` 会抢占专用状态同步工具；但期望工具仍在 Top@3 内，说明需要继续优化工具描述和排序权重，而不是简单增加工具数量。
3. 两套数据集的负向控制均为 `2/2 detected`：错误工具标注和错误审批标注都被评估器判定为失败，说明评估器不是无条件报喜的静态分数面板。

## 工程质量验证

当前已实际运行：

```powershell
uv run --directory backend pytest tests/agent -q
# 9 passed
```

前端构建和完整 Docker 集成测试属于独立门禁，需要在安装前端依赖并启动 PostgreSQL 后执行；本页不把未执行的检查写成通过。

## 复现命令

```powershell
uv run --directory backend python scripts/run_reliability_eval.py --dataset sample --seeds 7 19 42
uv run --directory backend python scripts/run_reliability_eval.py --dataset toolluban --seeds 7 19 42
uv run --directory backend pytest tests/agent -q
```

评估脚本会输出完整 JSON，包括每个随机种子、扰动类型、失败 Case、失败类别和修复建议。随机种子仅用于复现和稳定性分析，不代表模型能力排名。
