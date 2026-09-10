# AetherFlow Release Notes

## 0.1.0 - GitHub-ready baseline

- Added the employee-facing Agent workbench and task execution flow.
- Split the Runtime into routing, planning, retrieval, tool selection, execution, critique, memory, and evaluation modules.
- Added structured DAG validation, approval gates, dry-run execution, recovery records, and replayable `AgentTraceStep` records.
- Added the real `data_frame_profiler` tool for CSV profiling and anomaly hints.
- Added benchmark tasks, randomized-seed robustness evaluation, failure categories, and Release Gate metrics.
- Added Docker Compose startup, repository screenshots, and a focused GitHub CI workflow.

## Scope

This release is an enterprise Agent Runtime prototype. External writes, code execution, and customer-visible actions remain dry-run by default and require approval. Production integrations such as SSO, object storage, queues, and real connectors are intentionally left behind explicit extension points.
