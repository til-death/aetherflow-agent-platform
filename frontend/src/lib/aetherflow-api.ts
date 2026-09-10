export type WorkflowTask = {
  id: string
  title: string
  objective: string
  context?: string | null
  expected_output?: string | null
  scenario_hint?: string | null
  priority: string
  status: string
  risk_level: string
  requires_approval: boolean
  owner_team?: string | null
  final_summary?: string | null
  tags: string[]
  owner_id: string
  created_at: string
  updated_at: string
}

export type WorkflowTaskCreate = {
  title: string
  objective: string
  context?: string | null
  expected_output?: string | null
  scenario_hint?: string | null
  priority?: string
  status?: string
  risk_level?: string
  requires_approval?: boolean
  owner_team?: string | null
  final_summary?: string | null
  tags?: string[]
}

export type WorkflowTasksResponse = {
  data: WorkflowTask[]
  count: number
}

export type AgentTraceStep = {
  id: string
  run_id: string
  sequence: number
  stage: string
  agent_name: string
  tool_name?: string | null
  status: string
  input_snapshot?: string | null
  output_snapshot?: string | null
  confidence: number
  latency_ms: number
  metadata_json: Record<string, unknown>
  created_at: string
}

export type AgentRun = {
  id: string
  task_id?: string | null
  owner_id: string
  scenario: string
  status: string
  failure_type: string
  recovery_action?: string | null
  confidence: number
  reliability_score: number
  selected_tool?: string | null
  final_answer?: string | null
  run_profile: string
  runtime_version: string
  idempotency_key?: string | null
  approval_status: string
  approval_comment?: string | null
  approved_at?: string | null
  approved_by?: string | null
  risk_level: string
  graph_node_count: number
  cost_units: number
  created_at: string
  completed_at?: string | null
  steps: AgentTraceStep[]
}

export type AgentRunsResponse = {
  data: AgentRun[]
  count: number
}

export type AgentSummary = {
  task_count: number
  active_task_count: number
  approval_queue_count: number
  run_count: number
  success_rate: number
  handled_rate: number
  approval_rate: number
  recovery_rate: number
  average_confidence: number
  average_reliability_score: number
  average_cost_units: number
}

export type OperationsSummary = {
  total_tasks: number
  active_tasks: number
  completed_tasks: number
  failed_tasks: number
  approval_queue: number
  total_runs: number
  successful_runs: number
  recovered_runs: number
  failed_runs: number
  success_rate: number
  average_reliability: number
}

export type OperationsQueueItem = {
  task_id: string
  run_id?: string | null
  title: string
  objective: string
  owner_name: string
  owner_email: string
  owner_team: string
  task_status: string
  run_status: string
  scenario: string
  risk_level: string
  selected_tool?: string | null
  approval_status: string
  reliability_score: number
  created_at: string
  completed_at?: string | null
}

export type OperationsTeamSummary = {
  team: string
  task_count: number
  active_task_count: number
  run_count: number
  approval_queue_count: number
  success_rate: number
  average_reliability: number
}

export type OperationsDashboard = {
  generated_at: string
  summary: OperationsSummary
  teams: OperationsTeamSummary[]
  queue: OperationsQueueItem[]
}

export type ToolDefinition = {
  name: string
  label: string
  scenario: string
  risk_level: string
  avg_latency_ms: number
  success_rate: number
  description: string
}

export type EvaluationMetric = {
  name: string
  single_agent: number
  naive_multi_agent: number
  reliability_harness: number
  unit: string
}

export type EvaluationCaseResult = {
  case_id: string
  user_request: string
  expected_tool: string
  selected_tool: string
  top3_tools: string[]
  top5_tools: string[]
  expected_approval: boolean
  actual_approval: boolean
  expected_scenario: string
  actual_scenario: string
  contract_score: number
  matched_contract_terms: string[]
  missing_contract_terms: string[]
  trace_complete: boolean
  result: "passed" | "failed" | string
  failure_reason?: string | null
}

export type EvaluationFailureAnalysis = {
  case_id: string
  category: string
  reason: string
  recommendation: string
}

export type EvaluationDatasetInfo = {
  dataset_key: string
  task_dataset_name: string
  tool_library_name: string
  evaluation_mode: string
  dynamic_tool_count: number
  has_expected_tool: boolean
  has_tool_library: boolean
}

export type EvaluationExperimentSummary = {
  id: string
  experiment_name: string
  dataset_key: string
  runtime_version: string
  status: string
  case_count: number
  failure_count: number
  release_gate_status: string
  release_gate_label: string
  created_at: string
}

export type EvaluationExperimentsResponse = {
  data: EvaluationExperimentSummary[]
  count: number
}
export type EvaluationGateCheck = {
  name: string
  score: number
  threshold: number
  passed: boolean
  detail: string
}

export type EvaluationReleaseGate = {
  status: "pass" | "review" | "fail" | string
  label: string
  summary: string
}

export type EvaluationScenarioSlice = {
  scenario: string
  case_count: number
  pass_rate: number
  top1_accuracy: number
  approval_accuracy: number
  contract_coverage: number
  failed_cases: string[]
}

export type EvaluationToolCoverage = {
  tool_name: string
  expected_count: number
  selected_count: number
  top1_hits: number
  accuracy: number
  average_rank?: number | null
}

