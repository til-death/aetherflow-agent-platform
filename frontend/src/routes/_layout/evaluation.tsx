import type { LucideIcon } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  Database,
  Copy,
  FlaskConical,
  Gauge,
  GitBranch,
  Play,
  RefreshCw,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react"
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  AetherFlowApi,
  type AgentSummary,
  type EvaluationCaseResult,
  type EvaluationExperimentSummary,
  type EvaluationFailureAnalysis,
  type EvaluationGateCheck,
  type EvaluationMetric,
  type EvaluationReport,
  type EvaluationScenarioSlice,
  type EvaluationToolCoverage,
  type RunEvaluationResult,
  type ScorerDefinition,
  type ScorerScoreResult,
  type ToolDecisionCheck,
} from "@/lib/aetherflow-api"
import {
  formatPercent,
  formatScore,
  riskClass,
  riskLabel,
  scenarioLabel,
  statusClass,
  statusLabel,
} from "@/lib/aetherflow-format"

export const Route = createFileRoute("/_layout/evaluation")({
  component: Evaluation,
  head: () => ({ meta: [{ title: "评估工作台 - AetherFlow" }] }),
})

function Evaluation() {
  const [selectedRunId, setSelectedRunId] = useState("")
  const [selectedCaseId, setSelectedCaseId] = useState("")
  const [datasetKey, setDatasetKey] = useState("toolluban")
  const [selectedExperimentId, setSelectedExperimentId] = useState("")

  const summaryQuery = useQuery({ queryKey: ["aetherflow", "summary"], queryFn: AetherFlowApi.readSummary })
  const runsQuery = useQuery({ queryKey: ["aetherflow", "runs"], queryFn: AetherFlowApi.readRuns })
  const scorersQuery = useQuery({ queryKey: ["aetherflow", "scorers"], queryFn: AetherFlowApi.readScorers })
  const experimentsQuery = useQuery({ queryKey: ["aetherflow", "experiments"], queryFn: AetherFlowApi.readExperiments })
  const experimentDetailQuery = useQuery({ queryKey: ["aetherflow", "experiment", selectedExperimentId], queryFn: () => AetherFlowApi.readExperiment(selectedExperimentId), enabled: Boolean(selectedExperimentId) })
  const runs = runsQuery.data?.data ?? []
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? runs[0]

  useEffect(() => {
    if (!selectedRunId && runs[0]) setSelectedRunId(runs[0].id)
  }, [runs, selectedRunId])

  const auditQuery = useQuery({
    queryKey: ["aetherflow", "tool-decision-audit", selectedRun?.id],
    queryFn: () => {
      if (!selectedRun) throw new Error("没有可评估的运行记录")
      return AetherFlowApi.evaluateRun(selectedRun.id)
    },
    enabled: Boolean(selectedRun?.id),
  })

  const benchmarkMutation = useMutation<EvaluationReport, Error, string>({
    mutationFn: (dataset) => AetherFlowApi.runEvaluation(dataset),
    onSuccess: (nextReport) => {
      toast.success("Experiment 已完成")
      setSelectedCaseId(nextReport.failures[0]?.case_id ?? nextReport.cases[0]?.case_id ?? "")
      setSelectedExperimentId(nextReport.experiment_id)
      if (nextReport.dataset?.dataset_key) setDatasetKey(nextReport.dataset.dataset_key)
      void experimentsQuery.refetch()
    },
    onError: (error) => toast.error(error.message),
  })

  const report = experimentDetailQuery.data ?? (benchmarkMutation.data?.experiment_id === selectedExperimentId ? benchmarkMutation.data : undefined)
  const selectedCase = report?.cases.find((item) => item.case_id === selectedCaseId) ?? report?.cases[0]

  function handleDatasetChange(value: string) {
    setDatasetKey(value)
    setSelectedExperimentId("")
  }

  async function copyExperimentSummary() {
    if (!report) return
    try {
      await navigator.clipboard.writeText([
        `${report.experiment_name} · ${report.experiment_id}`,
        `数据集：${report.dataset?.task_dataset_name ?? "未命名"}，Case：${report.case_count}，失败：${report.failure_count}`,
        `Release Gate：${report.release_gate.label}。${report.release_gate.summary}`,
        ...report.recommended_actions.map((action) => `建议：${action}`),
      ].join("\n"))
      toast.success("实验摘要已复制")
    } catch {
      toast.error("复制失败，请检查浏览器剪贴板权限")
    }
  }

  return (
    <div className="page-shell">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="page-kicker">Agent Reliability / Experiment Studio</div>
          <h1 className="page-title text-3xl md:text-4xl">评估工作台</h1>
          <p className="mt-3 max-w-4xl text-base leading-7 text-muted-foreground">
            用可重复的 Benchmark 验证 Agent Runtime 的场景理解、工具选择、风险控制、Trace 完整性和输出契约，并把失败样本转成下一轮优化任务。
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          {report ? <Button type="button" variant="outline" onClick={copyExperimentSummary}><Copy />复制实验摘要</Button> : null}
          <Button type="button" onClick={() => benchmarkMutation.mutate(datasetKey)} disabled={benchmarkMutation.isPending}>
            {benchmarkMutation.isPending ? <RefreshCw className="animate-spin" /> : <Play />}
            {benchmarkMutation.isPending ? "实验运行中" : "运行 Experiment"}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="experiments" className="mt-7 space-y-6">
        <TabsList className="grid w-full gap-1 sm:w-auto sm:grid-cols-3">
          <TabsTrigger value="experiments">Experiments</TabsTrigger>
          <TabsTrigger value="single-run">单次运行</TabsTrigger>
          <TabsTrigger value="scorers">Scorer Studio</TabsTrigger>
        </TabsList>

        <TabsContent value="experiments" className="space-y-6">
          <DatasetSetup report={report} datasetKey={datasetKey} onDatasetChange={handleDatasetChange} onRun={() => benchmarkMutation.mutate(datasetKey)} isRunning={benchmarkMutation.isPending} />
          {experimentsQuery.data?.data.length ? <ExperimentHistory experiments={experimentsQuery.data.data} onSelect={(experiment) => { setSelectedExperimentId(experiment.id); setDatasetKey(experiment.dataset_key); setSelectedCaseId("") }} /> : null}
          {report ? <>
            <ExperimentHeader report={report} />
            <BenchmarkMetrics metrics={report.metrics} />
            <div className="grid gap-6 xl:grid-cols-2"><ReleaseGateChecks checks={report.gate_checks} /><RecommendedActions actions={report.recommended_actions} /></div>
            <div className="grid gap-6 xl:grid-cols-[1fr_1.15fr]"><ScenarioSlices slices={report.scenario_slices} /><ToolCoverage coverage={report.tool_coverage} /></div>
            <CaseResultsTable report={report} selectedCaseId={selectedCase?.case_id ?? ""} onSelectCase={setSelectedCaseId} />
            <div className="grid items-start gap-6 xl:grid-cols-[1fr_420px]"><CaseInspector selectedCase={selectedCase} /><FailureAnalysis failures={report.failures} /></div>
            <div className="rounded-lg border bg-card/60 p-4 text-sm leading-6 text-muted-foreground"><span className="font-semibold text-foreground">实验说明：</span>{report.notes[3] ?? "本次结果由 Runtime 的真实路由、规划、检索、工具执行和 Critic 链路回放得到。"}</div>
          </> : <EmptyExperimentState isRunning={benchmarkMutation.isPending} onRun={() => benchmarkMutation.mutate(datasetKey)} />}
        </TabsContent>

        <TabsContent value="single-run" className="space-y-6">
          <SingleRunStudio runs={runs} selectedRunId={selectedRun?.id ?? ""} selectedRun={selectedRun} audit={auditQuery.data} summary={summaryQuery.data} isAuditLoading={auditQuery.isLoading || auditQuery.isFetching} onSelectRun={setSelectedRunId} onRefresh={() => auditQuery.refetch()} />
        </TabsContent>

        <TabsContent value="scorers" className="space-y-6"><ScorersStudio scorers={scorersQuery.data ?? []} audit={auditQuery.data} /></TabsContent>
      </Tabs>
    </div>
  )
}
function DatasetSetup({ report, datasetKey, onDatasetChange, onRun, isRunning }: { report?: EvaluationReport; datasetKey: string; onDatasetChange: (value: string) => void; onRun: () => void; isRunning: boolean }) {
  const dataset = report?.dataset
  const options = [
    {
      key: "toolluban",
      name: "ToolLuban 中文工具库",
      taskFile: "toolluban_tasks.json",
      toolFile: "toolluban_tools.json + built_in_tool_registry",
      description: "中文业务任务与动态工具定义，重点验证工具路由、审批关卡和输出契约。",
    },
    {
      key: "sample",
      name: "通用 Runtime 样例",
      taskFile: "sample_tasks.json",
      toolFile: "built_in_tool_registry",
      description: "跨 knowledge、workflow、code、analysis 和 external API 的基础回归集。",
    },
  ]
  const activeOption = options.find((option) => option.key === datasetKey) ?? options[0]

  return (
    <Card>
      <CardHeader className="md:grid-cols-[1fr_auto]">
        <div>
          <CardTitle className="flex items-center gap-2 text-xl"><Database className="size-5" />Experiment 输入</CardTitle>
          <CardDescription>选择受控 Dataset 和 Tool Library，Runtime 会对全部 Case 做一次可复现回放。</CardDescription>
        </div>
        <Button type="button" onClick={onRun} disabled={isRunning}>
          <Play />
          {isRunning ? "运行中" : "运行 Benchmark"}
        </Button>
      </CardHeader>
      <CardContent className="grid gap-5">
        <div className="grid gap-3 md:grid-cols-2">
          {options.map((option) => (
            <button
              key={option.key}
              type="button"
              onClick={() => onDatasetChange(option.key)}
              className={datasetKey === option.key ? "rounded-lg border border-primary bg-primary/5 p-4 text-left shadow-sm transition" : "rounded-lg border bg-background/70 p-4 text-left transition hover:border-primary/40"}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="font-bold">{option.name}</div>
                {datasetKey === option.key ? <Badge>当前</Badge> : <Badge variant="outline">可选</Badge>}
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{option.description}</p>
              <div className="mt-3 grid gap-1 text-xs text-muted-foreground">
                <span>任务集：{option.taskFile}</span>
                <span>工具库：{option.toolFile}</span>
              </div>
            </button>
          ))}
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <SetupMetric label="当前数据集" value={dataset?.dataset_key ?? activeOption.key} />
          <SetupMetric label="任务文件" value={dataset?.task_dataset_name ?? activeOption.taskFile} />
          <SetupMetric label="Case 数量" value={report ? String(report.sample_size) : "运行后生成"} />
          <SetupMetric label="工具库" value={dataset?.tool_library_name ?? activeOption.toolFile} />
          <SetupMetric label="动态工具数" value={report ? String(dataset?.dynamic_tool_count ?? 0) : datasetKey === "toolluban" ? "31" : "0"} />
        </div>
        <div className="rounded-lg border border-blue-500/30 bg-blue-500/5 p-4 text-sm leading-6 text-blue-900">
          当前实验使用仓库内受控的 Benchmark fixture，任务标注和工具定义都由后端真实加载；后续可接入 Dataset Manager 做 JSON/CSV 导入与版本管理。
        </div>
      </CardContent>
    </Card>
  )
}

