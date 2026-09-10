export function formatPercent(value: number) {
  return Math.round(value * 100) + "%"
}

export function formatScore(value: number) {
  return value.toFixed(2)
}

export function statusClass(status: string) {
  const map: Record<string, string> = {
    succeeded: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    recovered: "border-cyan-500/40 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300",
    needs_human: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
    failed: "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
    running: "border-blue-500/40 bg-blue-500/10 text-blue-700 dark:text-blue-300",
    new: "border-slate-500/40 bg-slate-500/10 text-slate-700 dark:text-slate-300",
    draft: "border-slate-500/40 bg-slate-500/10 text-slate-700 dark:text-slate-300",
    ready: "border-violet-500/40 bg-violet-500/10 text-violet-700 dark:text-violet-300",
    needs_approval: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
    completed: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  }
  return map[status] ?? "border-border bg-secondary text-secondary-foreground"
}

export function statusLabel(status?: string | null) {
  const map: Record<string, string> = {
    succeeded: "成功",
    recovered: "已恢复",
    needs_human: "需人工处理",
    failed: "失败",
    running: "运行中",
    new: "新建",
    draft: "草稿",
    ready: "就绪",
    needs_approval: "需审批",
    completed: "已完成",
  }
  return status ? (map[status] ?? status) : "未知"
}

export function priorityClass(priority: string) {
  const map: Record<string, string> = {
    critical: "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
    high: "border-orange-500/40 bg-orange-500/10 text-orange-700 dark:text-orange-300",
    medium: "border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-300",
    low: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  }
  return map[priority] ?? "border-border bg-secondary text-secondary-foreground"
}

export function priorityLabel(priority?: string | null) {
  const map: Record<string, string> = {
    critical: "紧急",
    high: "高",
    medium: "中",
    low: "低",
  }
  return priority ? (map[priority] ?? priority) : "未设置"
}

export function riskClass(risk: string) {
  const map: Record<string, string> = {
    high: "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
    medium: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
    low: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  }
  return map[risk] ?? "border-border bg-secondary text-secondary-foreground"
}

export function riskLabel(risk?: string | null) {
  const map: Record<string, string> = {
    high: "高风险",
    medium: "中风险",
    low: "低风险",
  }
  return risk ? (map[risk] ?? risk) : "未设置"
}

export function scenarioLabel(scenario?: string | null) {
  const map: Record<string, string> = {
    knowledge: "知识检索",
    workflow: "业务流程",
    code: "代码任务",
    analysis: "数据分析",
    external_api: "外部接口",
    general: "通用任务",
  }
  return scenario ? (map[scenario] ?? scenario) : "未路由"
}

export function toolLabel(tool?: string | null) {
  const map: Record<string, string> = {
    hybrid_knowledge_search: "企业知识库检索",
    graph_neighbor_expand: "关系证据扩展",
    workflow_state_transition: "流程状态推进",
    approval_gate: "人工确认关卡",
    python_sandbox_runner: "Python 沙箱执行",
    data_frame_profiler: "数据表画像分析",
    http_api_connector: "HTTP 接口连接器",
    memory_write_policy: "记忆写入策略",
  }
  return tool ? (map[tool] ?? tool) : "Runtime 自动编排"
}