export type EvaluationReport = {
  generated_at: string
  experiment_id: string
  experiment_name: string
  runtime_version: string
  status: string
  sample_size: number
  case_count: number
  failure_count: number
  metrics: EvaluationMetric[]
  release_gate: EvaluationReleaseGate
  gate_checks: EvaluationGateCheck[]
  scenario_slices: EvaluationScenarioSlice[]
  tool_coverage: EvaluationToolCoverage[]
  recommended_actions: string[]
  notes: string[]
  dataset?: EvaluationDatasetInfo | null
  cases: EvaluationCaseResult[]
  failures: EvaluationFailureAnalysis[]
}

export type ScorerRule = {
  id: string
  source: "task" | "run" | "trace_steps" | "selected_tool" | "ranked_tools"
  selector: string
  operator:
    | "exists"
    | "not_exists"
    | "equals"
    | "not_equals"
    | "contains"
    | "not_contains"
    | "gte"
    | "lte"
    | "in"
    | "not_in"
    | "count_gte"
    | "count_lte"
  expected?: string | number | boolean | string[] | null
  weight: number
  reason?: string | null
}

export type ScorerDefinition = {
  id?: string | null
  name: string
  description?: string | null
  level: "common" | "scenario" | "domain"
  applies_to: {
    scenarios: string[]
    risk_levels: string[]
    domain_tags: string[]
  }
  rules: ScorerRule[]
  aggregation: {
    method: "weighted_average"
    pass_threshold: number
  }
}

export type ScorerRuleResult = {
  id: string
  passed: boolean
  score: number
  reason?: string | null
  actual: unknown
  expected: unknown
  weight: number
}

export type ScorerScoreResult = {
  name: string
  level: "common" | "scenario" | "domain"
  score: number
  passed: boolean
  reason: string
  rules: ScorerRuleResult[]
  definition: ScorerDefinition
}

export type ToolDecisionCheck = {
  name: string
  score: number
  passed: boolean
  signal: string
  explanation: string
}

export type RunEvaluationResult = {
  run_id: string
  task_id?: string | null
  scenario: string
  selected_tool?: string | null
  selected_tool_label?: string | null
  selected_tool_risk?: string | null
  score: number
  passed: boolean
  results: ScorerScoreResult[]
  grouped_scores: Record<string, number>
  decision_verdict: string
  decision_summary: string
  decision_checks: ToolDecisionCheck[]
  improvement_actions: string[]
  tool_alternatives: Array<Record<string, unknown>>
  notes: string[]
}
const API_BASE = import.meta.env.VITE_API_URL || ""

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("access_token")
  const headers = new Headers(init.headers)
  headers.set("Accept", "application/json")
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }
  if (token) {
    headers.set("Authorization", "Bearer " + token)
  }

  const response = await fetch(API_BASE + path, { ...init, headers })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || "Request failed with " + response.status)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

export const AetherFlowApi = {
  readTasks: () => request<WorkflowTasksResponse>("/api/v1/tasks/"),
  createTask: (payload: WorkflowTaskCreate) =>
    request<WorkflowTask>("/api/v1/tasks/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  runTaskAgent: (taskId: string, idempotencyKey?: string) =>
    request<AgentRun>("/api/v1/agent/tasks/" + taskId + "/runs", {
      method: "POST",
      headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
    }),
  approveRun: (runId: string, comment?: string) =>
    request<AgentRun>("/api/v1/agent/runs/" + runId + "/approve", {
      method: "POST",
      body: JSON.stringify({ comment: comment ?? null }),
    }),
  readRuns: () => request<AgentRunsResponse>("/api/v1/agent/runs"),
  readSummary: () => request<AgentSummary>("/api/v1/agent/summary"),
  readOperationsDashboard: (params?: { team?: string; status?: string; limit?: number }) => {
    const search = new URLSearchParams()
    if (params?.team) search.set("team", params.team)
    if (params?.status) search.set("status", params.status)
    if (params?.limit) search.set("limit", String(params.limit))
    const suffix = search.toString() ? "?" + search.toString() : ""
    return request<OperationsDashboard>("/api/v1/operations/dashboard" + suffix)
  },
  readTools: () => request<ToolDefinition[]>("/api/v1/agent/tools"),
  readScorers: () => request<ScorerDefinition[]>("/api/v1/agent/scorers"),
  readExperiments: () => request<EvaluationExperimentsResponse>("/api/v1/agent/experiments"),
  readExperiment: (experimentId: string) => request<EvaluationReport>("/api/v1/agent/experiments/" + encodeURIComponent(experimentId)),
  evaluateRun: (runId: string, scorerIds?: string[] | null) =>
    request<RunEvaluationResult>("/api/v1/agent/runs/" + runId + "/evaluate", {
      method: "POST",
      body: JSON.stringify({ scorer_ids: scorerIds ?? null }),
    }),
  previewScorer: (runId: string, definition: ScorerDefinition) =>
    request<ScorerScoreResult>("/api/v1/agent/scorers/preview", {
      method: "POST",
      body: JSON.stringify({ run_id: runId, definition }),
    }),
  runEvaluation: (dataset = "sample") =>
    request<EvaluationReport>("/api/v1/agent/evaluation/run?dataset=" + encodeURIComponent(dataset), {
      method: "POST",
    }),
}