function SetupMetric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border bg-card p-4"><div className="text-xs font-semibold text-muted-foreground">{label}</div><div className="mt-2 truncate font-bold">{value}</div></div>
}

function ExperimentHistory({ experiments, onSelect }: { experiments: EvaluationExperimentSummary[]; onSelect: (experiment: EvaluationExperimentSummary) => void }) {
  return <Card><CardHeader><CardTitle className="flex items-center gap-2 text-xl"><RefreshCw className="size-5" />最近实验</CardTitle><CardDescription>实验结果会落库保存，支持回看不同 Dataset 和 Runtime 版本的评估快照。</CardDescription></CardHeader><CardContent><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>实验</TableHead><TableHead>数据集</TableHead><TableHead>样本</TableHead><TableHead>失败</TableHead><TableHead>门禁</TableHead><TableHead>时间</TableHead></TableRow></TableHeader><TableBody>{experiments.slice(0, 5).map((experiment) => <TableRow key={experiment.id} className="cursor-pointer" onClick={() => onSelect(experiment)}><TableCell><div className="font-medium">{experiment.experiment_name}</div><div className="mt-1 text-xs text-muted-foreground">{experiment.id}</div></TableCell><TableCell>{experiment.dataset_key}</TableCell><TableCell>{experiment.case_count}</TableCell><TableCell>{experiment.failure_count}</TableCell><TableCell><Badge variant="outline" className={gateStatusClass(experiment.release_gate_status)}>{experiment.release_gate_label}</Badge></TableCell><TableCell className="whitespace-nowrap text-xs text-muted-foreground">{new Date(experiment.created_at).toLocaleString("zh-CN", { hour12: false })}</TableCell></TableRow>)}</TableBody></Table></div></CardContent></Card>
}

