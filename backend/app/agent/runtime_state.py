from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


class RuntimeStateStore:
    """Best-effort Redis state/event store with a database-backed fallback."""

    def __init__(self, url: str | None = None) -> None:
        self.url = url if url is not None else settings.REDIS_URL
        self.client: Redis[str] | None = None
        self._disabled = False
        if self.url:
            self.client = Redis.from_url(self.url, decode_responses=True, socket_timeout=0.5)

    @property
    def configured(self) -> bool:
        return bool(self.url) and not self._disabled

    def record_event(self, run_id: str, event: dict[str, Any]) -> None:
        if not self.configured or self.client is None:
            return
        try:
            key = f"shuiliu:run:{run_id}:events"
            payload = {"payload": json.dumps(event, ensure_ascii=False, default=str)}
            self.client.xadd(key, payload, maxlen=500, approximate=True)
            self.client.expire(key, settings.REDIS_RUNTIME_EVENT_TTL_SECONDS)
        except RedisError as error:
            self._disable(error)

    def record_state(self, run_id: str, state: str, **metadata: Any) -> None:
        if not self.configured or self.client is None:
            return
        try:
            key = f"shuiliu:run:{run_id}:state"
            fields = {
                "state": state,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                **{key: str(value) for key, value in metadata.items() if value is not None},
            }
            self.client.hset(key, mapping=fields)
            self.client.expire(key, settings.REDIS_RUNTIME_EVENT_TTL_SECONDS)
        except RedisError as error:
            self._disable(error)

    def read_events(self, run_id: str, limit: int = 100) -> list[dict[str, Any]]:
        if not self.configured or self.client is None:
            return []
        try:
            entries = self.client.xrange(f"shuiliu:run:{run_id}:events", count=max(1, min(limit, 500)))
            result: list[dict[str, Any]] = []
            for event_id, fields in entries:
                try:
                    payload = json.loads(fields.get("payload", "{}"))
                except json.JSONDecodeError:
                    payload = {"raw": fields.get("payload", "")}
                result.append({"event_id": event_id, **payload})
            return result
        except RedisError as error:
            self._disable(error)
            return []

    def health(self) -> dict[str, Any]:
        if not self.configured or self.client is None:
            return {"configured": False, "available": False, "backend": "postgres_trace"}
        try:
            self.client.ping()
            return {"configured": True, "available": True, "backend": "redis_stream"}
        except RedisError as error:
            self._disable(error)
            return {"configured": True, "available": False, "backend": "postgres_trace"}

    def _disable(self, error: RedisError) -> None:
        self._disabled = True
        logger.warning("Redis runtime state disabled; PostgreSQL Trace remains authoritative: %s", error)


runtime_state = RuntimeStateStore()
