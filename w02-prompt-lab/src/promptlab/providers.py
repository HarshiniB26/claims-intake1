from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, cast

import httpx
from pydantic import ValidationError

from promptlab.config import ModelConfig, Settings
from promptlab.schemas import StrictModel

AttemptKind = Literal["primary", "transport_retry", "repair", "repair_retry"]
AttemptStatus = Literal["success", "schema_invalid", "transport_error"]


@dataclass(frozen=True)
class AttemptData:
    attempt: int
    kind: AttemptKind
    status: AttemptStatus
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: Decimal
    error: str | None = None


@dataclass(frozen=True)
class CompletionResult:
    output: StrictModel
    attempts: list[AttemptData]
    repairs: int


class CompletionFailed(RuntimeError):
    def __init__(self, message: str, attempts: list[AttemptData], repairs: int) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.repairs = repairs


class OllamaProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.Client(timeout=httpx.Timeout(180.0))

    def close(self) -> None:
        self.client.close()

    def complete(
        self,
        *,
        model: ModelConfig,
        prompt: str,
        output_schema: type[StrictModel],
    ) -> CompletionResult:
        attempts: list[AttemptData] = []
        prior_invalid = ""

        for repair_number in range(self.settings.max_schema_repairs + 1):
            is_repair = repair_number > 0
            active_prompt = prompt
            if is_repair:
                active_prompt = (
                    f"{prompt}\n\nYour prior response did not validate. Return a corrected "
                    "JSON object "
                    f"only. Validation feedback: {prior_invalid[:1200]}"
                )

            schema_invalid = False
            for transport_number in range(self.settings.max_retries + 1):
                kind: AttemptKind
                if is_repair:
                    kind = "repair" if transport_number == 0 else "repair_retry"
                else:
                    kind = "primary" if transport_number == 0 else "transport_retry"

                started = time.perf_counter()
                try:
                    response = self.client.post(
                        f"{self.settings.ollama_base_url}/api/chat",
                        json={
                            "model": model.model_id,
                            "messages": [{"role": "user", "content": active_prompt}],
                            "stream": False,
                            "format": output_schema.model_json_schema(),
                            "options": {"temperature": self.settings.temperature},
                        },
                    )
                    response.raise_for_status()
                    payload = cast(dict[str, Any], response.json())
                    message = cast(dict[str, Any], payload["message"])
                    content = cast(str, message["content"])
                    prompt_tokens = int(payload.get("prompt_eval_count", 0))
                    completion_tokens = int(payload.get("eval_count", 0))
                    latency_ms = (time.perf_counter() - started) * 1000
                    cost = model.cost(prompt_tokens, completion_tokens)

                    try:
                        validated = output_schema.model_validate_json(content)
                    except ValidationError as exc:
                        prior_invalid = str(exc)
                        attempts.append(
                            AttemptData(
                                attempt=len(attempts) + 1,
                                kind=kind,
                                status="schema_invalid",
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                latency_ms=latency_ms,
                                cost_usd=cost,
                                error=prior_invalid[:2000],
                            )
                        )
                        schema_invalid = True
                        break

                    attempts.append(
                        AttemptData(
                            attempt=len(attempts) + 1,
                            kind=kind,
                            status="success",
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            latency_ms=latency_ms,
                            cost_usd=cost,
                        )
                    )
                    return CompletionResult(
                        output=validated,
                        attempts=attempts,
                        repairs=repair_number,
                    )
                except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                    latency_ms = (time.perf_counter() - started) * 1000
                    attempts.append(
                        AttemptData(
                            attempt=len(attempts) + 1,
                            kind=kind,
                            status="transport_error",
                            prompt_tokens=0,
                            completion_tokens=0,
                            latency_ms=latency_ms,
                            cost_usd=Decimal("0"),
                            error=str(exc)[:2000],
                        )
                    )
                    if transport_number < self.settings.max_retries:
                        time.sleep(0.25 * (2**transport_number))

            if not schema_invalid:
                raise CompletionFailed(
                    "Ollama request failed after bounded transport retries",
                    attempts,
                    repair_number,
                )

        raise CompletionFailed(
            "Model output failed schema validation after bounded repair",
            attempts,
            self.settings.max_schema_repairs,
        )
