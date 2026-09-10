import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  Bot,
  CheckSquare,
  ListPlus,
  Play,
  Plus,
  ShieldAlert,
  Wand2,
} from "lucide-react"
import type { ChangeEvent, FormEvent } from "react"
import { useMemo, useState } from "react"
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
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { AetherFlowApi, type WorkflowTaskCreate } from "@/lib/aetherflow-api"
import {
  priorityClass,
  priorityLabel,
  riskClass,
  riskLabel,
  scenarioLabel,
  statusClass,
  statusLabel,
} from "@/lib/aetherflow-format"

export const Route = createFileRoute("/_layout/tasks")({
  component: Tasks,
  head: () => ({
    meta: [{ title: "提交任务 - AetherFlow" }],
  }),
})

const emptyForm: WorkflowTaskCreate = {
  title: "",
  objective: "",
  context: "",
  expected_output: "",
  scenario_hint: "workflow",
  priority: "medium",
  status: "ready",
  risk_level: "medium",
  requires_approval: false,
  owner_team: "",
  tags: [],
}

const scenarioOptions = [
  { value: "knowledge", label: "知识检索" },
  { value: "workflow", label: "业务流程" },
  { value: "code", label: "代码任务" },
  { value: "analysis", label: "数据分析" },
  { value: "external_api", label: "外部接口" },
  { value: "general", label: "通用任务" },
]
const priorityOptions = [
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
  { value: "critical", label: "紧急" },
]
const riskOptions = [
  { value: "low", label: "低风险" },
  { value: "medium", label: "中风险" },
  { value: "high", label: "高风险" },
]

const scenarioValues = scenarioOptions.map((item) => item.value)
const priorityValues = priorityOptions.map((item) => item.value)
const riskValues = riskOptions.map((item) => item.value)

const scenarioAliases: Record<string, string> = {
  knowledge: "knowledge",
  知识: "knowledge",
  知识检索: "knowledge",
  文档问答: "knowledge",
  workflow: "workflow",
  流程: "workflow",
  业务流程: "workflow",
  工作流: "workflow",
  code: "code",
  代码: "code",
  代码任务: "code",
  analysis: "analysis",
  分析: "analysis",
  数据分析: "analysis",
  数据: "analysis",
  external_api: "external_api",
  api: "external_api",
  外部接口: "external_api",
  接口: "external_api",
  general: "general",
  通用: "general",
  通用任务: "general",
}

const priorityAliases: Record<string, string> = {
  low: "low",
  低: "low",
  低优先级: "low",
  medium: "medium",
  中: "medium",
  中优先级: "medium",
  high: "high",
  高: "high",
  高优先级: "high",
  critical: "critical",
  紧急: "critical",
  关键: "critical",
}

const riskAliases: Record<string, string> = {
  low: "low",
  低: "low",
  低风险: "low",
  medium: "medium",
  中: "medium",
  中风险: "medium",
  high: "high",
  高: "high",
  高风险: "high",
}

type TaskField = keyof WorkflowTaskCreate

const fieldAliasEntries: Array<[string, TaskField]> = [
  ["title", "title"],
  ["标题", "title"],
  ["任务标题", "title"],
  ["name", "title"],
  ["名称", "title"],
  ["objective", "objective"],
  ["目标", "objective"],
  ["任务目标", "objective"],
  ["需求", "objective"],
  ["context", "context"],
  ["上下文", "context"],
  ["数据", "context"],
  ["数据内容", "context"],
  ["csv", "context"],
  ["expected_output", "expected_output"],
  ["expected output", "expected_output"],
  ["预期输出", "expected_output"],
  ["输出要求", "expected_output"],
  ["scenario_hint", "scenario_hint"],
  ["scenario", "scenario_hint"],
  ["场景", "scenario_hint"],
  ["场景提示", "scenario_hint"],
  ["priority", "priority"],
  ["优先级", "priority"],
  ["status", "status"],
  ["状态", "status"],
  ["risk_level", "risk_level"],
  ["risk", "risk_level"],
  ["风险", "risk_level"],
  ["风险等级", "risk_level"],
  ["requires_approval", "requires_approval"],
  ["approval", "requires_approval"],
  ["需要审批", "requires_approval"],
  ["是否审批", "requires_approval"],
  ["owner_team", "owner_team"],
  ["team", "owner_team"],
  ["团队", "owner_team"],
  ["负责团队", "owner_team"],
  ["tags", "tags"],
  ["标签", "tags"],
]

