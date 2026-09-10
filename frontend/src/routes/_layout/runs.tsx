import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  GitBranch,
  Inbox,
  Play,
  Timer,
} from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { AetherFlowApi, type AgentRun, type WorkflowTask } from "@/lib/aetherflow-api"
import { formatScore, riskClass, riskLabel, scenarioLabel, statusClass, statusLabel, toolLabel } from "@/lib/aetherflow-format"

export const Route = createFileRoute("/_layout/runs")({
  component: Runs,
  head: () => ({ meta: [{ title: "处理中心 - AetherFlow" }] }),
})

type RunFilter = "all" | "needs_human" | "succeeded" | "recovered" | "failed"

const filterOptions: Array<{ key: RunFilter; label: string }> = [
  { key: "all", label: "全部" },
  { key: "needs_human", label: "待确认" },
  { key: "succeeded", label: "已完成" },
  { key: "recovered", label: "已恢复" },
  { key: "failed", label: "失败" },
]

function Runs() {
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<RunFilter>("all")
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const runsQuery = useQuery({ queryKey: ["aetherflow", "runs"], queryFn: AetherFlowApi.readRuns })
  const tasksQuery = useQuery({ queryKey: ["aetherflow", "tasks"], queryFn: AetherFlowApi.readTasks })
  const approvalMutation = useMutation({
    mutationFn: (runId: string) => AetherFlowApi.approveRun(runId),
    onSuccess: () => {
      toast.success("审批已通过，演练已完成")
      queryClient.invalidateQueries({ queryKey: ["aetherflow"] })
    },
    onError: (error) => toast.error(error.message),
  })

  const runs = runsQuery.data?.data ?? []
  const tasks = tasksQuery.data?.data ?? []
  const counts = useMemo(() => ({
    all: runs.length,
    needs_human: runs.filter((run) => run.status === "needs_human").length,
    succeeded: runs.filter((run) => run.status === "succeeded").length,
    recovered: runs.filter((run) => run.status === "recovered").length,
    failed: runs.filter((run) => run.status === "failed").length,
  }), [runs])
  const filteredRuns = useMemo(
    () => filter === "all" ? runs : runs.filter((run) => run.status === filter),
    [filter, runs],
  )
  const selectedRun = filteredRuns.find((run) => run.id === selectedRunId) ?? filteredRuns[0] ?? null
  const selectedTask = selectedRun ? tasks.find((task) => task.id === selectedRun.task_id) : undefined

  return (
    <div className="page-shell gap-6">
      <header className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <div>
          <div className="page-kicker">我的工作 · 处理中心</div>
          <h1 className="page-title mt-2 text-3xl md:text-4xl">处理记录</h1>
          <p className="page-description mt-3 text-base md:text-lg">集中查看 Agent 已完成、待确认和需要复盘的工作结果。</p>
        </div>
        <Button asChild>
          <Link to="/"><Play className="size-4" />开始新任务</Link>
        </Button>
      </header>

      <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
        <div className="flex flex-wrap gap-1 rounded-lg border bg-card p-1">
          {filterOptions.map((option) => (
            <button
              key={option.key}
              type="button"
              onClick={() => setFilter(option.key)}
              className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition ${filter === option.key ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
            >
              {option.label}
              <span className={filter === option.key ? "text-primary-foreground/80" : "text-muted-foreground"}>{counts[option.key]}</span>
            </button>
          ))}
        </div>
        {counts.needs_human > 0 ? <div className="inline-flex items-center gap-2 text-sm font-medium text-amber-700"><CircleAlert className="size-4" />有 {counts.needs_human} 项工作等待确认</div> : null}
      </div>

      <section className="grid min-h-[680px] overflow-hidden rounded-xl border bg-card shadow-sm lg:grid-cols-[minmax(280px,340px)_minmax(0,1fr)]">
        <aside className="border-b bg-muted/[0.16] lg:border-b-0 lg:border-r">
          <div className="border-b px-5 py-4">
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold">运行队列</div>
              <span className="text-xs text-muted-foreground">{filteredRuns.length} 项</span>
            </div>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">选择一项查看处理结论</p>
          </div>
          <div className="max-h-[620px] overflow-y-auto p-2">
            {runsQuery.isLoading ? <div className="p-4 text-sm text-muted-foreground">正在加载处理记录</div> : filteredRuns.length === 0 ? <div className="flex min-h-48 flex-col items-center justify-center px-5 text-center"><Inbox className="size-8 text-muted-foreground/60" /><p className="mt-3 text-sm font-medium">这个队列还没有记录</p><p className="mt-1 text-xs leading-5 text-muted-foreground">提交一项工作后，结果会自动出现在这里。</p></div> : filteredRuns.map((run) => {
              const task = tasks.find((item) => item.id === run.task_id)
              const selected = selectedRun?.id === run.id
              return <button key={run.id} type="button" onClick={() => setSelectedRunId(run.id)} className={`w-full rounded-lg border p-4 text-left transition ${selected ? "border-primary/50 bg-primary/[0.06] shadow-sm" : "border-transparent hover:border-border hover:bg-background"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-1.5"><Badge variant="outline" className={statusClass(run.status)}>{statusLabel(run.status)}</Badge><Badge variant="secondary" className="max-w-[116px] truncate">{scenarioLabel(run.scenario)}</Badge></div>
                    <div className="mt-3 line-clamp-2 text-sm font-semibold leading-5">{task?.title || "Agent 处理任务"}</div>
                    <div className="mt-2 text-xs text-muted-foreground">{formatTime(run.created_at)}</div>
                  </div>
                  <ArrowRight className={`mt-1 size-4 shrink-0 transition ${selected ? "text-primary" : "text-muted-foreground/50"}`} />
                </div>
              </button>
            })}
          </div>
        </aside>

        <main className="min-w-0">
          {selectedRun ? <RunDetails run={selectedRun} task={selectedTask} onApprove={() => approvalMutation.mutate(selectedRun.id)} isApproving={approvalMutation.isPending} /> : <div className="flex min-h-[680px] flex-col items-center justify-center px-6 text-center"><div className="flex size-14 items-center justify-center rounded-full bg-primary/10 text-primary"><Inbox className="size-7" /></div><h2 className="mt-5 text-lg font-semibold">还没有可查看的处理结果</h2><p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">从工作台提交第一项工作，Agent 会在这里保留最终结论和完整处理过程。</p><Button asChild className="mt-5"><Link to="/"><Play className="size-4" />提交新任务</Link></Button></div>}
        </main>
      </section>
    </div>
  )
}

function RunDetails({ run, task, onApprove, isApproving }: { run: AgentRun; task?: WorkflowTask; onApprove: () => void; isApproving: boolean }) {
  const needsApproval = run.status === "needs_human"
  return <div className="flex h-full min-w-0 flex-col">
    <div className="border-b px-5 py-5 md:px-8">
      <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className={statusClass(run.status)}>{statusLabel(run.status)}</Badge><Badge variant="secondary">{scenarioLabel(run.scenario)}</Badge><Badge variant="outline" className={riskClass(run.risk_level)}>{riskLabel(run.risk_level)}</Badge></div>
          <h2 className="mt-4 text-xl font-bold leading-7">{task?.title || "Agent 处理任务"}</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">{task?.objective || "这次运行没有关联可显示的任务描述。"}</p>
        </div>
        {needsApproval ? <Button onClick={onApprove} disabled={isApproving}><CheckCircle2 className="size-4" />{isApproving ? "确认提交中" : "批准并完成演练"}</Button> : null}
      </div>
      {needsApproval ? <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50/70 px-3 py-2.5 text-xs leading-5 text-amber-800"><CircleAlert className="mt-0.5 size-4 shrink-0" /><span>系统已完成方案校验，当前等待人工确认。批准只会完成本次 dry-run，不会执行真实外部写入。</span></div> : null}
    </div>

    <div className="flex-1 space-y-6 overflow-y-auto px-5 py-6 md:px-8">
      <div className="grid gap-3 sm:grid-cols-4">
        <Metric label="可靠性" value={formatScore(run.reliability_score)} />
        <Metric label="置信度" value={formatScore(run.confidence)} />
        <Metric label="处理方式" value={toolLabel(run.selected_tool)} />
        <Metric label="Trace 步骤" value={String(run.steps.length || run.graph_node_count)} />
      </div>

      <section>
        <div className="mb-3 flex items-center justify-between gap-3"><div><div className="section-label">最终结果</div><h3 className="mt-1 text-lg font-semibold">Agent 输出</h3></div><span className="text-xs text-muted-foreground">{formatTime(run.completed_at || run.created_at)}</span></div>
        <div className={`whitespace-pre-wrap rounded-lg border p-5 text-sm leading-7 ${needsApproval ? "border-amber-200 bg-amber-50/40" : "bg-background"}`}>{run.final_answer || "本次运行没有返回文本结果，请展开处理过程查看详情。"}</div>
      </section>

      <details open className="group rounded-lg border">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 text-sm font-semibold"><span className="flex items-center gap-2"><GitBranch className="size-4 text-primary" />处理依据与 Trace</span><ChevronDown className="size-4 text-muted-foreground transition group-open:rotate-180" /></summary>
        <div className="border-t px-4 py-4">
          <div className="space-y-0">
            {run.steps.map((step, index) => <div key={step.id} className="relative flex gap-4 pb-5 last:pb-0">
              {index < run.steps.length - 1 ? <div className="absolute left-[15px] top-8 h-[calc(100%-12px)] w-px bg-border" /> : null}
              <div className="z-[1] flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">{step.sequence}</div>
              <div className="min-w-0 flex-1 rounded-lg border bg-background p-3.5">
                <div className="flex flex-wrap items-start justify-between gap-2"><div className="flex items-center gap-2 text-sm font-semibold"><Bot className="size-4 text-primary" />{step.agent_name}</div><div className="flex items-center gap-3 text-xs text-muted-foreground"><span className="inline-flex items-center gap-1"><CheckCircle2 className="size-3" />{formatScore(step.confidence)}</span><span className="inline-flex items-center gap-1"><Timer className="size-3" />{step.latency_ms}ms</span></div></div>
                <div className="mt-2 flex flex-wrap gap-2"><Badge variant="outline" className={statusClass(step.status)}>{step.stage}</Badge>{step.tool_name ? <Badge variant="secondary">{toolLabel(step.tool_name)}</Badge> : null}</div>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{step.output_snapshot || "暂无输出快照"}</p>
                {Object.keys(step.metadata_json).length ? <details className="mt-3"><summary className="cursor-pointer text-xs font-medium text-primary">查看结构化数据</summary><pre className="mt-2 max-h-44 overflow-auto rounded-md border bg-muted/30 p-3 text-xs leading-5 text-muted-foreground">{JSON.stringify(step.metadata_json, null, 2)}</pre></details> : null}
              </div>
            </div>)}
          </div>
        </div>
      </details>

      <div className="grid gap-3 border-t pt-5 text-xs text-muted-foreground sm:grid-cols-3"><InfoItem label="运行编号" value={run.id} /><InfoItem label="Runtime 版本" value={run.runtime_version} /><InfoItem label="审批状态" value={run.approval_status === "approved" ? "已通过" : run.approval_status === "pending" ? "等待确认" : "无需审批"} /></div>
    </div>
  </div>
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="min-w-0 rounded-lg border bg-muted/[0.18] p-3"><div className="text-xs text-muted-foreground">{label}</div><div className="mt-1 truncate text-sm font-semibold" title={value}>{value}</div></div>
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return <div className="min-w-0"><div>{label}</div><div className="mt-1 truncate font-medium text-foreground" title={value}>{value}</div></div>
}

function formatTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
}
