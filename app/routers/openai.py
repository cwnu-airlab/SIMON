from typing import Annotated, cast

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import settings
from app.services.auth import get_current_user
from app.services.llm import LLMService, LLMServiceError

router = APIRouter(prefix="/v1", tags=["openai-compatible"])
CurrentUser = Annotated[dict[str, object], Depends(get_current_user)]


def _normalize_payload(payload: dict[str, object]) -> dict[str, object]:
    normalized = dict(payload)
    if "model" not in normalized:
        normalized["model"] = settings.vllm_model
    return normalized


def _is_stream_request(payload: dict[str, object]) -> bool:
    stream = payload.get("stream", False)
    return isinstance(stream, bool) and stream


def _shared_http_client(request: Request) -> httpx.AsyncClient | None:
    app = cast(object, request.scope.get("app"))
    if not isinstance(app, FastAPI):
        return None

    client = getattr(app.state, "http_client", None)
    if isinstance(client, httpx.AsyncClient):
        return client
    return None


@router.get("/models")
async def list_models(request: Request, current_user: CurrentUser) -> JSONResponse:
    _ = current_user
    llm_service = LLMService(client=_shared_http_client(request))

    try:
        payload = await llm_service.list_models()
    except LLMServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return JSONResponse(payload)


@router.post("/chat/completions", response_model=None)
async def create_chat_completion(
    body: dict[str, object],
    request: Request,
    current_user: CurrentUser,
) -> JSONResponse | StreamingResponse:
    _ = current_user
    if "messages" not in body:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="messages is required",
        )

    payload = _normalize_payload(body)
    llm_service = LLMService(client=_shared_http_client(request))

    if _is_stream_request(payload):
        async def event_stream():
            async for line in llm_service.stream_chat_completion_proxy(payload):
                if await request.is_disconnected():
                    return
                yield line

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        response_payload = await llm_service.create_chat_completion(payload)
    except LLMServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return JSONResponse(response_payload)