const fieldAliases = Object.fromEntries(
  fieldAliasEntries.map(([name, field]) => [normalizeKey(name), field]),
) as Record<string, TaskField>

const taskTableExample = `标题,目标,数据,预期输出,场景,优先级,风险等级,是否审批,负责团队,标签
分析客户续费风险CSV,对这份客户续费数据做字段画像，识别缺失值、异常值和分类分布。,"customer_id,行业,套餐,地区,月收入,服务请求数,流失风险\nC001,金融,企业版,华东,1680,2,0.18\nC002,零售,基础版,华南,79,9,0.74\nC003,教育,专业版,华北,240,1,0.21\nC004,医疗,企业版,华东,,0,0.09\nC005,零售,基础版,华南,69,15,0.91",字段数量、缺失值、数值统计、分类统计、异常提示,数据分析,高,中风险,否,data-ops,"CSV,画像,工具路由"
审计开户流程证据,检查开户流程是否证据充足，并判断高风险步骤是否需要审批。,步骤：收集合同、验证身份、创建CRM账户、发送欢迎邮件。风险：外部接口写入可能影响客户记录。,输出DAG、证据覆盖、审批判断和最终工具选择,业务流程,中,高风险,是,ops,"流程,审批,证据"`

const rawCsvExample = `客户编号,行业,套餐,地区,月收入,坐席数,近30天请求数,使用小时,流失风险
C001,金融,企业版,华东,1680,42,2,311,0.18
C002,零售,基础版,华南,79,3,9,18,0.74
C003,教育,专业版,华北,240,8,1,96,0.21
C004,医疗,企业版,华东,,55,0,402,0.09
C005,零售,基础版,华南,69,3,15,9,0.91
C006,制造,专业版,华东,310,11,3,121,0.29
C007,金融,企业版,华北,9999,39,1,287,0.12
C008,教育,基础版,华南,59,2,7,14,0.68`

type BatchParseResult = {
  tasks: WorkflowTaskCreate[]
  error?: string
  source: "empty" | "json" | "jsonl" | "task_table" | "raw_dataset" | "invalid"
}

type BatchMutationInput = {
  tasks: WorkflowTaskCreate[]
  runAfterCreate: boolean
}

function normalizeKey(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, "_")
}

function asText(value: unknown): string | null {
  if (typeof value !== "string") return null
  const trimmed = value.trim()
  return trimmed.length ? trimmed : null
}

function normalizeAliasedChoice(
  value: unknown,
  aliases: Record<string, string>,
  allowedValues: string[],
  fallback: string,
): string {
  const text = asText(value)
  if (!text) return fallback
  const normalized = aliases[normalizeKey(text)] ?? normalizeKey(text)
  return allowedValues.includes(normalized) ? normalized : fallback
}

function normalizeBoolean(value: unknown): boolean {
  if (typeof value === "boolean") return value
  if (typeof value === "number") return value === 1
  const text = asText(value)
  if (!text) return false
  const normalized = normalizeKey(text)
  return ["true", "yes", "y", "1", "是", "需要", "需审批", "需要审批"].includes(
    normalized,
  )
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((tag) => (typeof tag === "string" ? tag.trim() : ""))
      .filter(Boolean)
  }
  if (typeof value === "string") {
    return value
      .split(/[,，;；|]/)
      .map((tag) => tag.trim())
      .filter(Boolean)
  }
  return []
}

function normalizeTaskRecord(raw: Record<string, unknown>) {
  const normalized: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(raw)) {
    const mappedKey = fieldAliases[normalizeKey(key)] ?? key
    normalized[mappedKey] = value
  }
  return normalized
}

