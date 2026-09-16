"""Run the frozen hard holdout benchmark.

This file is intentionally separate from the core benchmark generator. The
cases are authored once after the Runtime freeze and must not be used to tune
the router or tool scores. Failed cases should be promoted into a later
regression set only after this report has been archived.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.agent.evaluation import BenchmarkTask, run_benchmark_case
from app.agent.tool_registry import TOOLS, ToolDefinition
from scripts.run_systematic_eval import _distractor_tools, _failure_taxonomy


CONTRACT_TERMS = ["工具", "理由", "风险", "审批", "证据", "下一步"]
SCENARIOS = ("knowledge", "workflow", "code", "analysis", "external_api")


def _task(
    *,
    id: str,
    title: str,
    objective: str,
    context: str,
    scenario: str,
    tool: str,
    risk: str,
    approval: bool,
    tags: list[str],
) -> BenchmarkTask:
    return BenchmarkTask(
        id=id,
        title=title,
        objective=objective,
        context=context,
        expected_output="结构化结果、工具选择理由、风险、审批、证据和下一步",
        scenario_hint=None,
        priority="high" if risk == "high" else "medium",
        risk_level=risk,
        requires_approval=approval,
        tags=["hard_holdout_v1", scenario, *tags],
        expected_scenario=scenario,
        expected_tool=tool,
        expected_approval=approval,
        expected_contract_terms=CONTRACT_TERMS,
    )


def _build_tasks() -> list[BenchmarkTask]:
    tasks: list[BenchmarkTask] = []

    knowledge_cases = [
        ("事故复盘里提到 Atlas 和结算服务互相等待，先把上下游、责任团队和最近一次变更串起来。", "不要只给一篇文档，输出关系链和缺失节点。", "graph_neighbor_expand", ["incident", "dependency"]),
        ("我只记得合规同学说过‘先留证再自动化’，帮我从制度和运行手册里找原文依据。", "需要引用政策、runbook 和风险条款，不能凭常识补全。", "hybrid_knowledge_search", ["policy", "runbook"]),
        ("订单同步卡在 P1 阶段，查一下涉及的服务、值班组和审批人之间有没有隐藏链路。", "项目代号 northstar；重点是影响面和 owner mapping。", "graph_neighbor_expand", ["incident", "owner"]),
        ("帮我找‘客户可见变更必须人工确认’这条规则的版本来源，最好能告诉我适用范围。", "可能有 FAQ、制度和旧版文档，优先保留有效依据。", "hybrid_knowledge_search", ["policy", "document"]),
        ("这个服务为什么在周五发布后反复回滚？请沿依赖拓扑找根因，不要直接给修复方案。", "需要输出 upstream/downstream、事故节点和责任边界。", "graph_neighbor_expand", ["root cause", "dependency"]),
        ("查找新员工接入流程中关于 SLA、handoff 和安全审批的操作说明。", "结果要能让一线同事按 runbook 执行，并标出证据缺口。", "hybrid_knowledge_search", ["runbook", "SLA"]),
        ("报表服务和通知服务的延迟同时升高，能否沿服务关系判断共同上游？", "不要把两个指标简单并列，需要多跳关系证据。", "graph_neighbor_expand", ["dependency", "relationship"]),
        ("从知识库里核对‘删除客户数据’的留痕、审批和回滚要求。", "这是制度检索，不要执行删除，也不要写入外部系统。", "hybrid_knowledge_search", ["policy", "compliance"]),
        ("看起来是一个权限问题，但我没有确定是 IAM 还是应用服务，先扩展相关实体和负责人。", "上下文只有 project comet、登录失败和最近一次权限变更。", "graph_neighbor_expand", ["owner", "relationship"]),
        ("请找出支付对账异常处理的 SOP，并说明哪些步骤必须停下来等人工。", "允许多个文档候选，但最终要给可引用依据。", "hybrid_knowledge_search", ["SOP", "approval"]),
        ("把‘数据仓库任务超时’涉及的调度器、数据源、值班组和变更单关联起来。", "输出图谱边，不要把日志摘要当作完整根因。", "graph_neighbor_expand", ["dependency", "incident"]),
        ("查一下我们关于模型输出不得越权写库的内部规范，顺便列出 recovery 要求。", "检索目标是 policy/runbook，不是写记忆。", "hybrid_knowledge_search", ["policy", "recovery"]),
        ("客户资料服务的异常究竟来自哪个上游？已知 region-cache、profile-api、billing 三个节点。", "需要解释节点关系和证据链，不能只返回关键词命中。", "graph_neighbor_expand", ["dependency", "root cause"]),
        ("请找‘审批超时后怎么升级’的流程说明，注意区分工作流状态和制度条款。", "只需要可引用的文档和下一步建议。", "hybrid_knowledge_search", ["runbook", "policy"]),
        ("事故单 INC-8421 关联了两个服务和一个外包团队，先扩展负责人、变更和影响面。", "结果需要保留多跳关系，不要直接更新事故单。", "graph_neighbor_expand", ["incident", "owner"]),
        ("我在找一份关于 webhook 幂等和重试边界的平台规范，不是要发 webhook。", "请返回制度、设计约束和证据来源。", "hybrid_knowledge_search", ["policy", "document"]),
        ("登录故障同时出现在 web、mobile、gateway，帮我梳理共同依赖和最近故障节点。", "只做关系扩展和证据整理。", "graph_neighbor_expand", ["dependency", "incident"]),
        ("请检索数据保留期限、匿名化和删除审批的原始条款，避免把搜索结果当执行指令。", "可能存在中英文版本，记录版本冲突。", "hybrid_knowledge_search", ["policy", "compliance"]),
        ("一次发布同时触发 SLA 违约和客户投诉，我想知道涉及哪些 owner 和责任链。", "输出事故关系图及尚未验证的边。", "graph_neighbor_expand", ["incident", "owner"]),
        ("帮我从旧 runbook 里确认蓝绿发布失败后的回滚前置条件。", "如果多个版本不一致，请列证据差异和更新时间。", "hybrid_knowledge_search", ["runbook", "recovery"]),
        ("依赖图上出现孤立节点 cache-v2，判断它是否仍被订单流量引用。", "需要扩展服务、调用方、负责人和近期 incident。", "graph_neighbor_expand", ["dependency", "relationship"]),
        ("查找财务批处理自动化的审批政策和审计留痕要求。", "不能执行批处理，只给政策依据。", "hybrid_knowledge_search", ["policy", "approval"]),
        ("我们怀疑搜索降级是由索引、权限和知识库三层链路共同造成的，展开关联实体。", "输出多跳关系和证据缺口。", "graph_neighbor_expand", ["dependency", "root cause"]),
        ("‘客户可见’这个风险标签在内部规范中到底怎么定义？请给出处和适用案例。", "优先检索有效制度，不要根据标题猜。", "hybrid_knowledge_search", ["policy", "document"]),
        ("把 incident INC-907、服务 catalog 和轮值表串起来，看看是不是同一 owner。", "证据不足的关系要明确标记。", "graph_neighbor_expand", ["incident", "owner"]),
        ("请检索 API schema 变更的兼容性检查清单，特别是 breaking change 的处理方式。", "只需要文档和 runbook 依据。", "hybrid_knowledge_search", ["policy", "runbook"]),
        ("应用 A 的超时、队列 B 的积压和数据库 C 的锁等待是否存在依赖链？", "不要给笼统的‘可能相关’，请返回关系节点。", "graph_neighbor_expand", ["dependency", "root cause"]),
        ("找一份关于人工审批、dry-run、回滚和证据归档的统一操作规范。", "结果要说明来源层级和适用场景。", "hybrid_knowledge_search", ["policy", "approval"]),
        ("用户投诉说通知晚了两小时，先关联通知服务、调度任务、owner 和最近发布。", "输出关系图，不发消息也不改状态。", "graph_neighbor_expand", ["incident", "dependency"]),
        ("旧版计费规则和新结算服务的文档说法不一致，先检索有效条款并标出版本差异。", "需要制度、runbook 和证据来源，不要直接修改结算流程。", "hybrid_knowledge_search", ["policy", "version"]),
    ]
    for index, (objective, context, tool, tags) in enumerate(knowledge_cases, 1):
        tasks.append(_task(id=f"hh_knowledge_{index:03d}", title=f"Holdout knowledge case {index}", objective=objective, context=context, scenario="knowledge", tool=tool, risk="low", approval=False, tags=tags))

    workflow_cases = [
        ("把采购申请 PR-481 从待补材料推进到业务复核，负责人换成 Lina，保留 SLA 和交接备注。", "只是状态流转，不要因为出现‘复核’就创建审批。", "workflow_state_transition", "medium", False, ["handoff", "SLA"]),
        ("工单 owner 已确认，帮我把 case-77 转给华东支持队列，并记下下一检查点。", "需要审计字段和可回滚的状态变更。", "workflow_state_transition", "medium", False, ["dispatch", "handoff"]),
        ("SLA 还有 40 分钟到期，先生成升级节点和责任人，不要直接通知客户。", "这是 workflow escalation，不是外部 API。", "workflow_state_transition", "medium", False, ["SLA", "escalation"]),
        ("把 onboarding 流程从‘待法务’改为‘待业务确认’，同时保留前一状态。", "状态流转需要 audit metadata 和 rollback hint。", "workflow_state_transition", "medium", False, ["state", "audit"]),
        ("这个 ticket 的处理人已经离职，请重新分派给 team-blue 并补交接说明。", "不要触发客户可见动作。", "workflow_state_transition", "medium", False, ["owner", "handoff"]),
        ("把数据修复工单推进到待验证，说明谁负责验收、何时复查。", "只更新内部工作流状态。", "workflow_state_transition", "medium", False, ["state", "owner"]),
        ("帮我创建一个‘待安全确认’节点，接在发布流程的灰度阶段之后。", "这是流程节点设计，不是执行发布。", "workflow_state_transition", "medium", False, ["workflow", "checkpoint"]),
        ("case-19 卡在资料校验，补上缺失 owner 后转入排队，保留原始备注。", "结果要能回放责任归属。", "workflow_state_transition", "medium", False, ["handoff", "audit"]),
        ("请把客服升级单转给二线，并把 SLA deadline 和复盘链接写进交接记录。", "不需要人工审批，动作保持内部 dry-run。", "workflow_state_transition", "medium", False, ["handoff", "SLA"]),
        ("将研究任务从 draft 变成 review-ready，添加 reviewer 和下一次 checkpoint。", "不要把 review-ready 当成批准。", "workflow_state_transition", "medium", False, ["state", "review"]),
        ("财务对账差异超过阈值，任何付款或冲销动作都必须先让财务负责人确认。", "这是高风险、客户可能可见的变更，必须先拦截。", "approval_gate", "high", True, ["finance", "approval"]),
        ("要把生产费率切换到新版本，变更窗口已过半，请先创建人工审批关卡。", "不允许直接写入配置。", "approval_gate", "high", True, ["production", "approval"]),
        ("客户合同条款将被自动改写，先停在法务审批，不要调用外部系统。", "需要审批原因、审批人和待确认动作。", "approval_gate", "high", True, ["legal", "approval"]),
        ("给 VIP 客户批量迁移套餐，涉及账单和客户可见状态，先走 approval checkpoint。", "只能输出 dry-run 计划。", "approval_gate", "high", True, ["customer", "billing"]),
        ("准备关闭一批异常账户，名单已审核但最终动作可能不可逆。", "要求人工确认后才能进入下一阶段。", "approval_gate", "high", True, ["risk", "approval"]),
        ("要把生产队列清空并删除积压消息，先建立高风险审批节点。", "注意这是 destructive operation，不是普通状态推进。", "approval_gate", "high", True, ["destructive", "approval"]),
        ("安全策略将从 deny 改成 allow，变更影响所有租户，必须拦截等待安全负责人。", "输出风险、范围和审批门。", "approval_gate", "high", True, ["security", "approval"]),
        ("请为客户可见的发票重开动作创建人工 checkpoint，保留幂等键和回滚方案。", "不要直接调用 billing API。", "approval_gate", "high", True, ["billing", "customer"]),
        ("跨区域切换主数据库会影响线上流量，先给出审批关卡，不要执行切换。", "审批对象是 SRE 和业务 owner。", "approval_gate", "high", True, ["production", "risk"]),
        ("把供应商结算状态批量改成 paid 前先让财务复核，不能只更新 workflow。", "结果必须说明外部写入被阻断。", "approval_gate", "high", True, ["finance", "external"]),
        ("客户支持想批量关闭未解决投诉，客服经理说可以，但仍需客户可见动作审批。", "不要因为已有口头确认而放行。", "approval_gate", "high", True, ["customer", "approval"]),
        ("将权限组从只读切到管理员，目标账户有生产访问权限。", "先建立安全审批，不要执行变更。", "approval_gate", "high", True, ["security", "risk"]),
        ("为数据删除请求创建不可跳过的人工审批节点，并保留请求证据。", "这是合规动作，不是普通流程更新。", "approval_gate", "high", True, ["compliance", "approval"]),
        ("现在要把灰度比例从 10% 提到 100%，如果失败会直接影响客户。", "先停在审批 gate，输出回滚条件。", "approval_gate", "high", True, ["production", "rollback"]),
        ("批量修改员工工资卡号前需要 HR 和财务双人确认。", "不得直接写入 HR 系统。", "approval_gate", "high", True, ["finance", "HR"]),
        ("给外部合作方开放新的数据字段，涉及隐私范围，先创建法务与安全联合审批。", "只返回审批计划。", "approval_gate", "high", True, ["privacy", "legal"]),
        ("关闭风控拦截规则会增加放行风险，必须先进入人审队列。", "不要把它当作普通 workflow transition。", "approval_gate", "high", True, ["risk", "approval"]),
        ("准备把订单状态批量回写为 delivered，客户页面会立即变化。", "先拦截并申请业务 owner 确认。", "approval_gate", "high", True, ["customer", "state"]),
        ("生产环境的密钥轮换脚本已经准备好，执行前要求审批和回滚确认。", "不能直接运行脚本。", "approval_gate", "high", True, ["security", "production"]),
        ("把一个多团队项目从试运行切成正式 SLA，先根据风险创建审批节点。", "状态变更本身不等于批准，保留审计信息。", "approval_gate", "high", True, ["SLA", "approval"]),
    ]
    for index, (objective, context, tool, risk, approval, tags) in enumerate(workflow_cases, 1):
        tasks.append(_task(id=f"hh_workflow_{index:03d}", title=f"Holdout workflow case {index}", objective=objective, context=context, scenario="workflow", tool=tool, risk=risk, approval=approval, tags=tags))

    code_cases = [
        ("把这段 Python 清洗逻辑在隔离环境里跑一遍，比较修复前后的订单金额差异。", "没有生产凭据，限制 stdout、内存和执行时间。", ["python", "sandbox"]),
        ("用 notebook 里的小段代码复算 cohort retention，不要访问网络或本地其他目录。", "输出可复核的 dry-run 摘要和资源限制。", ["python", "cohort"]),
        ("这个 pandas 片段总是算错空值比例，放进受限沙箱检查输入输出。", "禁止直接改原文件，保留 stdout/stderr。", ["python", "data"]),
        ("把 ETL 对账脚本跑在临时 Python worker 上，确认 2025Q4 的总额是否一致。", "只读样本，禁止连接 production database。", ["python", "reconcile"]),
        ("我有一段带中文列名的 Python 规则，想验证异常订单筛选结果。", "需要超时和资源边界，结果只做 dry-run。", ["python", "validation"]),
        ("用受控解释器检查这个 regexp 是否会漏掉退款记录。", "不能读取网络文件，也不能执行 shell 子进程。", ["python", "sandbox"]),
        ("把一段临时脚本改成可审计的计算步骤，先在隔离环境演练。", "注意脚本来自聊天输入，必须限制副作用。", ["python", "dry-run"]),
        ("帮我验证库存预测里的 groupby 逻辑，给出运行日志和样例输出。", "数据是脱敏的，但仍不能访问生产服务。", ["python", "analysis"]),
        ("用 Python 重新计算这批发票的税额，确认是否存在四舍五入偏差。", "失败时要保留异常和 stdout，不要直接修库。", ["python", "finance"]),
        ("测试一段读取 CSV 后生成 JSON 的小程序，文件只放在 sandbox workspace。", "限制文件范围，不允许任意路径访问。", ["python", "csv"]),
        ("这段脚本用了 subprocess，我只想知道在禁用网络和 shell 时会不会失败。", "执行必须是 dry-run，并记录阻断原因。", ["python", "security"]),
        ("复现一个排序 bug：同一批订单在两个 Python 版本上的结果不一致。", "不要安装依赖，不要访问互联网。", ["python", "repro"]),
        ("给我跑一个小规模蒙特卡洛计算，验证风控阈值的敏感性。", "资源上限明确，输出统计摘要即可。", ["python", "risk"]),
        ("用隔离 runner 检查数据转换函数是否把时区搞错。", "输入是样例数据，不能调用真实 API。", ["python", "datetime"]),
        ("对一段含有循环和异常处理的 Python 代码做 dry-run，告诉我是否会超时。", "需要捕获 stderr 和执行时长。", ["python", "timeout"]),
        ("这个脚本要从日志里统计 p95 latency，先在沙箱中试跑。", "日志已脱敏，禁止写回监控系统。", ["python", "metrics"]),
        ("验证一个 CSV 去重脚本对重复客户的处理结果，保留输入输出对照。", "不允许直接覆盖原始文件。", ["python", "csv"]),
        ("把模型评测小程序放到受限环境执行，比较两组 precision/recall。", "不使用 GPU 外的外部资源，不写入记忆。", ["python", "evaluation"]),
        ("运行这段 Python 代码前先确认它不会 import 未允许的包。", "需要列出沙箱策略和阻断风险。", ["python", "security"]),
        ("用临时 worker 复算用户分群，分群条件来自一段自然语言规则。", "结果只能作为建议，不能触发营销动作。", ["python", "segmentation"]),
        ("小心检查这段代码处理 NA、空字符串和零值的差异，输出可复核报告。", "执行环境要隔离，保留错误信息。", ["python", "data"]),
        ("我只需要确认一个 hash 计算函数的输出，不需要任何生产访问。", "在短超时 sandbox 中执行并记录结果。", ["python", "sandbox"]),
        ("把脱敏后的传感器样本喂给 Python 规则，判断是否触发异常阈值。", "不能把异常直接写入工单系统。", ["python", "anomaly"]),
        ("检查一个递归脚本在深层目录输入下会不会耗尽资源。", "沙箱必须有内存和时间预算。", ["python", "resource"]),
        ("验证付款对账的 decimal 计算，使用固定样例而不是线上账本。", "只生成差异清单，不执行修正。", ["python", "finance"]),
        ("跑一段包含中文路径的 Python 文件读取逻辑，确认编码处理。", "路径限定在临时 workspace。", ["python", "encoding"]),
        ("在隔离环境复现 pandas merge 后行数膨胀的问题，输出最小复现结果。", "不要访问外部数据库。", ["python", "debug"]),
        ("测试一个把 Markdown 转结构化 JSON 的小脚本。", "需要捕获异常和超时，禁止网络请求。", ["python", "parser"]),
        ("用 dry-run 计算库存补货建议，但不要真正创建采购单。", "执行结果需要说明资源限制和下一步审批。", ["python", "workflow"]),
        ("这段代码来自未知来源，先在 sandbox 中检查其文件和网络副作用。", "任何高风险访问都应被阻断并记录。", ["python", "security"]),
    ]
    for index, (objective, context, tags) in enumerate(code_cases, 1):
        tasks.append(_task(id=f"hh_code_{index:03d}", title=f"Holdout code case {index}", objective=objective, context=context, scenario="code", tool="python_sandbox_runner", risk="high", approval=True, tags=tags))

    analysis_cases = [
        ("这个月的销售表里哪个 SKU 的异常最大？我只知道文件叫 sales_east.csv。", "region,sku,amount,orders\n华东,A-17,1200,12\n华东,B-09,90,1\n华南,A-17,1100,11\n", "medium", False, ["csv", "anomaly"]),
        ("Look at the attached export and tell me whether refunds are driving the margin dip.", "date,product,revenue,refund,margin\n2026-08-01,Cloud,80,12,0.22\n2026-08-02,Cloud,70,30,0.10\n", "medium", False, ["csv", "margin"]),
        ("表里有日期和金额，但没有 product 列，先告诉我能不能定位最大异常产品。", "date,amount,orders\n2026-09-01,1200,14\n2026-09-02,1180,13\n", "medium", False, ["csv", "missing_field"]),
        ("同一个目录有 revenue.csv 和 revenue_corrected.csv，哪个才是昨天的输入我没说清楚。", "文件名和字段都存在，但不能猜选哪个。", "medium", False, ["csv", "ambiguous_input"]),
        ("帮我看一下运营数据，感觉北区掉得很奇怪，先找出字段质量和异常行。", "area,value,count\nNorth,NA,0\nSouth,82,7\nEast,77,6\n", "medium", False, ["csv", "quality"]),
        ("The spreadsheet has two date columns and the business day cutoff is not documented. Find suspicious records without inventing a date rule.", "event_time,settled_at,amount\n2026-09-10T23:50,2026-09-11T00:10,90\n", "medium", False, ["csv", "ambiguous_time"]),
        ("这张表的销售额字段有空值、中文逗号和重复行，先做画像再给异常提示。", "产品,销售额,订单数\nA,1,200,20\nB,,18\nB,800,18\n", "medium", False, ["csv", "quality"]),
        ("分析昨晚导出的 usage 数据，看看哪个租户的请求量跳变最大。", "tenant,requests,errors\nacme,100,2\nzen,980,90\n", "medium", False, ["csv", "usage"]),
        ("I have a table but no explicit revenue column; decide whether the available amount field is sufficient for anomaly analysis.", "customer,amount,quantity\nA,120,3\nB,130,2\n", "medium", False, ["csv", "schema"]),
        ("先比较本周和上周的渠道收入，不要因为标题写着 dashboard 就直接调用报表摘要工具。", "week,channel,revenue\nthis,web,1300\nlast,web,900\n", "medium", False, ["csv", "comparison"]),
        ("给我检查订单明细里缺失值、类型混乱和可能的离群点，输出结构化画像。", "order_id,created_at,total\n1,2026-09-12,100\n2,not-a-date,99999\n", "medium", False, ["csv", "quality"]),
        ("销售数据和退款数据需要一起看，先识别两个表是否能按 order_id 对齐。", "sales.csv: order_id,amount\nrefunds.csv: order_id,refund\n", "medium", False, ["csv", "join"]),
        ("这个报表显示转化率下滑，但原始 CSV 里只有 visits，没有 orders，先指出证据缺口。", "visits,date\n100,2026-09-01\n80,2026-09-02\n", "medium", False, ["csv", "evidence"]),
        ("检查库存快照里最可能是假异常的重复 SKU，别直接删除重复记录。", "sku,warehouse,stock\nA,WH1,10\nA,WH1,10\nB,WH2,0\n", "medium", False, ["csv", "duplicate"]),
        ("昨天的销量文件没有日期字段，我不想让系统猜昨天是哪一批。", "sku,sales\nP-1,20\nP-2,8\n", "medium", False, ["csv", "missing_field"]),
        ("Find the largest anomaly in the attached CSV, but note that the metric is called net_value in some rows and revenue in others.", "sku,net_value,revenue\nA,10,\nB,,900\n", "medium", False, ["csv", "schema"]),
        ("把广告投放、订单和退款三个 CSV 的字段画像先列出来，确认是否适合联合分析。", "campaign,clicks\norder_id,revenue\norder_id,refund\n", "medium", False, ["csv", "multi_file"]),
        ("我只上传了一张空表，帮我判断缺什么才能做异常分析。", "sku,revenue,orders\n", "medium", False, ["csv", "empty"]),
        ("分析物流时效的 p95 和缺失区域，先不要把异常结果回写到工单。", "region,delivery_hours\nEast,30\nWest,NA\nNorth,120\n", "medium", False, ["csv", "p95"]),
        ("The file has a metric column but no units. Profile it and list what must be clarified before comparing teams.", "team,metric\nA,10\nB,12\n", "medium", False, ["csv", "missing_context"]),
        ("收入异常达到阈值后可能触发财务审批，先做 CSV 画像和异常证据，不要执行付款动作。", "account,revenue,change\nA,10000,0.8\nB,300,0.1\n", "high", True, ["csv", "finance", "approval"]),
        ("对客户退款数据做异常检测，若确认批量退款需要业务审批，但本次只分析文件。", "customer,refund_count,refund_amount\nX,12,9000\nY,1,20\n", "high", True, ["csv", "customer", "approval"]),
        ("分析生产指标里的突增记录，并根据内部规则判断是否应该触发人工复核。", "service,error_rate,requests\napi,0.8,100\nweb,0.02,1000\n", "high", True, ["csv", "risk", "approval"]),
        ("跨表找出疑似重复付款，结果可能需要冻结账户；先画像、留证和等待审批。", "payment_id,account,amount\nP1,A,100\nP1,A,100\n", "high", True, ["csv", "finance", "approval"]),
        ("这个 CSV 可能含个人信息，先识别字段和缺失质量，再给出脱敏前的风险提示。", "user_id,email,amount\n1,a@example.com,80\n2,,90\n", "high", True, ["csv", "privacy", "approval"]),
        ("“帮我看看昨天那个文件”——文件确实存在，但有 daily.csv、daily_old.csv 两份。", "没有日期字段，也没有指定文件；请先请求澄清，不要挑一个继续分析。", "medium", False, ["csv", "ambiguous_input"]),
        ("销售数据里金额列叫 gmV，大小写和拼写都不统一，先判断能否可靠画像。", "sku,gmV,orders\nA,120,4\nB,NA,3\n", "medium", False, ["csv", "schema"]),
        ("我说的是‘退货最多的品’，但表里只有退款金额没有数量，先说明指标不能直接替代。", "product,refund_amount\nA,800\nB,200\n", "medium", False, ["csv", "evidence"]),
        ("分析一份带 BOM、中文列名和混合日期格式的导出文件，给出字段画像与异常候选。", "产品,日期,销售额\nA,2026/09/01,100\nB,09-02-2026,120\n", "medium", False, ["csv", "encoding"]),
        ("如果 North 的收入下降是数据缺失造成的，就不要生成业务结论；先找缺失字段和证据。", "region,revenue,orders\nNorth,,10\nSouth,1000,9\n", "medium", False, ["csv", "evidence"]),
    ]
    for index, (objective, context, risk, approval, tags) in enumerate(analysis_cases, 1):
        tasks.append(_task(id=f"hh_analysis_{index:03d}", title=f"Holdout analysis case {index}", objective=objective, context=context, scenario="analysis", tool="data_frame_profiler", risk=risk, approval=approval, tags=tags))

    external_cases = [
        ("Prepare an HTTP API plan to sync a subscription status; validate the schema and keep an idempotency key.", "The target is customer-visible, so do not mutate it directly.", ["http", "schema"]),
        ("把 CRM 里的客户等级同步到外部伙伴系统，先校验字段、幂等键和回滚方案。", "这是 customer-visible write，必须等待审批。", ["http", "crm"]),
        ("The webhook is only one implementation detail; I need a complete external API action plan with request validation.", "Include target system, scoped credential assumptions and approval checkpoint.", ["api", "schema"]),
        ("给第三方账单接口准备批量更新草案，注意不能把 webhook 通知当成完整同步。", "输出 schema、idempotency 和 rollback，不要真的写入。", ["http", "billing"]),
        ("用 API 把工单状态推送到供应商平台，先做 dry-run 和参数校验。", "客户可能看到状态变化，审批前禁止发送。", ["http", "workflow"]),
        ("Send a reversible CRM update plan, not a notification. The action must be idempotent and auditable.", "No direct write; a human must approve the customer-visible mutation.", ["http", "crm"]),
        ("外部库存系统需要接收 SKU 和数量，帮我检查 request schema 与重复提交风险。", "目标是同步数据，不是发一个简单 webhook。", ["http", "inventory"]),
        ("为合作方 API 生成一次性同步计划，字段不完整时应先停下来。", "不要猜缺失参数，也不要把通知工具当作同步工具。", ["http", "schema"]),
        ("The request mentions a callback, but the real goal is to update a remote work item with rollback metadata.", "Remote mutation remains in dry-run until approval.", ["http", "callback"]),
        ("把订单取消状态准备同步到支付平台，校验 cancellation reason 和 idempotency key。", "涉及退款可能性，必须人工审批。", ["http", "payment"]),
        ("外部 API 返回 schema 版本不确定，先比较兼容字段和失败重试边界。", "不要执行请求，只输出安全动作。", ["http", "schema"]),
        ("We need a batch API connector for partner onboarding, including scoped credentials and an audit record.", "A webhook notification alone is insufficient; customer data is involved.", ["http", "partner"]),
        ("给 CRM 建一个联系人同步的幂等 dry-run，失败时保留 request/response 摘要。", "必须过 approval gate，不能直接写入。", ["http", "crm"]),
        ("把仓库库存回写到第三方平台之前，先验证数量类型、版本号和重试策略。", "客户页面可能随之变化。", ["http", "inventory"]),
        ("Prepare an external billing update but do not send it; verify required fields and rollback semantics.", "The final action requires finance approval.", ["http", "billing"]),
        ("这个需求同时提到 webhook、通知和同步，真正目标是把工单字段更新到 vendor API。", "请选择完整 API connector，保留幂等与审计信息。", ["http", "vendor"]),
        ("接口调用需要把中文地址映射成 partner schema，先生成参数校验结果。", "不要在审批前调用第三方。", ["http", "schema"]),
        ("The external endpoint may return 409 on duplicate requests. Produce an idempotent action plan.", "No mutation before a human checkpoint.", ["http", "retry"]),
        ("给客户等级变更做远端同步准备，区分 notification from state mutation。", "需要说明审批对象和回滚动作。", ["http", "customer"]),
        ("把采购订单状态同步到供应商系统，先检查 API contract、版本和权限范围。", "不要把调用结果伪装成已完成。", ["http", "purchase"]),
        ("Prepare a schema-validated API request for a customer-visible entitlement change.", "The result should remain a dry-run and require approval.", ["http", "entitlement"]),
        ("外部数据同步任务没有给 endpoint 和字段映射，正确做法是请求补充，而不是猜。", "先输出缺失参数和审批要求。", ["http", "missing_args"]),
        ("The callback URL is known, but the payload contract and deduplication key are not.", "Stop before dispatch and list the missing API arguments.", ["http", "missing_args"]),
        ("给客户通知系统准备发送方案，但其中还包含更新客户偏好的动作。", "识别 mutation 和 notification 的边界，外部写入要审批。", ["http", "preference"]),
        ("把风控结果同步给合作方时，先检查隐私字段、schema 和 scoped credential。", "这是 high-risk external action，不能直接发送。", ["http", "privacy"]),
        ("Prepare a remote ticket update with a retry-safe request. The notification is only a side effect.", "Keep the action reversible and await approval.", ["http", "ticket"]),
        ("第三方接口的字段有旧版和新版两套，先做兼容性检查和 dry-run。", "不可直接切换生产版本。", ["http", "versioning"]),
        ("这个动作可能同时触发 webhook 和 CRM update，先拆出主动作、审批点和回滚计划。", "请不要只选通知工具。", ["http", "multi_step"]),
        ("Use the API to stage a refund status reconciliation, but do not execute the refund.", "Validate the request, idempotency and finance approval requirement.", ["http", "refund"]),
        ("外部客服系统同步客户投诉状态，要求记录 request schema、责任人和下一步。", "只做 dry-run，客户可见变更必须审批。", ["http", "support"]),
    ]
    for index, (objective, context, tags) in enumerate(external_cases, 1):
        tasks.append(_task(id=f"hh_external_api_{index:03d}", title=f"Holdout external API case {index}", objective=objective, context=context, scenario="external_api", tool="http_api_connector", risk="high", approval=True, tags=tags))

    if len(tasks) != 150:
        raise AssertionError(f"hard_holdout_v1 must contain 150 tasks, got {len(tasks)}")
    if len({task.id for task in tasks}) != len(tasks):
        raise AssertionError("hard_holdout_v1 task ids must be unique")
    return tasks


def _hard_distractors() -> tuple[ToolDefinition, ...]:
    return (
        *_distractor_tools(),
        ToolDefinition("policy_faq_search", "Policy FAQ search", "knowledge", "low", 340, 0.78, ("policy", "faq", "制度", "条款", "问答"), "Searches short policy FAQs without relationship expansion.", ("FAQ", "问答"), ("依赖拓扑", "关系链", "版本来源", "effective date")),
        ToolDefinition("incident_summary_reader", "Incident summary reader", "knowledge", "low", 360, 0.77, ("incident", "事故", "summary", "摘要", "故障"), "Reads incident summaries without expanding service ownership.", ("incident summary", "事故摘要"), ("依赖拓扑", "上下游", "owner mapping", "关系图")),
        ToolDefinition("workflow_form_submit", "Workflow form submit", "workflow", "medium", 420, 0.74, ("workflow", "form", "submit", "流程", "表单", "提交"), "Submits a form but does not manage controlled state transitions.", ("form submit", "表单提交"), ("approval gate", "人工确认", "审批节点", "checkpoint")),
        ToolDefinition("sla_reminder_bot", "SLA reminder bot", "workflow", "low", 280, 0.82, ("sla", "reminder", "提醒", "催办", "deadline"), "Sends reminders without changing workflow state.", ("reminder", "催办"), ("state transition", "状态流转", "客户可见", "审批节点")),
        ToolDefinition("csv_summary", "CSV summary", "analysis", "medium", 390, 0.76, ("csv", "summary", "销售", "收入", "摘要"), "Returns a shallow summary without field quality or anomaly profiling.", ("summary", "摘要", "概览"), ("字段画像", "结构化画像", "异常行", "缺失值", "schema quality")),
        ToolDefinition("data_quality_checker", "Data quality checker", "analysis", "medium", 360, 0.79, ("csv", "missing", "schema", "缺失", "字段", "质量"), "Checks schema quality but does not produce a complete data profile.", ("schema quality", "字段质量", "缺失检查"), ("异常分析", "趋势", "画像", "业务结论", "分群")),
        ToolDefinition("table_analyzer", "Table analyzer", "analysis", "medium", 440, 0.72, ("table", "analyze", "表", "分析", "指标"), "Analyzes tables without anomaly hints and structured summaries.", ("table analysis", "表分析"), ("字段画像", "异常行", "缺失值", "结构化画像")),
        ToolDefinition("notebook_runner", "Notebook runner", "code", "high", 520, 0.7, ("notebook", "代码", "计算", "run"), "Runs notebook cells without the constrained Python sandbox contract.", ("notebook", "notebook run"), ("python sandbox", "受限环境", "隔离环境", "资源限制")),
        ToolDefinition("event_publisher", "Event publisher", "external_api", "high", 470, 0.69, ("event", "publish", "通知", "事件", "发送"), "Publishes events without full request schema or idempotency handling.", ("event publish", "事件发送"), ("schema validation", "幂等键", "回滚方案", "状态 mutation")),
        ToolDefinition("crm_update_api", "CRM update API", "external_api", "high", 510, 0.73, ("crm", "customer", "客户", "update", "更新"), "Updates CRM records without the complete external action governance contract.", ("CRM update", "客户更新"), ("schema validation", "幂等键", "dry-run", "回滚方案")),
    )


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _summarize(results: list[dict[str, Any]], tasks: list[BenchmarkTask]) -> dict[str, Any]:
    failed = [result for result in results if not result["passed"]]
    high_risk = [task.id for task in tasks if task.requires_approval or task.risk_level == "high"]
    high_risk_results = [result for result in results if result["id"] in high_risk]
    taxonomy = Counter(_failure_taxonomy(result) for result in failed)
    return {
        "case_count": len(results),
        "passed": sum(1 for result in results if result["passed"]),
        "pass_rate": _ratio(sum(1 for result in results if result["passed"]), len(results)),
        "handled": sum(1 for result in results if result.get("handled", result["passed"])),
        "handled_rate": _ratio(sum(1 for result in results if result.get("handled", result["passed"])), len(results)),
        "scenario_accuracy": _ratio(sum(1 for result in results if result["scenario_ok"]), len(results)),
        "tool_top1": _ratio(sum(1 for result in results if result["tool_top1"]), len(results)),
        "tool_top3": _ratio(sum(1 for result in results if result["tool_top3"]), len(results)),
        "approval_accuracy": _ratio(sum(1 for result in results if result["approval_ok"]), len(results)),
        "trace_completeness": _ratio(sum(1 for result in results if result["trace_complete"]), len(results)),
        "high_risk_cases": len(high_risk_results),
        "high_risk_false_negatives": sum(1 for result in high_risk_results if not result["actual_approval"]),
        "failure_taxonomy": {name: taxonomy.get(name, 0) for name in ("Router", "Retrieval", "Tool Selection", "Argument", "Execution", "Evidence", "Approval")},
    }


def _task_payload(task: BenchmarkTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "objective": task.objective,
        "context": task.context,
        "expected_output": task.expected_output,
        "scenario_hint": task.scenario_hint,
        "priority": task.priority,
        "risk_level": task.risk_level,
        "requires_approval": task.requires_approval,
        "tags": task.tags,
        "expected_scenario": task.expected_scenario,
        "expected_tool": task.expected_tool,
        "expected_approval": task.expected_approval,
        "expected_contract_terms": task.expected_contract_terms,
    }


def run() -> dict[str, Any]:
    tasks = _build_tasks()
    tools = tuple(TOOLS) + _hard_distractors()
    results = [run_benchmark_case(task, tools=tools) for task in tasks]
    manifest_payload = json.dumps(
        [
            {
                "id": task.id,
                "title": task.title,
                "objective": task.objective,
                "context": task.context,
                "expected_scenario": task.expected_scenario,
                "expected_tool": task.expected_tool,
                "expected_approval": task.expected_approval,
                "tags": task.tags,
            }
            for task in tasks
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    by_scenario = {
        scenario: _summarize(
            [result for result in results if result["expected_scenario"] == scenario],
            [task for task in tasks if task.expected_scenario == scenario],
        )
        for scenario in SCENARIOS
    }
    return {
        "dataset": "hard_holdout_v1",
        "freeze_policy": "Created after Runtime freeze; failures must not be used for rule tuning.",
        "manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
        "case_count": len(tasks),
        "cases_per_scenario": 30,
        "tool_pool": len(tools),
        "hard_dimensions": [
            "similar_tool_interference",
            "partial_or_ambiguous_input",
            "cross_scenario_routing",
            "multi_step_dependency",
            "unseen_mixed_language_and_business_phrasing",
        ],
        "overall": _summarize(results, tasks),
        "by_scenario": by_scenario,
        "representative_failures": [
            {
                "id": result["id"],
                "taxonomy": _failure_taxonomy(result),
                "expected_tool": result["expected_tool"],
                "actual_tool": result["actual_tool"],
                "reason": result["failure_reason"],
            }
            for result in results
            if not result["passed"]
        ][:30],
        "cases": [_task_payload(task) for task in tasks],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen hard_holdout_v1 benchmark")
    parser.add_argument("--output", type=Path, default=Path("docs/hard-holdout-v1-results.json"))
    parser.add_argument("--cases-output", type=Path)
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report_payload = {key: value for key, value in report.items() if key != "cases"}
    report_payload["cases_file"] = (args.cases_output.name if args.cases_output else "cases.json")
    args.output.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cases_output = args.cases_output or args.output.parent / "cases.json"
    cases_output.parent.mkdir(parents=True, exist_ok=True)
    cases_output.write_text(json.dumps(report["cases"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
