# Evaluation Results

本页记录当前 Runtime 的可复现离线评估结果。

> 最近复核：2026-09-10<br>
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
