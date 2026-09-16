"""Run the frozen, independently authored hard_holdout_v2 dataset.

The v2 cases are created after the capability-aware reranker was frozen. They
are intentionally separate from hard_holdout_v1 and are not used to tune the
runtime. The runner writes the task manifest separately from the result report
so the dataset can be reviewed and reproduced without hiding the raw cases.
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
from scripts.run_hard_holdout import _hard_distractors
from scripts.run_systematic_eval import _failure_taxonomy


SCENARIOS = ("knowledge", "workflow", "code", "analysis", "external_api")
CONTRACT_TERMS = ["工具", "理由", "风险", "审批", "证据", "下一步"]


def _task(
    *,
    scenario: str,
    index: int,
    objective: str,
    context: str,
    tool: str,
    risk: str,
    approval: bool,
    tags: list[str],
) -> BenchmarkTask:
    return BenchmarkTask(
        id=f"h2_{scenario}_{index:03d}",
        title=f"Hard Holdout v2 {scenario} case {index}",
        objective=objective,
        context=context,
        expected_output="结构化结果、工具选择理由、风险、审批、证据和下一步",
        scenario_hint=None,
        priority="high" if risk == "high" else "medium",
        risk_level=risk,
        requires_approval=approval,
        tags=["hard_holdout_v2", scenario, *tags],
        expected_scenario=scenario,
        expected_tool=tool,
        expected_approval=approval,
        expected_contract_terms=CONTRACT_TERMS,
    )


def _build_tasks() -> list[BenchmarkTask]:
    tasks: list[BenchmarkTask] = []

    knowledge_cases = [
        ("把 billing-api、ledger-worker 和客户门户之间的调用链展开，找出可能的共同上游。", "需要标出未验证的关系，不要把 incident 摘要当成拓扑。", "graph_neighbor_expand", "low", False, ["topology", "dependency"]),
        ("Which retention rule applies to archived customer exports, and where is the authoritative clause?", "There are a FAQ and a policy revision; preserve the source version and effective date.", "hybrid_knowledge_search", "low", False, ["policy", "version"]),
        ("查找服务 alpha 的 owner、值班组和最近三次变更之间的关系。", "只给关系证据和缺失边，不要修改事故单。", "graph_neighbor_expand", "low", False, ["owner", "incident"]),
        ("请从内部规范中核对模型生成代码是否允许访问生产凭据。", "可能存在中文制度和英文 security note，优先返回可引用原文。", "hybrid_knowledge_search", "low", False, ["security", "policy"]),
        ("The checkout timeout appears after a gateway release; expand dependencies across gateway, cache, and payment.", "Return service edges and responsible teams, not a generic troubleshooting article.", "graph_neighbor_expand", "low", False, ["dependency", "release"]),
        ("找一下夜间批处理失败后的恢复手册，并区分自动重试和人工确认步骤。", "如果手册版本冲突，输出冲突证据。", "hybrid_knowledge_search", "low", False, ["runbook", "recovery"]),
        ("登录异常同时影响 mobile 和 web，沿身份服务和权限服务找共同依赖。", "需要多跳关系，不要只检索‘登录失败’的 FAQ。", "graph_neighbor_expand", "low", False, ["multi-hop", "identity"]),
        ("Find the approved wording for a customer-visible data correction and its audit requirement.", "Do not propose an external write; cite the policy and applicable scope.", "hybrid_knowledge_search", "low", False, ["policy", "audit"]),
        ("服务 mesh 上有一个孤立的 consumer，判断它是否仍被订单流程引用。", "输出调用方、owner 和最近运行记录的关系链。", "graph_neighbor_expand", "low", False, ["graph", "consumer"]),
        ("核对个人信息脱敏、保留期限和删除申请的制度依据。", "不要把搜索结果解释成已经批准的删除动作。", "hybrid_knowledge_search", "low", False, ["privacy", "retention"]),
        ("把数据湖 ingestion、schema registry 和报表任务串起来，找出字段变更的影响面。", "输出上下游和变更证据。", "graph_neighbor_expand", "low", False, ["data-lineage", "schema"]),
        ("请检索‘紧急发布’在周末是否允许，以及必须留下哪些审计字段。", "同时存在旧版 SOP 和新版 policy，保留有效版本。", "hybrid_knowledge_search", "low", False, ["release", "sop"]),
        ("Why did the recommendation job fan out after the feature flag change? Trace the relevant service relationships.", "Focus on graph expansion and owner mapping, not a policy answer.", "graph_neighbor_expand", "low", False, ["feature-flag", "root-cause"]),
        ("找出供应商接入流程中关于凭据范围、轮换和审批人的原始条款。", "需要文档证据，不要调用外部接口。", "hybrid_knowledge_search", "low", False, ["credential", "approval"]),
        ("将 incident INC-9912 关联到受影响的 API、队列和发布批次。", "如果关系只有推断，必须标成待验证。", "graph_neighbor_expand", "low", False, ["incident", "impact"]),
        ("从知识库确认异步任务重复消费时的幂等处理规范。", "返回 policy、runbook 和适用边界，不要发送 webhook。", "hybrid_knowledge_search", "low", False, ["idempotency", "runbook"]),
        ("订单状态延迟可能来自 queue、worker 或 partner adapter，展开这三个节点的关系。", "按证据解释共同上游和责任团队。", "graph_neighbor_expand", "low", False, ["queue", "adapter"]),
        ("请找出客服工单升级到法务前需要满足的条件。", "输出制度原文和不确定项，不能直接推进工单。", "hybrid_knowledge_search", "low", False, ["legal", "policy"]),
        ("Map the owners and dependencies behind the nightly finance reconciliation pipeline.", "The goal is a relationship graph; do not summarize the finance policy.", "graph_neighbor_expand", "low", False, ["finance", "pipeline"]),
        ("核对发布回滚、数据库迁移和客户通知之间的操作边界。", "优先检索有效 runbook，标出需要人工确认的步骤。", "hybrid_knowledge_search", "low", False, ["rollback", "customer"]),
        ("某个 API 的延迟只在 eu-west 上升，沿 region、gateway、cache 和 owner 展开关系。", "不要凭一个指标直接下根因结论。", "graph_neighbor_expand", "low", False, ["region", "latency"]),
        ("查找内部关于‘自动化只能 dry-run’的规范，并给出适用的风险等级。", "只要证据和下一步，不要执行动作。", "hybrid_knowledge_search", "low", False, ["dry-run", "risk"]),
        ("把 feature team、服务 owner 和最近变更单连起来，确认谁负责 catalog-api。", "需要跨实体关系和证据来源。", "graph_neighbor_expand", "low", False, ["team", "change"]),
        ("The incident notes mention a manual override. Retrieve the governing procedure and escalation boundary.", "Return citations and clarify which source is authoritative.", "hybrid_knowledge_search", "low", False, ["override", "procedure"]),
        ("分析平台的 ingestion job、对象存储和下游 dashboard 之间是否存在断链。", "目标是关系扩展，不是生成 dashboard 摘要。", "graph_neighbor_expand", "low", False, ["lineage", "dashboard"]),
        ("找‘供应商数据导出’的授权、留痕和过期要求。", "中文和英文资料可能重复，合并来源但保留版本。", "hybrid_knowledge_search", "low", False, ["export", "authorization"]),
        ("把订单取消、退款服务和财务审批节点的关系展开。", "只解释实体关系和证据缺口，不触发退款。", "graph_neighbor_expand", "low", False, ["refund", "approval"]),
        ("请检索 API key 泄露后的处置手册和通知边界。", "不要把 incident_summary 当成完整恢复方案。", "hybrid_knowledge_search", "low", False, ["secret", "recovery"]),
        ("service-a 调用 service-b 后又经过两个队列，找出每一跳的 owner。", "需要多跳 expansion 和未确认边。", "graph_neighbor_expand", "low", False, ["multi-hop", "owner"]),
        ("What is the approved exception process for a blocked deployment?", "Compare the policy clause with the operator runbook and cite both if they differ.", "hybrid_knowledge_search", "low", False, ["exception", "deployment"]),
        ("查一下营销任务、客户画像服务和数据权限组之间的依赖关系。", "输出影响面，不要把客户资料写入记忆。", "graph_neighbor_expand", "low", False, ["marketing", "access"]),
        ("从制度中核对跨境数据处理是否需要额外审批和留痕。", "只返回证据、版本和需要补充的信息。", "hybrid_knowledge_search", "low", False, ["cross-border", "compliance"]),
    ]
    for index, (objective, context, tool, risk, approval, tags) in enumerate(knowledge_cases, 1):
        tasks.append(_task(scenario="knowledge", index=index, objective=objective, context=context, tool=tool, risk=risk, approval=approval, tags=tags))

    workflow_cases = [
        ("把采购请求从 submitted 推进到 buyer_review，并保留审批 owner。", "这是状态流转，不代表已经批准采购。", "workflow_state_transition", "medium", False, ["state", "procurement"]),
        ("将一个客户可见的套餐变更停在人工 checkpoint，先列出回滚条件。", "不能直接更新生产状态。", "approval_gate", "high", True, ["approval", "customer"]),
        ("Move the incident from triage to assigned and attach the next on-call checkpoint.", "Do not close the incident or mark the remediation approved.", "workflow_state_transition", "medium", False, ["handoff", "incident"]),
        ("批量将过期合同标记为待复核，先确认法务 owner 和审计字段。", "本次只推进到 review，不执行终止。", "workflow_state_transition", "medium", False, ["review", "legal"]),
        ("把线上 feature flag 从 5% 扩到 50%，先创建人工审批关卡。", "客户流量会受到影响，输出 dry-run。", "approval_gate", "high", True, ["production", "gate"]),
        ("Assign the unresolved support queue to the regional owner and record an SLA checkpoint.", "This changes workflow ownership only; it is not a customer-visible write.", "workflow_state_transition", "medium", False, ["owner", "sla"]),
        ("准备清理积压消息，动作可能丢失客户事件，先拦截并等待 SRE 确认。", "不要把删除动作当普通队列状态更新。", "approval_gate", "high", True, ["destructive", "sre"]),
        ("把研发任务从 in_progress 改成 blocked，并记录阻塞原因和下一位负责人。", "只变更流程状态，不提交代码。", "workflow_state_transition", "medium", False, ["blocked", "handoff"]),
        ("The release is ready for production, but a human must approve the customer-impacting rollout.", "Prepare the checkpoint and rollback evidence, do not transition the release itself.", "approval_gate", "high", True, ["release", "rollback"]),
        ("给退款申请加上 finance_review 节点，保留发起人和金额范围。", "状态推进不等于退款执行。", "workflow_state_transition", "medium", False, ["finance", "state"]),
        ("跨区域切换值班组会改变告警责任，先申请 owner 确认再执行。", "输出 approval checkpoint，不要直接换班。", "approval_gate", "high", True, ["on-call", "owner"]),
        ("将服务请求转派给数据平台队列并设置 due date。", "这是常规 handoff，不能误判为审批。", "workflow_state_transition", "medium", False, ["handoff", "queue"]),
        ("把订单批量状态从 packed 改为 shipped，客户会立即看到，先停在审批。", "需要业务 owner 确认和回滚策略。", "approval_gate", "high", True, ["customer-visible", "batch"]),
        ("将 access request 从 draft 推到 security_review，并关联申请人。", "不要授予权限本身。", "workflow_state_transition", "medium", False, ["security", "state"]),
        ("暂停一个自动化规则的生产启用，要求产品和安全共同确认。", "该动作影响线上行为，保留 gate 和审计说明。", "approval_gate", "high", True, ["automation", "production"]),
        ("把数据修复单移到 validation 阶段，附上验证负责人和截止时间。", "不要写入修复结果。", "workflow_state_transition", "medium", False, ["validation", "owner"]),
        ("The customer success team asks to reopen all closed tickets in a region.", "This bulk operation needs a human checkpoint before any customer-facing mutation.", "approval_gate", "high", True, ["bulk", "mutation"]),
        ("将项目里程碑从 planned 改为 active，补充负责人和下一次检查点。", "只是项目状态流转。", "workflow_state_transition", "medium", False, ["milestone", "checkpoint"]),
        ("删除无效的生产队列会影响未处理请求，先生成高风险审批节点。", "不要执行 delete，也不要只更新队列状态。", "approval_gate", "high", True, ["delete", "queue"]),
        ("把审批申请分派给指定 reviewer，并更新 due date。", "分派 reviewer 不代表批准结果。", "workflow_state_transition", "medium", False, ["reviewer", "handoff"]),
        ("A vendor migration will alter live routing; pause at an approval gate and show rollback criteria.", "No state mutation before the service owner signs off.", "approval_gate", "high", True, ["migration", "routing"]),
        ("把客服工单从 waiting_customer 推进到 agent_review，记录 SLA 计时。", "不要发送客户通知。", "workflow_state_transition", "medium", False, ["support", "sla"]),
        ("将一批高优先级告警静音 30 分钟，先等待值班主管审批。", "这是有风险的生产控制动作。", "approval_gate", "high", True, ["alert", "mute"]),
        ("Move the data request to privacy_review and attach the data steward as owner.", "Do not approve or export any data in this step.", "workflow_state_transition", "medium", False, ["privacy", "review"]),
        ("把支付对账任务标记为 needs_attention 并转给财务队列。", "只做受控状态转换。", "workflow_state_transition", "medium", False, ["reconciliation", "finance"]),
        ("准备将客户等级大批量改为 premium，先拦截并要求业务负责人确认。", "客户页面会即时变化，不能直接更新。", "approval_gate", "high", True, ["tier", "customer"]),
        ("将实验任务从 queued 推进到 running，记录启动人和预算限制。", "这不涉及外部写入。", "workflow_state_transition", "medium", False, ["experiment", "state"]),
        ("切换主备数据库会产生不可逆影响，先创建审批关卡并列出回滚条件。", "不要执行 failover。", "approval_gate", "high", True, ["database", "failover"]),
        ("把招聘申请交接给下一位面试官，补充 handoff note 和截止时间。", "不要把交接误判成 offer 审批。", "workflow_state_transition", "medium", False, ["handoff", "recruiting"]),
        ("批量关闭疑似重复工单前，先判断是否需要主管确认。", "客户可见记录会被改变，只能停在人工 gate。", "approval_gate", "high", True, ["duplicate", "customer"]),
        ("将变更单从 implementation 推进到 verification，关联验证人。", "不发布变更，不执行外部 API。", "workflow_state_transition", "medium", False, ["change", "verification"]),
        ("把高风险数据导出请求停在审批节点，列出数据范围、owner 和审计要求。", "输出 checkpoint，不生成下载链接。", "approval_gate", "high", True, ["export", "audit"]),
    ]
    for index, (objective, context, tool, risk, approval, tags) in enumerate(workflow_cases, 1):
        tasks.append(_task(scenario="workflow", index=index, objective=objective, context=context, tool=tool, risk=risk, approval=approval, tags=tags))

    code_cases = [
        ("在隔离 Python 环境里复现一个 timezone 转换错误，输出最小样例。", "禁止网络和生产文件访问，保留 traceback。", ["python", "debug"]),
        ("Run a small pandas transform over a provided sample and capture stdout.", "Use a time and memory budget; do not load files outside the workspace.", ["python", "pandas"]),
        ("检查一段未知 Python 脚本是否尝试读取环境变量和发起网络请求。", "先 dry-run，风险行为需要被阻断并记录。", ["python", "security"]),
        ("用 sandbox 验证金额四舍五入和 decimal 精度，生成差异表。", "只使用固定输入，不连接线上账本。", ["python", "finance"]),
        ("将一小段 JSON 清洗代码放入受限 worker 执行，检查空字段处理。", "需要超时、内存限制和异常摘要。", ["python", "json"]),
        ("Reproduce a merge-key duplication issue using two in-memory tables.", "The runner must be isolated and must not write the original datasets.", ["python", "reproduce"]),
        ("运行一个 Markdown 到 JSON 的解析器并验证 schema 错误。", "禁止安装包和访问网络，输出可审计结果。", ["python", "parser"]),
        ("用 Python 计算一组脱敏日志的 p95 延迟和异常值。", "只允许读取输入字符串，记录资源预算。", ["python", "metrics"]),
        ("Test a retry backoff function with deterministic timestamps.", "Use the constrained sandbox; no external clock or network calls.", ["python", "testing"]),
        ("在临时目录内执行 CSV 编码检测脚本，比较 UTF-8 和 GBK 输入。", "不要覆盖输入文件。", ["python", "encoding"]),
        ("检查一个递归遍历脚本在深层目录下是否会超时。", "沙箱需要限制路径、时间和内存。", ["python", "resource"]),
        ("用受限 Python 计算库存安全线，只输出建议，不创建采购单。", "说明 dry-run 边界和资源限制。", ["python", "inventory"]),
        ("Execute a pure function that maps event names to normalized categories.", "No file, process, or network side effects are allowed.", ["python", "pure-function"]),
        ("复现一个日期解析对中文月份失败的问题，并保存输入输出对照。", "不要访问系统 locale 或外部服务。", ["python", "locale"]),
        ("用 sandbox 比较两个评分函数，输出 precision、recall 和边界样例。", "固定数据集，禁止写入评测结果库。", ["python", "evaluation"]),
        ("审查一段用户提交的 Python 代码并在隔离环境中试运行安全子集。", "任何 import、文件或网络副作用都要记录。", ["python", "untrusted"]),
        ("验证一个把嵌套对象展平为表格的函数。", "输入规模很小，要求捕获异常和超时。", ["python", "transform"]),
        ("Run a deterministic checksum calculation for uploaded text.", "The sandbox must not access credentials or the host filesystem.", ["python", "checksum"]),
        ("在临时 worker 里执行对账规则，找出输入两侧的差异。", "只生成报告，不自动修正账本。", ["python", "reconcile"]),
        ("测试一个将异常栈按模块聚合的脚本。", "网络关闭，输出包含错误样例和资源消耗。", ["python", "traceback"]),
        ("Compute a cohort retention table from an in-memory list.", "Use the Python sandbox and preserve the exact input/output contract.", ["python", "cohort"]),
        ("用 Python 判断订单金额是否满足一组规则，保留每条规则的命中原因。", "不能调用 CRM，也不能改变订单状态。", ["python", "rules"]),
        ("验证 CSV 行拆分器对引号、换行和中文逗号的处理。", "运行在隔离环境，捕获解析失败。", ["python", "csv"]),
        ("Run a small Monte Carlo sample to check a confidence interval implementation.", "Fixed seed, bounded iterations, no external resources.", ["python", "statistics"]),
        ("检查一个清理临时文件的脚本会不会越出 workspace 边界。", "只做安全 dry-run，禁止真实删除。", ["python", "filesystem"]),
        ("用沙箱复现模型输出 JSON 偶尔缺少字段的问题。", "需要记录输入、异常和恢复建议。", ["python", "schema"]),
        ("Validate a text tokenizer on mixed Chinese and English examples.", "No model download or network access; capture deterministic output.", ["python", "text"]),
        ("在内存数据上计算分组均值并检查空组行为。", "不写入数据库，提供资源上限。", ["python", "groupby"]),
        ("用受限环境测试一段 YAML 转 JSON 的小程序。", "禁止读取用户目录，异常要可回放。", ["python", "yaml"]),
        ("Test whether a parser handles malformed UTF-8 without crashing the worker.", "Keep the input local and record timeout and memory behavior.", ["python", "robustness"]),
        ("用 Python 生成一份脱敏后的字段映射建议，不能直接上传原始数据。", "只运行规则，不调用外部 API。", ["python", "privacy"]),
        ("执行一个固定样例的路由评分函数，比较候选工具的排序差异。", "只允许纯计算，不修改 Runtime 配置。", ["python", "ranking"]),
    ]
    for index, (objective, context, tags) in enumerate(code_cases, 1):
        tasks.append(_task(scenario="code", index=index, objective=objective, context=context, tool="python_sandbox_runner", risk="high", approval=True, tags=tags))

    analysis_cases = [
        ("这份门店表里哪类商品的退货率异常，但文件没有明确的业务日定义。", "store,category,orders,returns\nA,home,80,9\nB,tech,40,12\n", "medium", False, ["csv", "business-day"]),
        ("Compare the two uploaded extracts and tell me whether the revenue drop is a real change or a schema mismatch.", "left: date,net_sales\nright: date,gross_sales\n", "medium", False, ["csv", "schema"]),
        ("只有客户编号和金额，没有时间字段，能不能判断本周异常？先说明证据缺口。", "customer,amount\nC1,200\nC2,220\n", "medium", False, ["csv", "missing-field"]),
        ("文件夹里有 inventory_latest.csv 和 inventory_backup.csv，我没有指定使用哪一个。", "两个文件都能解析；请先澄清，不要自行挑选。", "medium", False, ["csv", "ambiguous-file"]),
        ("先做一份带中文列名的物流数据画像，找出缺失、类型和极端值。", "地区,订单号,时长小时\n华东,O-1,12\n华南,O-2,NA\n", "medium", False, ["csv", "profile"]),
        ("The table contains sessions and purchases but no user identifier; assess whether cohort analysis is defensible.", "date,sessions,purchases\n2026-09-01,100,8\n2026-09-02,90,7\n", "medium", False, ["csv", "cohort"]),
        ("检查支付明细里的重复 transaction_id、负数金额和空币种。", "transaction_id,amount,currency\nT1,90,CNY\nT1,90,CNY\nT2,-5,\n", "medium", False, ["csv", "quality"]),
        ("分析设备错误率的波动，先判断 error_count 和 request_count 是否足够。", "device,error_count,request_count\nA,4,100\nB,20,\n", "medium", False, ["csv", "metric"]),
        ("I need the most suspicious supplier, but the export has supplier_name in one file and supplier_id in another.", "supplier_name,amount\nX,100\nsupplier_id,amount\nS2,900\n", "medium", False, ["csv", "multi-file"]),
        ("表里只有曝光和点击，没有转化列，先给出可以和不能得出的结论。", "campaign,impressions,clicks\nA,1000,30\nB,800,20\n", "medium", False, ["csv", "evidence"]),
        ("Find outliers in a sensor export where the unit column is missing.", "sensor,reading\nS1,12\nS2,1200\n", "medium", False, ["csv", "unit"]),
        ("这个 Excel 导出的 CSV 可能把小数逗号和字段分隔符混在一起，先做可解析性和画像检查。", "产品;销售额;数量\nA;1,200;4\nB;900;2\n", "medium", False, ["csv", "delimiter"]),
        ("比较两个地区的退款金额，但不确定是否使用同一币种。", "region,refund_amount,currency\nEast,100,CNY\nWest,80,USD\n", "medium", False, ["csv", "currency"]),
        ("分析订单时延的 p99，先识别 timestamp 是否存在跨时区问题。", "order_id,created_at,completed_at\n1,2026-09-14T23:00+08:00,2026-09-15T01:00+08:00\n", "medium", False, ["csv", "timestamp"]),
        ("这张表的异常值可能来自重复导入，先画像并列出重复键，不要删除数据。", "key,value,loaded_at\nK1,10,1\nK1,10,2\nK2,12,1\n", "medium", False, ["csv", "duplicate"]),
        ("The report says conversion fell, but it only includes completed_orders and omits visits.", "date,completed_orders\n2026-09-10,12\n2026-09-11,9\n", "medium", False, ["csv", "evidence"]),
        ("给我分析库存周转，但文件只有 sku、stock 和一个不明含义的 score 字段。", "sku,stock,score\nA,10,0.4\nB,3,0.9\n", "medium", False, ["csv", "ambiguous-metric"]),
        ("多张 CSV 的列名大小写不一致，先判断能否安全合并并报告字段差异。", "north: OrderID,Amount\nsouth: order_id,amount\n", "medium", False, ["csv", "join"]),
        ("Look for suspicious margin records, but the file has gross_profit and margin_pct with different coverage.", "product,gross_profit,margin_pct\nA,100,\nB,,0.3\n", "medium", False, ["csv", "coverage"]),
        ("这份用户活跃数据包含 email，先做字段画像和隐私风险提示，不输出业务排名。", "user_id,email,active_days\n1,a@example.com,4\n2,,1\n", "high", True, ["csv", "privacy"]),
        ("收入异常可能导致暂停结算，但本次只需要画像、证据和审批建议。", "account,amount,delta\nA,90000,0.8\nB,100,0.1\n", "high", True, ["csv", "finance"]),
        ("分析退款集中度，结果可能触发冻结账户，请先停在人工复核。", "account,refunds,orders\nA,20,2\nB,1,50\n", "high", True, ["csv", "risk"]),
        ("这个生产错误率表会被用于是否回滚的决定，先做数据质量和异常画像。", "service,error_rate,window\napi,0.8,5m\nweb,,5m\n", "high", True, ["csv", "production"]),
        ("If the export contains personal identifiers, profile the fields and surface the approval boundary before sharing.", "id,email,region\n1,x@example.com,East\n", "high", True, ["csv", "privacy"]),
        ("我说‘最近销量’，但文件没有日期字段；请列出必须补充的信息。", "sku,units\nA,20\nB,10\n", "medium", False, ["csv", "clarification"]),
        ("同一目录有三份 campaign export，目标日期和文件名都不明确。", "campaign files: c1.csv, c2.csv, c2_fixed.csv\n", "medium", False, ["csv", "ambiguous-file"]),
        ("金额字段有 CNY、USD 和空值，先判断哪些比较需要汇率证据。", "account,amount,currency\nA,100,CNY\nB,100,USD\nC,90,\n", "medium", False, ["csv", "currency"]),
        ("Analyze latency spikes when the baseline window is not provided.", "service,p95_ms\napi,400\nweb,80\n", "medium", False, ["csv", "missing-context"]),
        ("先看会员留存数据是否有 user_id、signup_date 和 activity_date，再谈 cohort。", "user_id,signup_date\nU1,2026-09-01\nU2,2026-09-02\n", "medium", False, ["csv", "cohort"]),
        ("这份表中的 product_code 有前导零，先确认解析是否会破坏标识符。", "product_code,qty\n0012,4\n0013,7\n", "medium", False, ["csv", "type"]),
        ("检查带 BOM 的中文导出和混合日期格式，输出画像与需要人工确认的字段。", "产品,日期,金额\nA,2026/9/1,100\nB,09-02-2026,120\n", "medium", False, ["csv", "encoding"]),
        ("如果北区缺失率超过阈值可能需要数据 owner 复核，先输出质量证据。", "region,field,missing_rate\nNorth,phone,0.9\nSouth,phone,0.1\n", "high", True, ["csv", "approval"]),
    ]
    for index, (objective, context, risk, approval, tags) in enumerate(analysis_cases, 1):
        tasks.append(_task(scenario="analysis", index=index, objective=objective, context=context, tool="data_frame_profiler", risk=risk, approval=approval, tags=tags))

    external_cases = [
        ("为供应商库存接口准备一个幂等同步 dry-run，先校验 SKU、数量和版本字段。", "不要发送请求，客户可见写入需要审批。", ["schema", "inventory"]),
        ("Prepare a customer entitlement update through an external API, with rollback and scoped credentials.", "Keep it in dry-run until the owner approves the mutation.", ["api", "entitlement"]),
        ("这个需求提到 webhook，但实际要更新 partner ticket 的状态和负责人。", "请输出完整 API contract，不要只选通知动作。", ["ticket", "webhook"]),
        ("同步 CRM 的联系人标签，先检查字段映射、重复提交和权限范围。", "客户资料写入必须等待人工确认。", ["crm", "idempotency"]),
        ("The billing endpoint has two schema versions; compare compatibility before staging the update.", "No remote mutation before finance approval.", ["billing", "version"]),
        ("把退货状态同步给支付合作方，生成 request schema、幂等键和回滚计划。", "只做 dry-run，可能触发财务动作。", ["refund", "payment"]),
        ("外部 API 返回 409 时需要安全重试，先设计去重和 request/response 审计。", "不要真的重放请求。", ["retry", "audit"]),
        ("Prepare a vendor onboarding API plan when the endpoint and credential scope are known.", "Validate required fields and stop at the approval checkpoint.", ["partner", "credential"]),
        ("将订单发货状态同步到供应商系统，先验证 order_id、status 和幂等策略。", "客户可能看到变化，禁止直接写入。", ["order", "schema"]),
        ("这个接口只给了 callback URL，没有 payload contract 和 dedup key。", "正确做法是列出缺失参数，不要猜测并发送。", ["missing", "callback"]),
        ("把客户分群结果同步到外部营销平台前，先检查隐私字段和授权范围。", "只输出安全动作计划。", ["privacy", "marketing"]),
        ("The remote work item should be updated, while the notification is only a secondary effect.", "Use schema validation and preserve a reversible dry-run.", ["work-item", "notification"]),
        ("给 ERP 准备采购订单状态更新，需校验版本号、字段类型和回滚边界。", "生产写入必须审批。", ["erp", "purchase"]),
        ("外部库存服务可能把同一 batch 重复处理，生成幂等 action plan。", "不要执行，只保留请求摘要。", ["inventory", "batch"]),
        ("Prepare a reversible CRM address correction with an explicit audit record.", "The update is customer-visible and requires human approval.", ["crm", "address"]),
        ("同步供应商发票状态时，先比较旧版和新版 schema 的必填字段。", "不要将验证结果伪装成已写入。", ["invoice", "schema"]),
        ("这个动作包含通知、客户等级变更和审计记录，先拆出主 mutation 和审批点。", "禁止审批前调用第三方。", ["multi-step", "customer"]),
        ("The endpoint may time out after accepting a request; design idempotent retry semantics.", "No dispatch, only a governed API plan.", ["timeout", "retry"]),
        ("把客服投诉状态同步到外部 case system，检查责任人和状态枚举映射。", "仅做 dry-run，客户可见变更需要审批。", ["support", "mapping"]),
        ("外部账单服务要求金额、币种和 customer_ref，先做参数契约验证。", "财务审批前不能写入。", ["billing", "finance"]),
        ("Prepare an API call to stage a subscription pause, including an idempotency key.", "The action must remain reversible and pending approval.", ["subscription", "reversible"]),
        ("远端系统要求 signed request，但当前没有 credential scope，先暂停并列出缺口。", "不要自行生成凭据或发送请求。", ["credential", "missing"]),
        ("把仓库库存变更同步给 partner，区分 webhook 通知和状态 mutation。", "选择完整 API connector 并说明审批边界。", ["webhook", "mutation"]),
        ("The external API returns a new enum value not present in our schema.", "Compare compatibility and recovery steps; do not send a production update.", ["schema", "compatibility"]),
        ("把风控决策摘要发送给合作方，先识别是否包含个人信息和客户可见字段。", "高风险外部动作只能 dry-run。", ["risk", "privacy"]),
        ("给外部工单系统准备批量标签更新，检查 batch size、失败重试和幂等性。", "审批前不创建或更新工单。", ["ticket", "batch"]),
        ("Prepare a partner API reconciliation plan when source and target IDs do not align.", "List the missing mapping and keep the remote action unexecuted.", ["reconcile", "mapping"]),
        ("接口响应可能包含敏感字段，先说明 scoped credential、日志脱敏和审计策略。", "不要调用接口。", ["security", "logging"]),
        ("同步客户服务等级到第三方平台，先验证 state transition 是否允许回滚。", "客户页面会变化，必须人工批准。", ["customer", "rollback"]),
        ("The request mentions an event callback but needs a remote record update with a version check.", "Treat the callback as a side effect and stage the governed API action.", ["callback", "version"]),
        ("外部支付接口需要 cancellation_reason，但当前输入缺少该字段。", "先请求补充参数，不执行退款或取消。", ["payment", "missing"]),
        ("把仓库补货状态回写给供应商，保留 request、response 摘要和审计 owner。", "只做 dry-run，并等待业务审批。", ["replenishment", "audit"]),
    ]
    for index, (objective, context, tags) in enumerate(external_cases, 1):
        tasks.append(_task(scenario="external_api", index=index, objective=objective, context=context, tool="http_api_connector", risk="high", approval=True, tags=tags))

    if len(tasks) != 160:
        raise AssertionError(f"hard_holdout_v2 must contain 160 tasks, got {len(tasks)}")
    if len({task.id for task in tasks}) != len(tasks):
        raise AssertionError("hard_holdout_v2 task ids must be unique")
    return tasks


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


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


def _summarize(results: list[dict[str, Any]], tasks: list[BenchmarkTask]) -> dict[str, Any]:
    failed = [result for result in results if not result["passed"]]
    high_risk_results = [
        result
        for result in results
        if any(task.id == result["id"] and (task.requires_approval or task.risk_level == "high") for task in tasks)
    ]
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


def run() -> dict[str, Any]:
    tasks = _build_tasks()
    tools: tuple[ToolDefinition, ...] = tuple(TOOLS) + tuple(_hard_distractors())
    results = [run_benchmark_case(task, tools=tools) for task in tasks]
    manifest_payload = json.dumps(
        [_task_payload(task) for task in tasks],
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
        "dataset": "hard_holdout_v2",
        "freeze_policy": "Authored after capability-aware reranker freeze; results are not used for tuning this Runtime.",
        "manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
        "case_count": len(tasks),
        "cases_per_scenario": {
            scenario: sum(1 for task in tasks if task.expected_scenario == scenario)
            for scenario in SCENARIOS
        },
        "tool_pool": len(tools),
        "hard_dimensions": [
            "similar_tool_interference",
            "precondition_and_missing_input",
            "cross_scenario_routing",
            "multi_step_dependency",
            "unseen_mixed_language_and_business_phrasing",
            "abstention_and_safe_recovery",
        ],
        "overall": _summarize(results, tasks),
        "by_scenario": by_scenario,
        "representative_failures": [
            {
                "id": result["id"],
                "taxonomy": _failure_taxonomy(result),
                "expected_tool": result["expected_tool"],
                "actual_tool": result["actual_tool"],
                "top3_tools": result["top3_tools"],
                "reason": result["failure_reason"],
            }
            for result in results
            if not result["passed"]
        ][:40],
        "cases": [_task_payload(task) for task in tasks],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen hard_holdout_v2 benchmark")
    parser.add_argument("--output", type=Path, default=Path("docs/hard-holdout-v2-results.json"))
    parser.add_argument("--cases-output", type=Path)
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report_payload = {key: value for key, value in report.items() if key != "cases"}
    cases_output = args.cases_output or args.output.parent / "cases.json"
    report_payload["cases_file"] = cases_output.name
    args.output.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cases_output.parent.mkdir(parents=True, exist_ok=True)
    cases_output.write_text(json.dumps(report["cases"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
