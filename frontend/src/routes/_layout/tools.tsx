import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Gauge, Network, ShieldCheck, Wrench } from "lucide-react"

import { Badge } from "@/components/ui/badge"
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
import { AetherFlowApi } from "@/lib/aetherflow-api"
import { formatPercent, riskClass, riskLabel, scenarioLabel } from "@/lib/aetherflow-format"

export const Route = createFileRoute("/_layout/tools")({
  component: Tools,
  head: () => ({ meta: [{ title: "工具注册表 - AetherFlow" }] }),
})

const policies = [
  ["场景优先", "Runtime 会先约束场景，再对候选工具排序。"],
  ["风险感知", "高风险工具会进入审批关卡，而不是直接执行写操作。"],
  ["全程可观测", "每次工具决策都会保存分数、延迟、置信度和输入摘要。"],
]

function Tools() {
  const toolsQuery = useQuery({ queryKey: ["aetherflow", "tools"], queryFn: AetherFlowApi.readTools })
  const tools = toolsQuery.data ?? []

  return (
    <div className="page-shell">
      <div className="space-y-3">
        <div className="page-kicker">工具治理</div>
        <h1 className="page-title text-3xl md:text-4xl">Tool / MCP 注册表</h1>
        <p className="max-w-3xl text-base leading-7 text-muted-foreground">面向企业工作流 Agent 的可治理工具选择层。</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {policies.map(([title, body]) => (
          <Card key={title}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="size-4" />{title}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm leading-6 text-muted-foreground">{body}</CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl"><Wrench className="size-5" />已注册工具</CardTitle>
          <CardDescription>工具评分会综合场景匹配、语义匹配、历史成功率、风险和延迟。</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>工具</TableHead>
                <TableHead>场景</TableHead>
                <TableHead>风险</TableHead>
                <TableHead>成功率</TableHead>
                <TableHead>延迟</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tools.map((tool) => (
                <TableRow key={tool.name}>
                  <TableCell>
                    <div className="font-medium">{tool.label}</div>
                    <div className="text-xs text-muted-foreground">{tool.description}</div>
                  </TableCell>
                  <TableCell><Badge variant="secondary"><Network className="size-3" />{scenarioLabel(tool.scenario)}</Badge></TableCell>
                  <TableCell><Badge variant="outline" className={riskClass(tool.risk_level)}>{riskLabel(tool.risk_level)}</Badge></TableCell>
                  <TableCell><span className="inline-flex items-center gap-1"><Gauge className="size-3" />{formatPercent(tool.success_rate)}</span></TableCell>
                  <TableCell>{tool.avg_latency_ms}ms</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