function normalizeBatchTask(value: unknown, index: number): WorkflowTaskCreate {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`第 ${index + 1} 条数据必须是任务对象。`)
  }

  const raw = normalizeTaskRecord(value as Record<string, unknown>)
  const title = asText(raw.title)
  const objective = asText(raw.objective)

  if (!title || !objective) {
    throw new Error(`第 ${index + 1} 条任务需要包含标题和目标。`)
  }

  return {
    title,
    objective,
    context: asText(raw.context),
    expected_output: asText(raw.expected_output),
    scenario_hint: normalizeAliasedChoice(
      raw.scenario_hint,
      scenarioAliases,
      scenarioValues,
      "analysis",
    ),
    priority: normalizeAliasedChoice(
      raw.priority,
      priorityAliases,
      priorityValues,
      "medium",
    ),
    status: normalizeAliasedChoice(
      raw.status,
      { ready: "ready", 就绪: "ready", draft: "draft", 草稿: "draft" },
      ["ready", "draft"],
      "ready",
    ),
    risk_level: normalizeAliasedChoice(
      raw.risk_level,
      riskAliases,
      riskValues,
      "medium",
    ),
    requires_approval: normalizeBoolean(raw.requires_approval),
    owner_team: asText(raw.owner_team),
    tags: normalizeTags(raw.tags),
  }
}

function detectDelimiter(line: string) {
  const candidates = ["\t", ",", "，", ";"]
  return candidates.reduce(
    (best, candidate) =>
      line.split(candidate).length > line.split(best).length ? candidate : best,
    ",",
  )
}

function parseDelimitedLine(line: string, delimiter: string) {
  const cells: string[] = []
  let cell = ""
  let inQuotes = false

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index]
    const next = line[index + 1]

    if (char === '"') {
      if (inQuotes && next === '"') {
        cell += '"'
        index += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }

    if (char === delimiter && !inQuotes) {
      cells.push(cell.trim())
      cell = ""
      continue
    }

    cell += char
  }

  cells.push(cell.trim())
  return cells
}

function parseDelimitedRows(input: string) {
  const lines = input
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  if (!lines.length) return []
  const delimiter = detectDelimiter(lines[0])
  return lines.map((line) => parseDelimitedLine(line, delimiter))
}

function parseTaskTable(rows: string[][]): WorkflowTaskCreate[] | null {
  if (rows.length < 2) return null

  const mappedHeaders = rows[0].map((header) => fieldAliases[normalizeKey(header)] ?? null)
  if (!mappedHeaders.includes("title") || !mappedHeaders.includes("objective")) {
    return null
  }

  return rows
    .slice(1)
    .filter((row) => row.some((cell) => cell.trim()))
    .map((row, rowIndex) => {
      const raw: Record<string, unknown> = {}
      mappedHeaders.forEach((field, columnIndex) => {
        if (field) raw[field] = row[columnIndex] ?? ""
      })
      return normalizeBatchTask(raw, rowIndex)
    })
}

function parseRawDataset(rows: string[][], input: string): WorkflowTaskCreate[] | null {
  const meaningfulRows = rows.filter((row) => row.some((cell) => cell.trim()))
  if (meaningfulRows.length < 2) return null

  const columns = meaningfulRows[0].filter(Boolean)
  if (columns.length < 2) return null

  return [
    {
      title: `分析导入数据集（${columns.length}列 ${meaningfulRows.length - 1}行）`,
      objective:
        "对导入的 CSV/TSV 数据进行字段画像，识别缺失值、数值分布、分类分布和异常提示，并说明为什么选择数据画像工具。",
      context: input,
      expected_output:
        "字段数量、缺失值、数值统计、分类统计、异常提示，以及工具选择依据。",
      scenario_hint: "analysis",
      priority: "medium",
      status: "ready",
      risk_level: "medium",
      requires_approval: false,
      owner_team: "data-ops",
      tags: ["数据导入", "CSV画像", "实际数据测试"],
    },
  ]
}

function parseBatchTasks(input: string): BatchParseResult {
  const trimmed = input.trim()
  if (!trimmed) return { tasks: [], source: "empty" }

  try {
    const parsed = JSON.parse(trimmed)
    const values = Array.isArray(parsed) ? parsed : [parsed]
    return {
      tasks: values.map((item, index) => normalizeBatchTask(item, index)),
      source: "json",
    }
  } catch (jsonError) {
    const lines = trimmed
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)

    if (lines.length > 1 && lines.every((line) => line.startsWith("{"))) {
      try {
        const values = lines.map((line) => JSON.parse(line))
        return {
          tasks: values.map((item, index) => normalizeBatchTask(item, index)),
          source: "jsonl",
        }
      } catch (lineError) {
        return {
          tasks: [],
          source: "invalid",
          error:
            lineError instanceof Error
              ? lineError.message
              : "JSON Lines 解析失败。",
        }
      }
    }

    const rows = parseDelimitedRows(trimmed)
    const taskTableTasks = parseTaskTable(rows)
    if (taskTableTasks?.length) {
      return { tasks: taskTableTasks, source: "task_table" }
    }

    const datasetTask = parseRawDataset(rows, trimmed)
    if (datasetTask?.length) {
      return { tasks: datasetTask, source: "raw_dataset" }
    }

    return {
      tasks: [],
      source: "invalid",
      error:
        jsonError instanceof Error
          ? "无法识别导入内容。请使用 JSON、JSON Lines、任务表 CSV/TSV，或直接粘贴原始 CSV 数据。"
          : "导入内容解析失败。",
    }
  }
}

