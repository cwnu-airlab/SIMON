import json
import logging
from collections.abc import AsyncGenerator
from typing import cast

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

Message = dict[str, str]
ModelParams = dict[str, float | int | bool]


class LLMServiceError(RuntimeError):
    pass


class LLMService:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client: httpx.AsyncClient | None = client

    async def list_models(self) -> dict[str, object]:
        response = await self._request("GET", f"{settings.vllm_base_url}/v1/models")
        payload = cast(object, response.json())
        if not isinstance(payload, dict):
            raise LLMServiceError("Unexpected models response from vLLM")
        return cast(dict[str, object], payload)

    async def create_chat_completion(self, payload: dict[str, object]) -> dict[str, object]:
        response = await self._request(
            "POST",
            f"{settings.vllm_base_url}/v1/chat/completions",
            json=payload,
            timeout=httpx.Timeout(120.0),
        )
        body = cast(object, response.json())
        if not isinstance(body, dict):
            raise LLMServiceError("Unexpected chat completion response from vLLM")
        return cast(dict[str, object], body)

    async def stream_chat_completion_proxy(
        self,
        payload: dict[str, object],
    ) -> AsyncGenerator[bytes]:
        stream_timeout = httpx.Timeout(120.0)
        url = f"{settings.vllm_base_url}/v1/chat/completions"

        try:
            if self._client is not None:
                async with self._client.stream(
                    "POST",
                    url,
                    json=payload,
                    timeout=stream_timeout,
                ) as response:
                    async for line in self._stream_response_lines(response):
                        yield line
                return

            async with httpx.AsyncClient(timeout=stream_timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    async for line in self._stream_response_lines(response):
                        yield line
        except httpx.ConnectError as exc:
            logger.error("vLLM error: %s", exc, exc_info=True)
            yield self._error_event(f"vLLM unreachable at {settings.vllm_base_url}")
        except httpx.TimeoutException as exc:
            logger.error("vLLM error: %s", exc, exc_info=True)
            yield self._error_event("vLLM request timed out after 120 seconds")
        except LLMServiceError as exc:
            logger.error("vLLM error: %s", exc, exc_info=True)
            yield self._error_event(str(exc))
        except httpx.HTTPError as exc:
            logger.error("vLLM error: %s", exc, exc_info=True)
            yield self._error_event(f"vLLM request failed: {exc}")

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, object] | None = None,
        timeout: httpx.Timeout | float | None = None,
    ) -> httpx.Response:
        try:
            if self._client is not None:
                response = await self._client.request(method, url, json=json, timeout=timeout)
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(method, url, json=json)

            _ = response.raise_for_status()
            return response
        except httpx.ConnectError as exc:
            raise LLMServiceError(f"vLLM unreachable at {settings.vllm_base_url}") from exc
        except httpx.TimeoutException as exc:
            raise LLMServiceError("vLLM request timed out after 120 seconds") from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() or str(exc)
            raise LLMServiceError(detail) from exc
        except httpx.HTTPError as exc:
            raise LLMServiceError(f"vLLM request failed: {exc}") from exc

    async def check_health(self) -> bool:
        try:
            if self._client is not None:
                response = await self._client.get(
                    f"{settings.vllm_base_url}/v1/models",
                    timeout=5.0,
                )
                return response.status_code == 200

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.vllm_base_url}/v1/models")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def stream_chat_completion(
        self,
        messages: list[Message],
        model_params: ModelParams,
    ) -> AsyncGenerator[bytes]:
        payload = {
            "model": settings.vllm_model,
            "messages": messages,
            "stream": True,
            "temperature": model_params.get("temperature", 0.7),
            "max_tokens": model_params.get("max_tokens", 4096),
            "top_p": model_params.get("top_p", 0.9),
            "chat_template_kwargs": {"enable_thinking": model_params.get("enable_thinking", True)},
        }

        stream_timeout = httpx.Timeout(120.0)
        url = f"{settings.vllm_base_url}/v1/chat/completions"

        try:
            if self._client is not None:
                async with self._client.stream(
                    "POST",
                    url,
                    json=payload,
                    timeout=stream_timeout,
                ) as response:
                    async for line in self._stream_response_lines(response):
                        yield line
                return

            async with httpx.AsyncClient(timeout=stream_timeout) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                ) as response:
                    async for line in self._stream_response_lines(response):
                        yield line
        except httpx.ConnectError as e:
            logger.error(f"vLLM error: {e}", exc_info=True)
            message = f"vLLM unreachable at {settings.vllm_base_url}"
            yield self._error_event(message)
        except httpx.TimeoutException as e:
            logger.error(f"vLLM error: {e}", exc_info=True)
            yield self._error_event("vLLM request timed out after 120 seconds")
        except LLMServiceError as e:
            logger.error(f"vLLM error: {e}", exc_info=True)
            yield self._error_event(str(e))
        except httpx.HTTPError as e:
            logger.error(f"vLLM error: {e}", exc_info=True)
            yield self._error_event(f"vLLM request failed: {e}")

    @staticmethod
    async def _stream_response_lines(
        response: httpx.Response,
    ) -> AsyncGenerator[bytes]:
        _ = response.raise_for_status()

        raw_content_type = cast(str, response.headers.get("content-type", ""))
        content_type = raw_content_type
        if "text/event-stream" not in content_type:
            raise LLMServiceError(f"Unexpected content type from vLLM: {content_type}")

        buffer = b""
        async for chunk in response.aiter_raw():
            if not chunk:
                continue

            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                yield line + b"\n"

        if buffer:
            yield buffer

    @staticmethod
    def _error_event(message: str) -> bytes:
        payload = json.dumps({"type": "error", "message": message})
        return f"data: {payload}\n\n".encode()
