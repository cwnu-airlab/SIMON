import json
import logging
from typing import Annotated, TypedDict, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.models.chat import ChatRequest
from app.services.auth import get_current_user
from app.services.database import (
    add_message,
    create_conversation,
    get_conversation,
    get_messages,
    update_conversation,
)
from app.services.llm import LLMService

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)
CurrentUser = Annotated[dict[str, object], Depends(get_current_user)]


class ConversationRow(TypedDict):
    id: str
    title: str
    system_prompt: str | None
    model_params: str | None


class MessageRow(TypedDict):
    role: str
    content: str


def _conversation_title_from_message(message: str) -> str:
    title = message.strip()[:50]
    return title or "New Chat"


def _parse_model_params(raw: str | None) -> dict[str, float | int | bool]:
    if raw is None:
        return {}
    parsed_obj = cast(object, json.loads(raw))
    if isinstance(parsed_obj, dict):
        parsed = cast(dict[str, object], parsed_obj)
        model_params: dict[str, float | int | bool] = {}
        for key in ("temperature", "max_tokens", "top_p", "enable_thinking"):
            value = parsed.get(key)
            if isinstance(value, (bool, int, float)):
                model_params[key] = value
        return model_params
    return {}


def _build_llm_messages(
    system_prompt: str,
    history: list[MessageRow],
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    for msg in history:
        role = msg["role"]
        content = msg["content"]
        messages.append({"role": role, "content": content})

    return messages


def _extract_stream_deltas(line: bytes) -> tuple[str, str, bool]:
    stripped = line.strip()
    if not stripped.startswith(b"data:"):
        return "", "", False

    payload = stripped[5:].strip()
    if payload == b"[DONE]":
        return "", "", True

    try:
        chunk_obj = cast(object, json.loads(payload))
    except json.JSONDecodeError:
        return "", "", False

    if not isinstance(chunk_obj, dict):
        return "", "", False
    chunk = cast(dict[str, object], chunk_obj)

    choices_obj = chunk.get("choices")
    if not isinstance(choices_obj, list) or not choices_obj:
        return "", "", False
    choices = cast(list[object], choices_obj)

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return "", "", False
    first_choice_dict = cast(dict[str, object], first_choice)

    delta = first_choice_dict.get("delta")
    if not isinstance(delta, dict):
        return "", "", False
    delta_dict = cast(dict[str, object], delta)

    reasoning = delta_dict.get("reasoning", "")
    if not isinstance(reasoning, str):
        reasoning = ""
    if not reasoning:
        alt_reasoning = delta_dict.get("reasoning_content", "")
        if isinstance(alt_reasoning, str):
            reasoning = alt_reasoning

    content = delta_dict.get("content", "")
    if not isinstance(content, str):
        content = ""

    return reasoning, content, False


@router.post("/completions")
async def stream_chat_completion(
    body: ChatRequest,
    request: Request,
    current_user: CurrentUser,
) -> StreamingResponse:
    conversation: ConversationRow | None = None
    user_id = str(current_user["id"])
    if body.conversation_id is not None:
        conversation_row = await get_conversation(user_id, body.conversation_id)
        conversation = cast(ConversationRow | None, conversation_row)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {body.conversation_id} not found",
            )
    else:
        created = await create_conversation(user_id)
        conversation = cast(ConversationRow, cast(object, created))
        title = _conversation_title_from_message(body.message)
        updated = await update_conversation(user_id, conversation["id"], title=title)
        if updated is not None:
            conversation = cast(ConversationRow, cast(object, updated))

    conversation_id = conversation["id"]
    _ = await add_message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="user",
        content=body.message,
    )

    # Auto-title if still using default (handles sidebar-created conversations)
    if conversation["title"] == "New Chat":
        title = _conversation_title_from_message(body.message)
        updated = await update_conversation(user_id, conversation_id, title=title)
        if updated is not None:
            conversation = cast(ConversationRow, cast(object, updated))

    latest_conversation_row = await get_conversation(user_id, conversation_id)
    latest_conversation = cast(ConversationRow | None, latest_conversation_row)
    if latest_conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    history_rows = await get_messages(user_id, conversation_id)
    history = cast(list[MessageRow], history_rows)
    llm_messages = _build_llm_messages(
        system_prompt=latest_conversation.get("system_prompt") or "",
        history=history,
    )
    model_params = _parse_model_params(latest_conversation.get("model_params"))

    llm_service = LLMService()

    async def event_stream():
        start_payload = json.dumps(
            {"conversation_id": conversation_id, "type": "start"},
        )
        yield f"data: {start_payload}\n\n".encode()

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        saw_reasoning = False
        done_received = False

        try:
            async for line in llm_service.stream_chat_completion(
                messages=llm_messages,
                model_params=model_params,
            ):
                if await request.is_disconnected():
                    logger.info("Client disconnected for conversation %s", conversation_id)
                    return

                reasoning_delta, content_delta, is_done = _extract_stream_deltas(line)
                if reasoning_delta:
                    saw_reasoning = True
                    reasoning_parts.append(reasoning_delta)
                if content_delta:
                    content_parts.append(content_delta)

                yield line

                if is_done:
                    done_received = True
                    break
        except Exception as exc:
            logger.error(
                "Streaming failed for conversation %s: %s",
                conversation_id,
                exc,
                exc_info=True,
            )
            error_payload = json.dumps({"error": "Failed to stream completion"})
            yield f"event: error\ndata: {error_payload}\n\n".encode()
            return

        if not done_received:
            return

        assistant_content = "".join(content_parts)
        assistant_reasoning = "".join(reasoning_parts)
        if saw_reasoning and assistant_content.startswith("\n\n"):
            assistant_content = assistant_content[2:]

        if assistant_content or assistant_reasoning:
            _ = await add_message(
                user_id=user_id,
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_content,
                reasoning=assistant_reasoning or None,
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