function gateStatusClass(status: string) {
  if (status === "pass") return "border-emerald-500/40 bg-emerald-500/10 text-emerald-700"
  if (status === "review") return "border-amber-500/40 bg-amber-500/10 text-amber-700"
  return "border-red-500/40 bg-red-500/10 text-red-700"
}
function EmptyExperimentState({ isRunning, onRun }: { isRunning: boolean; onRun: () => void }) {
  return <Card className="border-dashed"><CardContent className="flex flex-col items-center justify-center gap-4 py-14 text-center"><div className="rounded-full bg-primary/10 p-3 text-primary"><FlaskConical className="size-6" /></div><div><div className="text-lg font-bold">还没有实验结果</div><p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">运行一次 Benchmark 后，这里会出现 Release Gate、场景切片、工具覆盖、Case Explorer 和失败修复建议。它们共同回答“当前 Runtime 能不能放行”。</p></div><Button type="button" onClick={onRun} disabled={isRunning}><Play />{isRunning ? "实验运行中" : "运行第一轮 Experiment"}</Button></CardContent></Card>
}

function ExperimentHeader({ report }: { report: EvaluationReport }) {
  const gate = report.release_gate
  const icon = gate.status === "pass" ? <CheckCircle2 className="size-7" /> : gate.status === "review" ? <AlertTriangle className="size-7" /> : <XCircle className="size-7" />
  const tone = gate.status === "pass" ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-900" : gate.status === "review" ? "border-amber-500/30 bg-amber-500/5 text-amber-900" : "border-red-500/30 bg-red-500/5 text-red-900"
  return <Card className={tone}><CardContent className="grid gap-6 p-6 xl:grid-cols-[1fr_auto]"><div><div className="flex flex-wrap items-center gap-2"><Badge variant="outline">Experiment 已完成</Badge><Badge variant="outline">{report.dataset?.dataset_key ?? "unknown"}</Badge><span className="text-xs text-muted-foreground">{report.runtime_version}</span></div><div className="mt-4 flex items-start gap-3">{icon}<div><div className="text-2xl font-bold">{gate.label}</div><p className="mt-2 max-w-3xl text-sm leading-6 opacity-80">{gate.summary}</p></div></div><div className="mt-5 text-xs text-muted-foreground">{report.experiment_name} · {report.experiment_id}</div></div><div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:w-[440px] xl:grid-cols-2"><MiniMetric label="Cases" value={String(report.case_count)} /><MiniMetric label="失败样本" value={String(report.failure_count)} /><MiniMetric label="工具总数" value={String((report.dataset?.dynamic_tool_count ?? 0) + 8)} /><MiniMetric label="Trace 策略" value="完整回放" /></div></CardContent></Card>
}

