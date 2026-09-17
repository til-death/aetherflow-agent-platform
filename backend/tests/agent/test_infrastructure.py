from app.agent.mcp_adapter import build_mcp_tool_catalog
from app.agent.runtime_state import RuntimeStateStore


def test_mcp_catalog_exposes_tool_contract_and_risk_annotations() -> None:
    catalog = build_mcp_tool_catalog()

    assert catalog["protocolVersion"] == "2025-06-18"
    assert len(catalog["tools"]) >= 6
    external_api = next(tool for tool in catalog["tools"] if tool["name"] == "http_api_connector")
    assert external_api["inputSchema"]["type"] == "object"
    assert external_api["annotations"]["destructiveHint"] is True
    assert external_api["_aetherflow"]["riskLevel"] == "high"


def test_runtime_state_store_degrades_to_database_trace_without_redis() -> None:
    store = RuntimeStateStore(url=None)

    store.record_state("run-1", "running")
    store.record_event("run-1", {"stage": "planner"})

    assert store.health() == {"configured": False, "available": False, "backend": "postgres_trace"}
    assert store.read_events("run-1") == []
