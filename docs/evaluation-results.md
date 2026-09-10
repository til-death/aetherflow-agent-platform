# Evaluation Results

本页记录当前离线评测结果。评测不依赖外部 LLM API Key，使用 Runtime 的规则 Planner、Tool Router、Executor 和 Critic，重点验证任务编排与风险治理链路是否稳定。

## 测试设计

- 基线任务：`sample` 10 条，`toolluban` 13 条。
- 随机种子：`7`、`19`、`42`。
- 输入扰动：双语输入、噪声上下文、稀疏输入、语句重排。
- 负向控制：错误工具标注、错误审批标注必须被评估器判定为失败。
- 核心指标：场景准确率、工具 Top@1/3/5、审批准确率、Trace 完整性、输出契约、高风险审批漏判率。

## 结果汇总

| 数据集 | 基线 | 压力测试 | 场景准确率 | Tool Top@1 | Tool Top@3/5 | 审批准确率 | 审批漏判率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `sample` | 10/10 (100%) | 114/120 (95%) | 100% | 100% | 100% / 100% | 100% | 0% |
| `toolluban` | 13/13 (100%) | 153/156 (98%) | 100% | 98% | 100% / 100% | 100% | 0% |

三个随机种子的结果一致，说明当前离线规则链路具备可重复性。这里的基线是已知标注任务回放，不应被解读为真实 LLM 能力分数；压力测试结果更适合用于发现输入变化下的回归问题。

## 失败样本

当前暴露出两类可复盘问题：

1. 稀疏输入没有包含 CSV 原文时，`data_frame_profiler` 无法生成真实字段画像。更合理的产品行为是进入“等待补充数据”的恢复状态，而不是把任务当作已完成。
2. ToolLuban 的某个流程任务在上下文被压缩后，动态工具被通用流程工具抢占。后续可通过增强动态工具的关键词、描述和场景权重改善 Top@1。

## 运行命令

```powershell
uv run --directory backend python scripts/run_reliability_eval.py --dataset sample --seeds 7 19 42
uv run --directory backend python scripts/run_reliability_eval.py --dataset toolluban --seeds 7 19 42
```

完整 JSON 报告会输出基线、压力测试、按随机种子统计、按扰动类型统计、失败样本和负向控制结果。