function ReleaseGateChecks({ checks }: { checks: EvaluationGateCheck[] }) {
  return <Card><CardHeader><CardTitle className="flex items-center gap-2 text-xl"><ShieldCheck className="size-5" />Release Gate</CardTitle><CardDescription>放行判断由门槛和 Case 失败数共同决定，先看这里就能定位阻塞项。</CardDescription></CardHeader><CardContent className="grid gap-2">{checks.map((check) => <div key={check.name} className="flex flex-col gap-3 rounded-lg border bg-background/70 p-4 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-start gap-3">{check.passed ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600" /> : <XCircle className="mt-0.5 size-5 shrink-0 text-red-600" />}<div><div className="font-bold">{check.name}</div><div className="mt-1 text-sm text-muted-foreground">{check.detail}</div></div></div><div className="flex items-center gap-2"><span className="text-lg font-bold tabular-nums">{formatPercent(check.score)}</span><Badge variant="outline">门槛 {formatPercent(check.threshold)}</Badge></div></div>)}</CardContent></Card>
}

function RecommendedActions({ actions }: { actions: string[] }) {
  return <Card><CardHeader><CardTitle className="flex items-center gap-2 text-xl"><ArrowRight className="size-5" />下一轮优化建议</CardTitle><CardDescription>把失败结果转成可以修改 Router、工具描述、审批策略或 Benchmark 的动作。</CardDescription></CardHeader><CardContent className="grid gap-3">{actions.map((action, index) => <div key={`${action}-${index}`} className="flex gap-3 rounded-lg border bg-background/70 p-4 text-sm leading-6"><Badge variant="outline">{index + 1}</Badge><span>{action}</span></div>)}</CardContent></Card>
}
function BenchmarkMetrics({ metrics }: { metrics: EvaluationMetric[] }) {
  const metricMap = new Map(metrics.map((metric) => [metric.name, metric]))
  const cards = [
    ["Scenario Accuracy", "任务是否进入预期场景"],
    ["Tool Top@1 Accuracy", "首选工具命中率"],
    ["Tool Top@3 Recall", "正确工具进入前三候选"],
    ["Approval Accuracy", "高风险任务审批判断准确率"],
    ["Trace Completeness", "关键执行阶段是否完整"],
    ["Output Contract Coverage", "输出是否覆盖业务契约"],
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl"><Gauge className="size-5" />可靠性指标</CardTitle>
        <CardDescription>每个指标都对应 Runtime 的一个可观测环节，分数用于支撑放行和诊断。</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {cards.map(([name, description]) => {
          const metric = metricMap.get(name)
          return <MetricCard key={name} title={metricLabel(name)} description={description} value={metric ? formatPercent(metric.reliability_harness) : "未运行"} />
        })}
      </CardContent>
    </Card>
  )
}

function MetricCard({ title, description, value }: { title: string; description: string; value: string }) {
  return <div className="rounded-lg border bg-background/70 p-5"><div className="text-sm font-bold">{title}</div><div className="mt-4 text-3xl font-bold tabular-nums">{value}</div><div className="mt-3 text-sm leading-6 text-muted-foreground">{description}</div></div>
}

function ScenarioSlices({ slices }: { slices: EvaluationScenarioSlice[] }) {
  return <Card><CardHeader><CardTitle className="flex items-center gap-2 text-xl"><GitBranch className="size-5" />场景切片</CardTitle><CardDescription>按预期场景拆开看，避免总体平均分掩盖某个业务场景的退化。</CardDescription></CardHeader><CardContent className="grid gap-3">{slices.map((slice) => <div key={slice.scenario} className="rounded-lg border bg-background/70 p-4"><div className="flex items-center justify-between gap-3"><div className="font-bold">{scenarioLabel(slice.scenario)}</div><StatusPill passed={slice.pass_rate >= 0.8} /></div><div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"><MiniMetric label="通过率" value={formatPercent(slice.pass_rate)} /><MiniMetric label="Top@1" value={formatPercent(slice.top1_accuracy)} /><MiniMetric label="审批" value={formatPercent(slice.approval_accuracy)} /><MiniMetric label="契约" value={formatPercent(slice.contract_coverage)} /></div>{slice.failed_cases.length ? <div className="mt-3 text-xs text-red-700">失败 Case：{slice.failed_cases.join("、")}</div> : null}</div>)}</CardContent></Card>
}

function ToolCoverage({ coverage }: { coverage: EvaluationToolCoverage[] }) {
  return <Card><CardHeader><CardTitle className="flex items-center gap-2 text-xl"><Wrench className="size-5" />工具覆盖</CardTitle><CardDescription>按标注工具统计期望次数、首选命中和平均候选排名，判断工具库是否真的可用。</CardDescription></CardHeader><CardContent><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>期望工具</TableHead><TableHead>期望次数</TableHead><TableHead>首选命中</TableHead><TableHead>命中率</TableHead><TableHead>平均排名</TableHead></TableRow></TableHeader><TableBody>{coverage.map((item) => <TableRow key={item.tool_name}><TableCell className="font-medium">{displayToolName(item.tool_name)}</TableCell><TableCell>{item.expected_count}</TableCell><TableCell>{item.top1_hits}/{item.expected_count}</TableCell><TableCell><StatusPill passed={item.accuracy >= 0.85} /><span className="ml-2 tabular-nums">{formatPercent(item.accuracy)}</span></TableCell><TableCell>{item.average_rank ? `Top ${item.average_rank}` : "未召回"}</TableCell></TableRow>)}</TableBody></Table></div></CardContent></Card>
}
function CaseResultsTable({ report, selectedCaseId, onSelectCase }: { report?: EvaluationReport; selectedCaseId: string; onSelectCase: (id: string) => void }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl"><ClipboardCheck className="size-5" />Case 结果</CardTitle>
        <CardDescription>每条样本都展示 expected vs selected，失败时可以定位是路由、工具、审批还是契约问题。</CardDescription>
      </CardHeader>
      <CardContent>
        {!report ? (
          <EmptyState text="运行 Benchmark 后显示 case 结果。" />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>样本</TableHead>
                  <TableHead>用户请求</TableHead>
                  <TableHead>期望工具</TableHead>
                  <TableHead>实际工具</TableHead>
                  <TableHead>Top@3</TableHead>
                  <TableHead>审批判断</TableHead>
                  <TableHead>输出契约</TableHead>
                  <TableHead>结论</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {report.cases.map((item) => (
                  <TableRow key={item.case_id} className={selectedCaseId === item.case_id ? "bg-secondary" : undefined} onClick={() => onSelectCase(item.case_id)}>
                    <TableCell className="font-medium">{item.case_id}</TableCell>
                    <TableCell className="min-w-[260px] max-w-[360px]"><span className="line-clamp-2 text-sm text-muted-foreground">{item.user_request}</span></TableCell>
                    <TableCell>{item.expected_tool}</TableCell>
                    <TableCell>{item.selected_tool}</TableCell>
                    <TableCell>{item.top3_tools.includes(item.expected_tool) ? <Badge className="bg-emerald-600">命中</Badge> : <Badge variant="outline" className="border-red-500/40 text-red-700">未命中</Badge>}</TableCell>
                    <TableCell>{item.expected_approval === item.actual_approval ? "正确" : "偏差"}</TableCell>
                    <TableCell>{formatScore(item.contract_score)}</TableCell>
                    <TableCell><StatusPill passed={item.result === "passed"} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function CaseInspector({ selectedCase }: { selectedCase?: EvaluationCaseResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl"><GitBranch className="size-5" />Case Explorer</CardTitle>
        <CardDescription>点击表格行后查看 Top 5 候选、审批判断和失败原因。</CardDescription>
      </CardHeader>
      <CardContent>
        {!selectedCase ? <EmptyState text="选择一个 case 查看明细。" /> : (
          <div className="grid gap-4">
            <div className="rounded-lg border bg-background/70 p-4 text-sm leading-6">{selectedCase.user_request}</div>
            <div className="grid gap-3 md:grid-cols-2">
              <MiniMetric label="Expected Tool" value={selectedCase.expected_tool} />
              <MiniMetric label="Selected Tool" value={selectedCase.selected_tool} />
              <MiniMetric label="Expected Approval" value={selectedCase.expected_approval ? "需要审批" : "无需审批"} />
              <MiniMetric label="Actual Approval" value={selectedCase.actual_approval ? "需要审批" : "无需审批"} />
            </div>
            <div className="rounded-lg border bg-background/70 p-4">
              <div className="text-sm font-bold">Top 5 Ranked Tools</div>
              <div className="mt-3 flex flex-wrap gap-2">{selectedCase.top5_tools.map((tool) => <Badge key={tool} variant={tool === selectedCase.expected_tool ? "default" : "secondary"}>{tool}</Badge>)}</div>
            </div>
            <div className="rounded-lg border bg-background/70 p-4">
              <div className="text-sm font-bold">输出契约条款</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedCase.matched_contract_terms.map((term) => <Badge key={term} className="bg-emerald-600">{term}</Badge>)}
                {selectedCase.missing_contract_terms.map((term) => <Badge key={term} variant="outline" className="border-red-500/40 text-red-700">缺失：{term}</Badge>)}
              </div>
            </div>
            {selectedCase.failure_reason ? <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm leading-6 text-red-800">{selectedCase.failure_reason}</div> : <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm text-emerald-800">该 case 已通过。</div>}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function FailureAnalysis({ failures }: { failures: EvaluationFailureAnalysis[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl"><AlertTriangle className="size-5" />失败样本分析</CardTitle>
        <CardDescription>失败不是只显示 none，而是给出可修复方向。</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {failures.length === 0 ? <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm text-emerald-800">当前 benchmark 没有失败样本。</div> : failures.map((failure) => (
          <div key={failure.case_id} className="rounded-lg border bg-background/70 p-4">
            <div className="flex flex-wrap items-center gap-2"><Badge variant="outline">{failure.case_id}</Badge><span className="font-bold">{failure.category}</span></div>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">{failure.reason}</p>
            <p className="mt-2 text-sm leading-6 text-amber-700">建议：{failure.recommendation}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function SingleRunStudio({ runs, selectedRunId, selectedRun, audit, summary, isAuditLoading, onSelectRun, onRefresh }: { runs: RunEvaluationSourceRun[]; selectedRunId: string; selectedRun?: RunEvaluationSourceRun; audit?: RunEvaluationResult; summary?: AgentSummary; isAuditLoading: boolean; onSelectRun: (id: string) => void; onRefresh: () => void }) {
  const passedChecks = audit?.decision_checks.filter((check) => check.passed).length ?? 0
  const checkCount = audit?.decision_checks.length ?? 0
  return (
    <div className="space-y-6">
      <div className="grid items-start gap-6 xl:grid-cols-[420px_1fr]">
        <RunSelector selectedRunId={selectedRunId} runs={runs} onChange={onSelectRun} onRefresh={onRefresh} />
        <DecisionHero audit={audit} isLoading={isAuditLoading} />
      </div>
      <div className="grid items-start gap-6 xl:grid-cols-[1fr_420px]">
        <DecisionChecks audit={audit} />
        <RunOutcome run={selectedRun} audit={audit} />
      </div>
      <ToolAlternatives audit={audit} />
      <ScoreSummary audit={audit} summary={summary} passedChecks={passedChecks} checkCount={checkCount} />
    </div>
  )
}

function RunSelector({ selectedRunId, runs, onChange, onRefresh }: { selectedRunId: string; runs: RunEvaluationSourceRun[]; onChange: (value: string) => void; onRefresh: () => void }) {
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? runs[0]
  return (
    <Card>
      <CardHeader className="md:grid-cols-[1fr_auto]">
        <div>
          <CardTitle className="flex items-center gap-2 text-xl"><Wrench className="size-5" />单次运行评估</CardTitle>
          <CardDescription>选择一次真实 Agent Run，评估工具选择、Trace 和输出契约。</CardDescription>
        </div>
        <Button type="button" variant="outline" onClick={onRefresh} disabled={!selectedRun}><RefreshCw />刷新</Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <label className="grid gap-2 text-sm font-medium">
          运行记录
          <select className="h-10 rounded-lg border bg-card px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/30" value={selectedRun?.id ?? ""} onChange={(event) => onChange(event.target.value)}>
            {runs.map((run) => <option key={run.id} value={run.id}>{scenarioLabel(run.scenario)} · {run.selected_tool ?? "未选工具"} · {run.id.slice(0, 8)}</option>)}
          </select>
        </label>
        {selectedRun ? <div className="grid gap-3 rounded-lg border bg-background/70 p-4 text-sm"><div className="font-bold">{selectedRun.selected_tool ?? "未选择工具"}</div><div className="grid grid-cols-3 gap-2"><MiniMetric label="置信度" value={formatScore(selectedRun.confidence)} /><MiniMetric label="可靠性" value={formatScore(selectedRun.reliability_score)} /><MiniMetric label="Trace" value={String(selectedRun.steps.length)} /></div></div> : <EmptyState text="请先运行一个任务，再回来查看评估。" />}
      </CardContent>
    </Card>
  )
}

type RunEvaluationSourceRun = {
  id: string
  scenario: string
  selected_tool?: string | null
  status: string
  risk_level: string
  confidence: number
  reliability_score: number
  final_answer?: string | null
  steps: unknown[]
}

function ScorersStudio({ scorers, audit }: { scorers: ScorerDefinition[]; audit?: RunEvaluationResult }) {
  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_420px]">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl"><FlaskConical className="size-5" />内置 Scorer</CardTitle>
          <CardDescription>Scorer 是底层规则包，用来做通用可靠性、场景适配和领域规则校验，不再挤在 Benchmark 主页面。</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          {scorers.map((scorer) => <div key={scorer.id ?? scorer.name} className="rounded-lg border bg-background/70 p-4"><div className="flex items-center justify-between gap-3"><span className="font-bold">{scorer.name}</span><Badge variant="outline">{scorer.level}</Badge></div><div className="mt-2 text-sm text-muted-foreground">{scorer.rules.length} 条规则 · 阈值 {formatPercent(scorer.aggregation.pass_threshold)}</div></div>)}
        </CardContent>
      </Card>
      <EvaluatorLayers audit={audit} />
    </div>
  )
}

function displayToolName(tool?: string | null) {
  if (!tool) return "未选择"
  const normalized = tool.toLowerCase()
  const map: Record<string, string> = {
    data_frame_profiler: "数据表画像工具",
    http_api_connector: "HTTP API 连接器",
    hybrid_knowledge_search: "混合知识检索",
    graph_neighbor_expand: "图邻居扩展",
    workflow_state_transition: "流程状态迁移",
    approval_gate: "审批关卡",
    python_sandbox_runner: "Python 沙箱",
    memory_write_policy: "记忆写入策略",
  }
  return map[normalized] ?? tool
}

function buildDecisionSummary(audit: RunEvaluationResult) {
  const toolName = displayToolName(audit.selected_tool_label ?? audit.selected_tool)
  const scenario = scenarioLabel(audit.scenario)
  const failedChecks = audit.decision_checks.filter((check) => !check.passed)
  if (audit.decision_verdict === "ready" && audit.passed) return `${scenario}任务的工具决策已通过审计。系统选择了${toolName}，关键检查均已通过，当前结果可以采信。`
  if (failedChecks.length) return `${scenario}任务需要复核。系统选择了${toolName}，但 ${failedChecks.map((check) => check.name).join("、")} 未完全通过。`
  return `${scenario}任务需要复核。系统选择了${toolName}，但整体决策还没有达到可直接采信状态。`
}

function buildRunOutcomeSummary(run?: RunEvaluationSourceRun, audit?: RunEvaluationResult) {
  if (!run) return "还没有运行记录。请先在“任务”页点击“运行 Runtime”。"
  const toolName = displayToolName(audit?.selected_tool_label ?? audit?.selected_tool ?? run.selected_tool)
  const finalAnswer = run.final_answer ?? ""
  const needsApproval = run.status === "needs_human" || finalAnswer.includes("approval_checkpoint_required") || finalAnswer.includes("Human approval is required")
  if (run.scenario === "external_api") return needsApproval ? `系统已完成外部接口任务的方案校验，并选择${toolName}生成了幂等动作计划。由于该任务涉及高风险或客户可见操作，当前停在人工审批关卡，审批通过后才能执行真实变更。` : `系统已完成外部接口任务处理，选择${toolName}完成接口方案校验和执行计划生成。完整请求约束与 Trace 可在运行页查看。`
  if (run.scenario === "analysis") return `系统已完成数据分析任务处理，选择${toolName}进行数据画像。字段数量、缺失值、数值摘要、分类摘要和异常提示可在“运行”页的 Executor 步骤查看。`
  if (run.scenario === "workflow") return `系统已完成流程任务规划，选择${toolName}处理执行链路。审批关卡、依赖节点和 Critic 结论可在完整 Trace 中查看。`
  if (finalAnswer) return `系统已完成${scenarioLabel(run.scenario)}任务，最终选择${toolName}。完整执行细节可在运行页 Trace 中查看。`
  return "当前运行没有最终摘要。请到“运行”页查看 Executor 步骤的输出快照。"
}

function DecisionHero({ audit, isLoading }: { audit?: RunEvaluationResult; isLoading: boolean }) {
  if (!audit) return <Card><CardContent className="p-6 text-sm text-muted-foreground">{isLoading ? "正在加载评估结论" : "暂未生成运行评估"}</CardContent></Card>
  const verdictReady = audit.decision_verdict === "ready" && audit.passed
  const failedChecks = audit.decision_checks.filter((check) => !check.passed)
  return (
    <Card className={verdictReady ? "bg-[#f0fff8]" : "bg-[#fff8ed]"}>
      <CardHeader>
        <div className="section-label">最终判断</div>
        <CardTitle className="mt-2 flex flex-wrap items-center gap-3 text-2xl">{verdictReady ? <CheckCircle2 className="size-6 text-emerald-600" /> : <AlertTriangle className="size-6 text-amber-600" />}{verdictReady ? "评估通过，可以作为有效结果" : "需要复核后再采信"}</CardTitle>
        <CardDescription>{buildDecisionSummary(audit)}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-3 rounded-lg border bg-card p-5"><div className="flex flex-wrap gap-2"><Badge variant="secondary">{scenarioLabel(audit.scenario)}</Badge>{audit.selected_tool_risk ? <Badge variant="outline" className={riskClass(audit.selected_tool_risk)}>{riskLabel(audit.selected_tool_risk)}</Badge> : null}</div><div><div className="text-sm text-muted-foreground">最终选择工具</div><div className="mt-1 text-xl font-bold">{displayToolName(audit.selected_tool_label ?? audit.selected_tool)}</div></div><div className="grid gap-2 text-sm text-muted-foreground"><div>判断方法：看场景是否匹配、工具选择是否合理、风险审批是否被正确触发、执行与 Critic 是否通过。</div>{failedChecks.length ? <div className="text-amber-700">需关注：{failedChecks.map((check) => check.name).join("、")}</div> : <div className="text-emerald-700">所有关键检查均已通过。</div>}</div></div>
      </CardContent>
    </Card>
  )
}

function RunOutcome({ run, audit }: { run?: RunEvaluationSourceRun; audit?: RunEvaluationResult }) {
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-xl"><GitBranch className="size-5" />最终处理结果</CardTitle><CardDescription>这里展示面向用户的处理结论；完整数据画像和每一步执行细节仍可在“运行”页 Trace 中查看。</CardDescription></CardHeader>
      <CardContent className="grid gap-4">
        {run ? <><div className="flex flex-wrap gap-2"><Badge variant="outline" className={statusClass(run.status)}>{statusLabel(run.status)}</Badge><Badge variant="secondary">{scenarioLabel(run.scenario)}</Badge><Badge variant="outline" className={riskClass(run.risk_level)}>{riskLabel(run.risk_level)}</Badge></div><div className="rounded-lg border bg-background/70 p-4 text-sm leading-6 text-muted-foreground">{buildRunOutcomeSummary(run, audit)}</div><div className="grid grid-cols-2 gap-3 text-sm"><MiniMetric label="所选工具" value={displayToolName(audit?.selected_tool_label ?? audit?.selected_tool ?? run.selected_tool)} /><MiniMetric label="Trace 步骤" value={String(run.steps.length)} /></div><Button asChild variant="outline"><Link to="/runs">去运行页看完整 Trace <ArrowRight className="size-4" /></Link></Button></> : <EmptyState text="还没有运行记录。请先在任务页点击运行 Runtime。" />}
      </CardContent>
    </Card>
  )
}

function DecisionChecks({ audit }: { audit?: RunEvaluationResult }) {
  return <Card><CardHeader><CardTitle className="flex items-center gap-2 text-xl"><ClipboardCheck className="size-5" />为什么这么判断</CardTitle><CardDescription>只看这几项就够了：场景、工具排序、风险审批、执行和 Critic。</CardDescription></CardHeader><CardContent>{audit ? <div className="grid gap-3 md:grid-cols-2">{audit.decision_checks.map((check) => <DecisionCheckCard key={check.name} check={check} />)}</div> : <EmptyState text="选择运行记录后加载决策检查。" />}</CardContent></Card>
}

function DecisionCheckCard({ check }: { check: ToolDecisionCheck }) {
  return <div className="rounded-lg border bg-background/70 p-4"><div className="flex items-start justify-between gap-3"><div><div className="font-bold">{check.name}</div><p className="mt-2 text-sm leading-6 text-muted-foreground">{check.explanation}</p></div>{check.passed ? <CheckCircle2 className="size-5 shrink-0 text-emerald-600" /> : <XCircle className="size-5 shrink-0 text-red-600" />}</div><div className="mt-4 flex flex-wrap items-center gap-2"><Badge variant="outline">{formatScore(check.score)}</Badge><span className="text-xs text-muted-foreground">{check.signal}</span></div></div>
}

function ToolAlternatives({ audit }: { audit?: RunEvaluationResult }) {
  return <Card><CardHeader><CardTitle className="flex items-center gap-2 text-xl"><GitBranch className="size-5" />候选工具排序</CardTitle><CardDescription>如果第一名就是最终工具，且分数明显高于备选，一般说明工具选择比较稳。</CardDescription></CardHeader><CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{audit?.tool_alternatives.length ? audit.tool_alternatives.map((tool, index) => <div key={`${String(tool.name)}-${index}`} className={`rounded-lg border p-4 ${index === 0 ? "bg-secondary" : "bg-background/70"}`}><div className="flex items-center justify-between gap-3"><div className="font-bold">{displayToolName(String(tool.label ?? tool.name))}</div><Badge variant="outline">{formatScore(Number(tool.score ?? 0))}</Badge></div><div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground"><span>{scenarioLabel(String(tool.scenario ?? "general"))}</span><span>{riskLabel(String(tool.risk_level ?? "unknown"))}</span>{index === 0 ? <span>排序第一</span> : null}</div></div>) : <EmptyState text="本次运行没有捕获候选工具排序。" />}</CardContent></Card>
}

function EvaluatorLayers({ audit }: { audit?: RunEvaluationResult }) {
  const grouped = useMemo(() => Object.entries(audit?.grouped_scores ?? {}), [audit])
  return <Card><CardHeader><CardTitle className="flex items-center gap-2 text-xl"><ShieldCheck className="size-5" />Scorer 预览</CardTitle><CardDescription>显示当前单次运行在底层 scorer 上的评分结果。</CardDescription></CardHeader><CardContent className="grid gap-4">{grouped.length ? <div className="grid gap-3 sm:grid-cols-3">{grouped.map(([level, score]) => <MiniMetric key={level} label={`${level}层`} value={formatScore(score)} />)}</div> : null}{audit ? <div className="grid gap-3">{audit.results.map((item) => <LayerResultCard key={item.name} result={item} />)}</div> : <EmptyState text="暂无 scorer 预览。" />}</CardContent></Card>
}

function LayerResultCard({ result }: { result: ScorerScoreResult }) {
  const passedRules = result.rules.filter((rule) => rule.passed).length
  return <div className="rounded-lg border bg-background/70 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><div className="font-bold">{result.name}</div><Badge variant="outline">{result.level}</Badge></div><p className="mt-1 text-sm text-muted-foreground">通过 {passedRules}/{result.rules.length} 条规则</p></div><div className="text-right"><div className="text-lg font-bold tabular-nums">{formatScore(result.score)}</div><StatusPill passed={result.passed} /></div></div></div>
}

function ScoreSummary({ audit, summary, passedChecks, checkCount }: { audit?: RunEvaluationResult; summary?: AgentSummary; passedChecks: number; checkCount: number }) {
  return <Card className="bg-background/70"><CardHeader className="pb-3"><CardTitle className="flex items-center gap-2 text-base"><Gauge className="size-4" />评分摘要</CardTitle><CardDescription>辅助参考，不作为主界面的第一判断入口。</CardDescription></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><ScoreMetric icon={Gauge} label="决策分数" value={audit ? formatScore(audit.score) : "0.00"} /><ScoreMetric icon={ClipboardCheck} label="通过检查" value={checkCount ? `${passedChecks}/${checkCount}` : "0/0"} /><ScoreMetric icon={ShieldCheck} label="Runtime 可靠性" value={summary ? formatScore(summary.average_reliability_score) : "0.00"} /><ScoreMetric icon={Gauge} label="自动完成率" value={summary ? formatPercent(summary.success_rate) : "0%"} /></CardContent></Card>
}

function ScoreMetric({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return <div className="rounded-lg border bg-card p-3"><div className="flex items-center justify-between gap-2 text-xs font-semibold text-muted-foreground"><span>{label}</span><Icon className="size-3 text-primary" /></div><div className="mt-2 text-lg font-bold tabular-nums">{value}</div></div>
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border bg-card p-3"><div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">{label}</div><div className="mt-2 font-bold tabular-nums break-words">{value}</div></div>
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-lg border bg-background/70 p-4 text-sm text-muted-foreground">{text}</div>
}

function StatusPill({ passed }: { passed: boolean }) {
  return <Badge variant="outline" className={passed ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700" : "border-red-500/40 bg-red-500/10 text-red-700"}>{passed ? "通过" : "失败"}</Badge>
}

function metricLabel(name: string) {
  const map: Record<string, string> = {
    "Tool Top@1 Accuracy": "Tool Top@1",
    "Tool Top@3 Recall": "Tool Top@3",
    "Tool Top@5 Recall": "Tool Top@5",
    "Scenario Accuracy": "场景准确率",
    "Approval Accuracy": "审批准确率",
    "Trace Completeness": "Trace 完整率",
    "Output Contract Coverage": "输出契约覆盖率",
  }
  return map[name] ?? name
}

















