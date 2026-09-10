from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings

SchemaModel = TypeVar("SchemaModel", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLMDisabledError(LLMError):
    pass


class LLMClient:
    def __init__(self) -> None:
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = str(settings.OPENAI_BASE_URL).rstrip("/")
        self.model = settings.AGENT_MODEL
        self.timeout_seconds = settings.AGENT_LLM_TIMEOUT_SECONDS
        self.max_retries = settings.AGENT_LLM_MAX_RETRIES
        self.store_responses = settings.AGENT_STORE_RESPONSES

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def complete_json(
        self,
        *,
        purpose: str,
        system: str,
        user: str,
        schema_model: type[SchemaModel],
    ) -> SchemaModel:
        if not self.enabled:
            raise LLMDisabledError("OPENAI_API_KEY is not configured")

        errors: list[str] = []
        for attempt in range(self.max_retries + 1):
            try:
                raw_text = self._responses_call(
                    purpose=purpose,
                    system=system,
                    user=user,
                    schema_model=schema_model,
                )
                return schema_model.model_validate_json(raw_text)
            except (httpx.HTTPError, ValidationError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                errors.append(f"attempt={attempt + 1}: {type(exc).__name__}: {exc}")
                if attempt < self.max_retries:
                    repaired = self._try_repair_json(
                        purpose=purpose,
                        schema_model=schema_model,
                        bad_output=locals().get("raw_text", ""),
                        error=str(exc),
                    )
                    if repaired is not None:
                        return repaired

        raise LLMError("; ".join(errors[-3:]))

    def _responses_call(
        self,
        *,
        purpose: str,
        system: str,
        user: str,
        schema_model: type[BaseModel],
    ) -> str:
        schema = schema_model.model_json_schema()
        payload = {
            "model": self.model,
            "store": self.store_responses,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": purpose,
                    "schema": schema,
                    "strict": True,
                }
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/responses", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return self._extract_output_text(data)

    def _try_repair_json(
        self,
        *,
        purpose: str,
        schema_model: type[SchemaModel],
        bad_output: object,
        error: str,
    ) -> SchemaModel | None:
        if not bad_output:
            return None
        repair_system = "Return only corrected JSON matching the supplied schema. Do not add prose."
        repair_user = json.dumps(
            {
                "schema": schema_model.model_json_schema(),
                "bad_output": str(bad_output)[:6000],
                "validation_error": error[:2000],
            },
            ensure_ascii=False,
        )
        try:
            repaired_text = self._responses_call(
                purpose=f"{purpose}_repair",
                system=repair_system,
                user=repair_user,
                schema_model=schema_model,
            )
            return schema_model.model_validate_json(repaired_text)
        except (httpx.HTTPError, ValidationError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def _extract_output_text(self, data: dict[str, object]) -> str:
        direct = data.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct

        output = data.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    text = block.get("text")
                    if isinstance(text, str) and text.strip():
                        return text

        raise LLMError("Responses API returned no output text")