function sourceLabel(source: BatchParseResult["source"]) {
  const map: Record<BatchParseResult["source"], string> = {
    empty: "等待输入",
    json: "JSON任务",
    jsonl: "JSON Lines任务",
    task_table: "任务表格",
    raw_dataset: "原始数据集",
    invalid: "格式异常",
  }
  return map[source]
}

function Tasks() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<WorkflowTaskCreate>(emptyForm)
  const [tagText, setTagText] = useState("")
  const [batchText, setBatchText] = useState("")
  const [runBatchAfterCreate, setRunBatchAfterCreate] = useState(true)

  const batchParse = useMemo(() => parseBatchTasks(batchText), [batchText])

  const tasksQuery = useQuery({
    queryKey: ["aetherflow", "tasks"],
    queryFn: AetherFlowApi.readTasks,
  })

  const createMutation = useMutation({
    mutationFn: AetherFlowApi.createTask,
    onSuccess: () => {
      setForm(emptyForm)
      setTagText("")
      toast.success("任务已创建")
      queryClient.invalidateQueries({ queryKey: ["aetherflow"] })
    },
    onError: (error) => toast.error(error.message),
  })

  const batchMutation = useMutation({
    mutationFn: async ({ tasks, runAfterCreate }: BatchMutationInput) => {
      const created = []

      for (const task of tasks) {
        const createdTask = await AetherFlowApi.createTask(task)
        created.push(createdTask)

        if (runAfterCreate) {
          await AetherFlowApi.runTaskAgent(createdTask.id)
        }
      }

      return {
        createdCount: created.length,
        runCount: runAfterCreate ? created.length : 0,
      }
    },
    onSuccess: ({ createdCount, runCount }) => {
      toast.success(
        runCount
          ? `已创建 ${createdCount} 条任务，并运行 ${runCount} 个 Runtime`
          : `已创建 ${createdCount} 条任务`,
      )
      queryClient.invalidateQueries({ queryKey: ["aetherflow"] })
    },
    onError: (error) => toast.error(error.message),
  })

  const runMutation = useMutation({
    mutationFn: (taskId: string) => AetherFlowApi.runTaskAgent(taskId),
    onSuccess: () => {
      toast.success("Runtime 执行完成")
      queryClient.invalidateQueries({ queryKey: ["aetherflow"] })
    },
    onError: (error) => toast.error(error.message),
  })

  const tasks = tasksQuery.data?.data ?? []

  const submitTask = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    createMutation.mutate({
      ...form,
      context: form.context || null,
      expected_output: form.expected_output || null,
      owner_team: form.owner_team || null,
      tags: tagText
        .split(/[,，;；|]/)
        .map((tag) => tag.trim())
        .filter(Boolean),
    })
  }

  const submitBatch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (batchParse.error) {
      toast.error(batchParse.error)
      return
    }

    if (!batchParse.tasks.length) {
      toast.error("请先粘贴或上传至少一条任务/数据。")
      return
    }

    batchMutation.mutate({
      tasks: batchParse.tasks,
      runAfterCreate: runBatchAfterCreate,
    })
  }

  const handleBatchFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = () => {
      setBatchText(String(reader.result ?? ""))
      toast.success(`已读取文件：${file.name}`)
    }
    reader.onerror = () => toast.error("文件读取失败，请确认文件是文本格式。")
    reader.readAsText(file, "UTF-8")
    event.target.value = ""
  }

  return (
    <div className="page-shell">
      <div>
        <div className="page-kicker">我的工作 · 任务</div>
        <h1 className="page-title text-3xl md:text-4xl">我的任务</h1>
        <p className="mt-2 max-w-2xl text-base leading-7 text-muted-foreground">
          查看已保存的工作、继续运行任务；需要批量处理或精确控制时，再使用右侧的高级选项。
        </p>
      </div>

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="order-2 flex flex-col gap-5 xl:order-2">
          <Card className="h-fit">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Plus className="size-5" />
                高级创建任务
              </CardTitle>
              <CardDescription>
                适合需要明确指定处理范围、输出要求和确认方式的工作。
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form className="flex flex-col gap-4" onSubmit={submitTask}>
                <div className="grid gap-2">
                  <Label htmlFor="title">标题</Label>
                  <Input
                    id="title"
                    value={form.title}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        title: event.target.value,
                      }))
                    }
                    required
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="objective">任务目标</Label>
                  <textarea
                    id="objective"
                    className="min-h-28 rounded-lg border bg-card px-3 py-2 text-sm outline-none transition focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/30"
                    value={form.objective}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        objective: event.target.value,
                      }))
                    }
                    required
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="context">上下文 / 数据</Label>
                  <textarea
                    id="context"
                    className="min-h-24 rounded-lg border bg-card px-3 py-2 text-sm outline-none transition focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/30"
                    value={form.context ?? ""}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        context: event.target.value,
                      }))
                    }
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="expected">预期输出</Label>
                  <Input
                    id="expected"
                    value={form.expected_output ?? ""}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        expected_output: event.target.value,
                      }))
                    }
                  />
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="grid gap-2">
                    <Label>场景</Label>
                    <Select
                      value={form.scenario_hint ?? "general"}
                      onValueChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          scenario_hint: value,
                        }))
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {scenarioOptions.map((scenario) => (
                          <SelectItem key={scenario.value} value={scenario.value}>
                            {scenario.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label>优先级</Label>
                    <Select
                      value={form.priority ?? "medium"}
                      onValueChange={(value) =>
                        setForm((current) => ({ ...current, priority: value }))
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {priorityOptions.map((priority) => (
                          <SelectItem key={priority.value} value={priority.value}>
                            {priority.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label>风险</Label>
                    <Select
                      value={form.risk_level ?? "medium"}
                      onValueChange={(value) =>
                        setForm((current) => ({ ...current, risk_level: value }))
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {riskOptions.map((risk) => (
                          <SelectItem key={risk.value} value={risk.value}>
                            {risk.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="owner_team">负责团队</Label>
                  <Input
                    id="owner_team"
                    value={form.owner_team ?? ""}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        owner_team: event.target.value,
                      }))
                    }
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="tags">标签</Label>
                  <Input
                    id="tags"
                    value={tagText}
                    onChange={(event) => setTagText(event.target.value)}
                    placeholder="流程, SLA, 数据分析"
                  />
                </div>
                <label className="flex items-center gap-3 rounded-lg border bg-background/60 p-3 text-sm font-semibold">
                  <Checkbox
                    checked={Boolean(form.requires_approval)}
                    onCheckedChange={(checked) =>
                      setForm((current) => ({
                        ...current,
                        requires_approval: Boolean(checked),
                      }))
                    }
                  />
                  需要审批关卡
                </label>
                <Button type="submit" disabled={createMutation.isPending}>
                  <CheckSquare />
                  保存任务
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="h-fit">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <ListPlus className="size-5" />
                批量任务处理
              </CardTitle>
              <CardDescription>
                适合运营或工程人员一次处理多条结构化任务；日常员工无需使用批量导入。
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form className="flex flex-col gap-4" onSubmit={submitBatch}>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setBatchText(taskTableExample)}
                  >
                    <Wand2 />
                    加载任务表示例
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setBatchText(rawCsvExample)}
                  >
                    <Wand2 />
                    加载原始数据示例
                  </Button>
                  <Badge variant="secondary">
                    {sourceLabel(batchParse.source)} · {batchParse.tasks.length} 条
                  </Badge>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="batch_file">上传数据文件</Label>
                  <Input
                    id="batch_file"
                    type="file"
                    accept=".json,.jsonl,.csv,.tsv,.txt,text/csv,application/json"
                    onChange={handleBatchFile}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="batch_tasks">导入内容</Label>
                  <textarea
                    id="batch_tasks"
                    className="min-h-72 rounded-lg border bg-card px-3 py-2 font-mono text-xs outline-none transition focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/30"
                    value={batchText}
                    onChange={(event) => setBatchText(event.target.value)}
                    placeholder="可以粘贴任务JSON、任务表CSV，或直接粘贴原始CSV数据。"
                  />
                </div>
                <div
                  className={
                    batchParse.error
                      ? "rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
                      : "rounded-lg border bg-background/60 p-3 text-sm text-muted-foreground"
                  }
                >
                  {batchParse.error
                    ? batchParse.error
                    : batchParse.tasks.length
                      ? `已识别为${sourceLabel(batchParse.source)}。创建后每条任务仍会进入完整 Runtime 主流程。`
                      : "支持中英文列名：title/标题、objective/目标、context/数据、scenario/场景、risk/风险等。"}
                </div>
                <label className="flex items-center gap-3 rounded-lg border bg-background/60 p-3 text-sm font-semibold">
                  <Checkbox
                    checked={runBatchAfterCreate}
                    onCheckedChange={(checked) =>
                      setRunBatchAfterCreate(Boolean(checked))
                    }
                  />
                  创建后立即开始处理
                </label>
                <Button
                  type="submit"
                  disabled={
                    batchMutation.isPending ||
                    Boolean(batchParse.error) ||
                    batchParse.tasks.length === 0
                  }
                >
                  <Play />
                  {batchMutation.isPending ? "批量处理中" : "创建批量任务"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        <div className="order-1 flex min-w-0 flex-col gap-5 xl:order-1">
          {tasksQuery.isLoading ? (
            <div className="rounded-lg border p-6 text-sm text-muted-foreground">
              正在加载任务
            </div>
          ) : tasks.length === 0 ? (
            <div className="rounded-lg border p-6 text-sm text-muted-foreground">
              暂无任务
            </div>
          ) : (
            <div className="grid gap-4">
              {tasks.map((task) => (
                <Card key={task.id}>
                  <CardHeader className="gap-3 md:grid-cols-[1fr_auto]">
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge
                          variant="outline"
                          className={statusClass(task.status)}
                        >
                          {statusLabel(task.status)}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={priorityClass(task.priority)}
                        >
                          {priorityLabel(task.priority)}优先级
                        </Badge>
                        <Badge
                          variant="outline"
                          className={riskClass(task.risk_level)}
                        >
                          {riskLabel(task.risk_level)}
                        </Badge>
                        {task.requires_approval ? (
                          <Badge
                            variant="outline"
                            className={statusClass("needs_approval")}
                          >
                            <ShieldAlert className="size-3" /> 需审批
                          </Badge>
                        ) : null}
                      </div>
                      <CardTitle className="text-xl leading-snug">
                        {task.title}
                      </CardTitle>
                      <CardDescription className="line-clamp-2">
                        {task.objective}
                      </CardDescription>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => runMutation.mutate(task.id)}
                      disabled={runMutation.isPending}
                    >
                      <Play />
                      开始处理
                    </Button>
                  </CardHeader>
                  <CardContent className="grid gap-4 md:grid-cols-[240px_1fr]">
                    <div className="grid gap-2 text-sm">
                      <div>
                        <span className="text-muted-foreground">场景</span>
                        <div className="font-medium">
                          {scenarioLabel(task.scenario_hint)}
                        </div>
                      </div>
                      <div>
                        <span className="text-muted-foreground">负责团队</span>
                        <div className="font-medium">
                          {task.owner_team || "未分配"}
                        </div>
                      </div>
                      <div>
                        <span className="text-muted-foreground">标签</span>
                        <div className="flex flex-wrap gap-1 pt-1">
                          {task.tags.length
                            ? task.tags.map((tag) => (
                                <Badge key={tag} variant="secondary">
                                  {tag}
                                </Badge>
                              ))
                            : "无"}
                        </div>
                      </div>
                    </div>
                    <div className="rounded-lg border bg-background/70 p-4 text-sm leading-6">
                      <div className="mb-2 flex items-center gap-2 font-medium">
                        <Bot className="size-4" />
                        处理摘要
                      </div>
                      <p className="text-muted-foreground">
                        {task.final_summary || "该任务还没有运行记录。"}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}



