import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  RefreshCw,
  ShieldCheck,
  Users,
  XCircle,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { useState } from "react"

import { type UserPublic, UsersService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { AetherFlowApi, type OperationsQueueItem } from "@/lib/aetherflow-api"
import { formatPercent, formatScore, riskClass, riskLabel, scenarioLabel, statusClass, statusLabel, toolLabel } from "@/lib/aetherflow-format"

export const Route = createFileRoute("/_layout/operations")({
  component: Operations,
  beforeLoad: async () => {
    const user: UserPublic = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({ meta: [{ title: "运营总览 - AetherFlow" }] }),
})

function Operations() {
  const [team, setTeam] = useState("")
  const [status, setStatus] = useState("")
  const dashboardQuery = useQuery({
    queryKey: ["aetherflow", "operations", team, status],
    queryFn: () => AetherFlowApi.readOperationsDashboard({ team: team || undefined, status: status || undefined, limit: 40 }),
  })
  const dashboard = dashboardQuery.data
  const summary = dashboard?.summary

  return (
    <div className="page-shell gap-6">
      <header className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <div>
          <div className="page-kicker">管理中心 · 运营总览</div>
          <h1 className="page-title mt-2 text-3xl md:text-4xl">公司工作运行情况</h1>
          <p className="page-description mt-3 text-base md:text-lg">从任务分配到人工确认，集中查看团队当前正在处理的工作和运行质量。</p>
        </div>
        <Button variant="outline" onClick={() => void dashboardQuery.refetch()} disabled={dashboardQuery.isFetching}>
          <RefreshCw className={dashboardQuery.isFetching ? "size-4 animate-spin" : "size-4"} />刷新数据
        </Button>
      </header>

      {dashboardQuery.isError ? <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm leading-6 text-red-700">运营数据暂时无法加载：{dashboardQuery.error instanceof Error ? dashboardQuery.error.message : "请稍后重试"}</div> : null}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Stat icon={Activity} label="任务总数" value={String(summary?.total_tasks ?? 0)} hint={`${summary?.active_tasks ?? 0} 项进行中`} />
        <Stat icon={Clock3} label="待确认" value={String(summary?.approval_queue ?? 0)} hint="需要负责人完成最后一步" tone={summary?.approval_queue ? "amber" : undefined} />
        <Stat icon={CheckCircle2} label="运行成功率" value={formatPercent(summary?.success_rate ?? 0)} hint={`${summary?.successful_runs ?? 0} 次成功或恢复`} tone="green" />
        <Stat icon={XCircle} label="失败运行" value={String(summary?.failed_runs ?? 0)} hint={`${summary?.failed_tasks ?? 0} 个任务失败`} tone={summary?.failed_runs ? "red" : undefined} />
        <Stat icon={ShieldCheck} label="平均可靠性" value={formatScore(summary?.average_reliability ?? 0)} hint={`${summary?.total_runs ?? 0} 次运行样本`} />
      </section>

      {summary?.approval_queue ? <div className="flex flex-col justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50/70 px-4 py-3 text-sm text-amber-900 sm:flex-row sm:items-center"><div className="flex items-center gap-2"><AlertTriangle className="size-4 shrink-0" /><span>当前有 {summary.approval_queue} 项工作等待人工确认，建议优先处理高风险任务。</span></div><Button asChild size="sm" variant="outline" className="border-amber-300 bg-background text-amber-900 hover:bg-amber-100"><Link to="/runs">打开处理记录</Link></Button></div> : null}

      <section className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.8fr)]">
        <Card className="min-w-0">
          <CardHeader className="gap-4 border-b sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2"><Activity className="size-5 text-primary" />当前工作队列</CardTitle>
              <CardDescription className="mt-1.5">按最近活动查看全公司的任务、负责人和处理状态。</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <select value={team} onChange={(event) => setTeam(event.target.value)} aria-label="按团队筛选" className="h-9 rounded-md border border-input bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20">
                <option value="">全部团队</option>
                {dashboard?.teams.map((item) => <option key={item.team} value={item.team}>{item.team}</option>)}
              </select>
              <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="按状态筛选" className="h-9 rounded-md border border-input bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20">
                <option value="">全部状态</option>
                <option value="needs_human">待确认</option>
                <option value="running">运行中</option>
                <option value="succeeded">已完成</option>
                <option value="recovered">已恢复</option>
                <option value="failed">失败</option>
                <option value="not_started">未运行</option>
              </select>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>工作</TableHead>
                  <TableHead>负责人 / 团队</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>风险</TableHead>
                  <TableHead>最近活动</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dashboardQuery.isLoading ? <TableRow><TableCell colSpan={5} className="py-12 text-center text-muted-foreground">正在读取公司工作队列…</TableCell></TableRow> : dashboard?.queue.length ? dashboard.queue.map((item) => <QueueRow key={item.run_id || item.task_id} item={item} />) : <TableRow><TableCell colSpan={5} className="py-12 text-center text-muted-foreground">当前筛选条件下没有工作记录</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Users className="size-5 text-primary" />团队负载与质量</CardTitle>
            <CardDescription>用任务量、审批积压和成功率判断团队是否需要支持。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {dashboard?.teams.length ? dashboard.teams.map((item) => <div key={item.team} className="rounded-lg border p-4">
              <div className="flex items-center justify-between gap-3"><div className="min-w-0 truncate font-semibold">{item.team}</div><span className="text-sm font-bold tabular-nums">{formatPercent(item.success_rate)}</span></div>
              <div className="mt-3 grid grid-cols-3 gap-3 text-xs"><div><div className="text-muted-foreground">任务</div><div className="mt-1 font-semibold">{item.task_count}</div></div><div><div className="text-muted-foreground">待确认</div><div className={`mt-1 font-semibold ${item.approval_queue_count ? "text-amber-700" : ""}`}>{item.approval_queue_count}</div></div><div><div className="text-muted-foreground">可靠性</div><div className="mt-1 font-semibold">{formatScore(item.average_reliability)}</div></div></div>
            </div>) : <div className="py-10 text-center text-sm text-muted-foreground">暂无团队数据</div>}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

function QueueRow({ item }: { item: OperationsQueueItem }) {
  const isPending = item.run_status === "needs_human"
  return <TableRow>
    <TableCell className="min-w-[250px] whitespace-normal">
      <div className="font-semibold leading-5">{item.title}</div>
      <div className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{item.objective}</div>
      <div className="mt-2 flex flex-wrap gap-1.5"><Badge variant="secondary">{scenarioLabel(item.scenario)}</Badge>{item.selected_tool ? <span className="text-xs text-muted-foreground">{toolLabel(item.selected_tool)}</span> : null}</div>
    </TableCell>
    <TableCell className="whitespace-normal"><div className="font-medium">{item.owner_name}</div><div className="mt-1 text-xs text-muted-foreground">{item.owner_team} · {item.owner_email}</div></TableCell>
    <TableCell><Badge variant="outline" className={statusClass(item.run_status)}>{item.run_status === "not_started" ? "未运行" : statusLabel(item.run_status)}</Badge>{isPending ? <div className="mt-1 text-xs text-amber-700">等待确认</div> : null}</TableCell>
    <TableCell><Badge variant="outline" className={riskClass(item.risk_level)}>{riskLabel(item.risk_level)}</Badge></TableCell>
    <TableCell className="text-xs text-muted-foreground">{formatTime(item.completed_at || item.created_at)}</TableCell>
  </TableRow>
}

function Stat({ icon: Icon, label, value, hint, tone }: { icon: LucideIcon; label: string; value: string; hint: string; tone?: "amber" | "green" | "red" }) {
  const toneClass = tone === "amber" ? "text-amber-700" : tone === "green" ? "text-emerald-700" : tone === "red" ? "text-red-700" : "text-foreground"
  return <div className="rounded-lg border bg-card p-4 shadow-sm"><div className="flex items-center justify-between gap-3"><span className="text-sm text-muted-foreground">{label}</span><Icon className={`size-4 ${toneClass}`} /></div><div className={`mt-3 text-2xl font-bold tracking-tight tabular-nums ${toneClass}`}>{value}</div><div className="mt-1 text-xs text-muted-foreground">{hint}</div></div>
}

function formatTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
}
