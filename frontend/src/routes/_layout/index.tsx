import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpen,
  Bot,
  ChevronDown,
  FileCheck2,
  LoaderCircle,
  Play,
  Workflow,
  X,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import type { FormEvent } from "react"
import { useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { AetherFlowApi, type AgentRun, type WorkflowTask, type WorkflowTaskCreate } from "@/lib/aetherflow-api"
import {
  riskClass,
  riskLabel,
  scenarioLabel,
  statusClass,
  statusLabel,
} from "@/lib/aetherflow-format"

export const Route = createFileRoute("/_layout/")({
  component: Workspace,
  head: () => ({ meta: [{ title: "工作台 - AetherFlow" }] }),
})

type WorkspaceMode = {
  value: string
  title: string
  hint: string
  icon: LucideIcon
  example: string
}

const workspaceModes: WorkspaceMode[] = [
  { value: "analysis", title: "分析数据", hint: "识别趋势、异常并形成结论", example: "分析本月销售数据，找出下降明显的产品，并给出三条跟进建议。", icon: BarChart3 },
  { value: "knowledge", title: "查制度与资料", hint: "基于企业资料给出有依据的回答", example: "根据员工出差制度，整理差旅报销需要的材料和审批步骤。", icon: BookOpen },
  { value: "workflow", title: "推进业务流程", hint: "拆解步骤并生成下一步行动", example: "把这项采购需求拆成申请、审批、比价和交付四个步骤，并标出负责人。", icon: Workflow },
  { value: "external_api", title: "准备系统操作", hint: "先校验方案，必要时进入审批", example: "准备给客户发送一批跟进邮件，先检查收件人、内容和发送风险，不要直接发送。", icon: FileCheck2 },
]

function Workspace() {
  const [requestText, setRequestText] = useState("")
  const [contextText, setContextText] = useState("")
  const [expectedOutput, setExpectedOutput] = useState("")
  const [selectedMode, setSelectedMode] = useState("analysis")
  const [riskLevel, setRiskLevel] = useState("medium")
  const [requiresApproval, setRequiresApproval] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const [activeRun, setActiveRun] = useState<AgentRun | null>(null)
  const [submitError, setSubmitError] = useState("")

  const summaryQuery = useQuery({ queryKey: ["aetherflow", "summary"], queryFn: AetherFlowApi.readSummary })
  const tasksQuery = useQuery({ queryKey: ["aetherflow", "tasks"], queryFn: AetherFlowApi.readTasks })
  const runsQuery = useQuery({ queryKey: ["aetherflow", "runs"], queryFn: AetherFlowApi.readRuns })

  const runMutation = useMutation({
    mutationFn: async (payload: WorkflowTaskCreate) => {
      const task = await AetherFlowApi.createTask(payload)
      const run = await AetherFlowApi.runTaskAgent(task.id)
      return { task, run }
    },
    onSuccess: ({ run }) => {
      setActiveRun(run)
      setRequestText("")
      setContextText("")
      setExpectedOutput("")
      setSubmitError("")
      void Promise.all([summaryQuery.refetch(), tasksQuery.refetch(), runsQuery.refetch()])
      toast.success(run.status === "needs_human" ? "任务已处理，等待人工确认" : "任务已完成处理")
    },
    onError: (error) => {
      setSubmitError(error instanceof Error ? error.message : "任务处理失败，请稍后重试")
      void Promise.all([tasksQuery.refetch(), runsQuery.refetch()])
      toast.error("任务处理失败")
    },
  })

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const objective = requestText.trim()
    if (!objective) {
      setSubmitError("请先描述你要完成的工作")
      return
    }

    const modeLabel = workspaceModes.find((mode) => mode.value === selectedMode)?.title ?? "通用任务"
    setActiveRun(null)
    setSubmitError("")
    runMutation.mutate({
      title: objective.length > 28 ? objective.slice(0, 28) + "…" : objective,
      objective,
      context: contextText.trim() || null,
      expected_output: expectedOutput.trim() || null,
      scenario_hint: selectedMode,
      priority: "medium",
      status: "ready",
      risk_level: riskLevel,
      requires_approval: requiresApproval || riskLevel === "high",
      owner_team: "employee_workspace",
      tags: ["employee_workspace", modeLabel],
    })
  }

  const runs = runsQuery.data?.data.slice(0, 4) ?? []
  const tasks = tasksQuery.data?.data ?? []
  const summary = summaryQuery.data
  const isProcessing = runMutation.isPending

  return (
    <div className="page-shell space-y-8">
      <section className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
        <div className="max-w-3xl">
          <div className="section-label">员工工作台</div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <h1 className="page-title">把工作交给 Agent</h1>
            <Badge variant="outline" className="border-emerald-300 bg-emerald-50 text-emerald-700">
              <span className="mr-1.5 size-1.5 rounded-full bg-emerald-500" /> 可立即处理
            </Badge>
          </div>
          <p className="page-description mt-3">输入你要完成的工作，Agent 会理解目标、选择合适的处理方式，并返回可检查、可追溯的结果。</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button asChild variant="outline">
            <Link to="/runs"><Activity className="size-4" />处理记录</Link>
          </Button>
          <Button asChild variant="ghost">
            <Link to="/tasks">任务列表<ArrowRight className="size-4" /></Link>
          </Button>
        </div>
      </section>

      <section className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(330px,0.75fr)]">
        <Card className="border-primary/20 shadow-sm">
          <CardHeader className="border-b bg-primary/[0.03]">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground"><Bot className="size-5" /></div>
              <div>
                <CardTitle>你要完成什么工作？</CardTitle>
                <CardDescription>可以直接用自然语言描述，不需要先理解工具或流程配置。</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-6">
            <form className="space-y-6" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <Label htmlFor="employee-request">任务描述</Label>
                  {(requestText || contextText || expectedOutput) ? <Button type="button" variant="ghost" size="icon-sm" title="清空输入" aria-label="清空输入" onClick={() => { setRequestText(""); setContextText(""); setExpectedOutput(""); setSubmitError("") }} disabled={isProcessing}><X className="size-4" /></Button> : null}
                </div>
                <textarea
                  id="employee-request"
                  value={requestText}
                  onChange={(event) => setRequestText(event.target.value)}
                  placeholder="例如：分析本月销售数据，找出华东区域下降明显的产品，并给出下周的跟进建议。"
                  className="min-h-36 w-full resize-y rounded-xl border border-input bg-background px-4 py-3 text-sm leading-6 shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                  disabled={isProcessing}
                />
                <p className="text-xs text-muted-foreground">支持中文和英文。描述越接近真实工作目标，Agent 越容易选择合适的处理路径。</p>
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <span className="text-xs text-muted-foreground">试用示例：</span>
                  {workspaceModes.map((mode) => <button key={mode.value} type="button" className="rounded-full border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:border-primary/40 hover:text-primary" onClick={() => { setSelectedMode(mode.value); setRequestText(mode.example); setSubmitError("") }} disabled={isProcessing}>{mode.title}</button>)}
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <Label>可以选择一个工作类型</Label>
                  <span className="text-xs text-muted-foreground">不确定时可以不选，Agent 会自动判断</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {workspaceModes.map((mode) => {
                    const Icon = mode.icon
                    const selected = selectedMode === mode.value
                    return (
                      <button
                        key={mode.value}
                        type="button"
                        onClick={() => setSelectedMode(mode.value)}
                        className={`flex items-start gap-3 rounded-xl border p-4 text-left transition ${selected ? "border-primary bg-primary/[0.06] shadow-sm" : "border-border hover:border-primary/40 hover:bg-muted/40"}`}
                        disabled={isProcessing}
                      >
                        <Icon className={`mt-0.5 size-5 shrink-0 ${selected ? "text-primary" : "text-muted-foreground"}`} />
                        <span className="min-w-0">
                          <span className="block text-sm font-semibold">{mode.title}</span>
                          <span className="mt-1 block text-xs leading-5 text-muted-foreground">{mode.hint}</span>
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="flex items-center justify-between border-t pt-4">
                <button type="button" className="inline-flex items-center gap-2 text-sm font-semibold text-primary" onClick={() => setShowDetails((value) => !value)}>
                  <ChevronDown className={`size-4 transition ${showDetails ? "rotate-180" : ""}`} />补充处理要求
                </button>
                <span className="text-xs text-muted-foreground">可选</span>
              </div>

              {showDetails ? <div className="grid gap-4 rounded-xl bg-muted/30 p-4 md:grid-cols-2">
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="employee-context">相关背景或数据</Label>
                  <textarea
                    id="employee-context"
                    value={contextText}
                    onChange={(event) => setContextText(event.target.value)}
                    placeholder="粘贴背景、表格内容、制度条款或业务约束"
                    className="min-h-24 w-full resize-y rounded-lg border border-input bg-background px-3 py-2 text-sm leading-6 outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                    disabled={isProcessing}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="employee-output">希望得到的结果</Label>
                  <Input id="employee-output" value={expectedOutput} onChange={(event) => setExpectedOutput(event.target.value)} placeholder="例如：一页经营简报和三条行动建议" disabled={isProcessing} />
                </div>
                <div className="space-y-2">
                  <Label>风险与确认</Label>
                  <div className="flex flex-wrap gap-2">
                    {["low", "medium", "high"].map((level) => (
                      <button key={level} type="button" onClick={() => setRiskLevel(level)} className={`rounded-lg border px-3 py-2 text-xs font-semibold transition ${riskLevel === level ? riskClass(level) + " border-current" : "border-border bg-background text-muted-foreground hover:border-primary/40"}`} disabled={isProcessing}>{riskLabel(level)}</button>
                    ))}
                  </div>
                  <label className="flex items-center gap-2 text-xs text-muted-foreground">
                    <input type="checkbox" checked={requiresApproval} onChange={(event) => setRequiresApproval(event.target.checked)} disabled={isProcessing} className="size-4 accent-primary" />
                    涉及外部系统或对外发送时先让我确认
                  </label>
                </div>
              </div> : null}

              {submitError ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm leading-6 text-red-700">{submitError}</div> : null}
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-5 text-muted-foreground">高风险操作只生成方案并进入人工确认，不会直接修改外部系统。</p>
                <Button type="submit" disabled={isProcessing || !requestText.trim()} className="min-w-40">
                  {isProcessing ? <><LoaderCircle className="size-4 animate-spin" />Agent 处理中</> : <><Play className="size-4" />提交给 Agent</>}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <ResultPanel run={activeRun} isProcessing={isProcessing} error={submitError} />
      </section>

      <RecentWork runs={runs} tasks={tasks} isLoading={runsQuery.isLoading} />

      <WorkSummary summary={summary} />
    </div>
  )
}

type ResultPanelProps = {
  run: AgentRun | null
  isProcessing: boolean
  error: string
}

function ResultPanel({ run, isProcessing, error }: ResultPanelProps) {
  const needsApproval = run?.status === "needs_human"

  return (
    <Card className="min-h-[460px] overflow-hidden">
      <CardHeader className="border-b">
        <div className="section-label">处理结果</div>
        <CardTitle className="mt-2 flex items-center gap-2"><FileCheck2 className="size-5 text-primary" />结果会显示在这里</CardTitle>
        <CardDescription>提交后可以看到结论、下一步动作和处理记录。</CardDescription>
      </CardHeader>
      <CardContent className="p-6">
        {isProcessing ? <div className="flex min-h-[330px] flex-col items-center justify-center text-center">
          <div className="flex size-14 items-center justify-center rounded-full bg-primary/10 text-primary"><LoaderCircle className="size-7 animate-spin" /></div>
          <div className="mt-5 font-semibold">Agent 正在处理你的请求</div>
          <p className="mt-2 max-w-xs text-sm leading-6 text-muted-foreground">正在识别场景、规划步骤、选择工具并检查结果。完成后会自动显示在这里。</p>
          <div className="mt-6 flex flex-wrap justify-center gap-2 text-xs text-muted-foreground"><span className="rounded-full bg-muted px-3 py-1">理解任务</span><span className="rounded-full bg-muted px-3 py-1">选择处理方式</span><span className="rounded-full bg-muted px-3 py-1">检查结果</span></div>
        </div> : error ? <div className="flex min-h-[330px] flex-col justify-center">
          <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm leading-6 text-red-700">
            <div className="font-semibold">这次处理没有完成</div>
            <p className="mt-2 break-words text-red-700/80">{error}</p>
          </div>
          <p className="mt-4 text-xs leading-5 text-muted-foreground">任务已保留在任务列表中，你可以调整需求后重新提交。</p>
        </div> : run ? <div className="space-y-5">
          <div className={`rounded-xl border p-5 ${needsApproval ? "border-amber-200 bg-amber-50/70" : "border-emerald-200 bg-emerald-50/70"}`}>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className={statusClass(run.status)}>{statusLabel(run.status)}</Badge>
              <Badge variant="secondary">{scenarioLabel(run.scenario)}</Badge>
              {run.risk_level ? <Badge variant="outline" className={riskClass(run.risk_level)}>{riskLabel(run.risk_level)}</Badge> : null}
            </div>
            <h2 className="mt-4 text-xl font-bold">{needsApproval ? "方案已生成，等待你确认" : "这项工作已经处理完成"}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{needsApproval ? "系统已完成校验，但不会代替你执行高风险或对外操作。" : "你可以直接使用下面的结果，也可以打开处理记录查看完整依据。"}</p>
          </div>
          <div>
            <div className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-muted-foreground">处理结果</div>
            <div className="max-h-56 overflow-auto rounded-xl border bg-background p-4 text-sm leading-7 whitespace-pre-wrap">{run.final_answer || "本次运行没有返回可展示的文本结果，请打开处理记录查看详细步骤。"}</div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button asChild>
              <Link to="/runs"><Activity className="size-4" />查看完整记录<ArrowRight className="size-4" /></Link>
            </Button>
            {needsApproval ? <Button asChild variant="outline"><Link to="/runs">查看确认记录</Link></Button> : null}
          </div>
        </div> : <div className="flex min-h-[330px] flex-col items-center justify-center text-center">
          <div className="flex size-14 items-center justify-center rounded-full border border-dashed border-primary/40 bg-primary/[0.04] text-primary"><Bot className="size-7" /></div>
          <div className="mt-5 font-semibold">还没有处理结果</div>
          <p className="mt-2 max-w-xs text-sm leading-6 text-muted-foreground">从左侧输入一项真实工作，结果会在这里直接返回。</p>
        </div>}
      </CardContent>
    </Card>
  )
}

function RecentWork({ runs, tasks, isLoading }: { runs: AgentRun[]; tasks: WorkflowTask[]; isLoading: boolean }) {
  return (
    <section>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="section-label">我的处理</div>
          <h2 className="mt-2 text-2xl font-bold tracking-tight">最近处理记录</h2>
          <p className="mt-1 text-sm text-muted-foreground">继续查看之前交给 Agent 的工作，不需要重新配置。</p>
        </div>
        <Button asChild variant="ghost"><Link to="/runs">查看全部<ArrowRight className="size-4" /></Link></Button>
      </div>
      {isLoading ? <div className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">正在读取处理记录…</div> : runs.length === 0 ? <div className="rounded-xl border border-dashed bg-card p-8 text-center text-sm text-muted-foreground">还没有处理记录。提交第一项工作后，结果和处理详情会出现在这里。</div> : <div className="grid gap-3 md:grid-cols-2">
        {runs.map((run) => {
          const task = tasks.find((item) => item.id === run.task_id)
          return <Link key={run.id} to="/runs" className="group rounded-xl border bg-card p-4 transition hover:border-primary/40 hover:shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap gap-2"><Badge variant="outline" className={statusClass(run.status)}>{statusLabel(run.status)}</Badge><Badge variant="secondary">{scenarioLabel(run.scenario)}</Badge></div>
                <div className="mt-3 truncate font-semibold">{task?.title || "Agent 处理任务"}</div>
                <p className="mt-1 line-clamp-2 text-sm leading-6 text-muted-foreground">{run.final_answer || "暂无文本摘要，请打开处理记录查看。"}</p>
              </div>
              <ArrowRight className="mt-1 size-4 shrink-0 text-muted-foreground transition group-hover:translate-x-1 group-hover:text-primary" />
            </div>
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground"><span>{new Date(run.created_at).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span><span>打开查看处理详情</span></div>
          </Link>
        })}
      </div>}
    </section>
  )
}

function WorkSummary({ summary }: { summary?: { run_count: number; approval_queue_count: number } }) {
  return <section className="flex flex-col justify-between gap-5 rounded-xl border bg-card px-5 py-4 md:flex-row md:items-center"><div><div className="section-label">工作概览</div><p className="mt-2 text-sm leading-6 text-muted-foreground">Agent 已经处理的工作会保留在处理中心，待确认事项需要你完成最后一步。</p></div><div className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm"><SummaryItem label="已处理" value={String(summary?.run_count ?? 0)} /><SummaryItem label="待确认" value={String(summary?.approval_queue_count ?? 0)} emphasis={Boolean(summary?.approval_queue_count)} /></div></section>
}

function SummaryItem({ label, value, emphasis = false }: { label: string; value: string; emphasis?: boolean }) {
  return <div><div className="text-xs text-muted-foreground">{label}</div><div className={`mt-1 text-lg font-bold tabular-nums ${emphasis ? "text-amber-700" : ""}`}>{value}</div></div>
}













