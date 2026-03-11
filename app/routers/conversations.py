"""Conversation CRUD endpoints."""

import json
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.models.chat import (
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
    ModelParams,
)
from app.services.auth import get_current_user
from app.services.database import (
    create_conversation,
    delete_conversation,
    get_conversation,
    get_messages,
    list_conversations,
    update_conversation,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])
CurrentUser = Annotated[dict[str, object], Depends(get_current_user)]


def _parse_model_params(raw: str | None) -> ModelParams:
    if raw is None:
        return ModelParams()
    parsed_obj = cast(object, json.loads(raw))
    if not isinstance(parsed_obj, dict):
        return ModelParams()

    parsed = cast(dict[str, object], parsed_obj)
    temperature = parsed.get("temperature")
    max_tokens = parsed.get("max_tokens")
    top_p = parsed.get("top_p")
    enable_thinking = parsed.get("enable_thinking")
    temperature_value = (
        float(temperature)
        if isinstance(temperature, (int, float)) and not isinstance(temperature, bool)
        else 0.7
    )
    max_tokens_value = (
        max_tokens if isinstance(max_tokens, int) and not isinstance(max_tokens, bool) else 4096
    )
    top_p_value = (
        float(top_p) if isinstance(top_p, (int, float)) and not isinstance(top_p, bool) else 0.9
    )
    enable_thinking_value = enable_thinking if isinstance(enable_thinking, bool) else True

    return ModelParams(
        temperature=temperature_value,
        max_tokens=max_tokens_value,
        top_p=top_p_value,
        enable_thinking=enable_thinking_value,
    )


def _to_conversation_response(row: dict[str, object]) -> ConversationResponse:
    return ConversationResponse(
        id=str(row["id"]),
        title=str(row["title"]),
        system_prompt=str(row["system_prompt"]),
        model_params=_parse_model_params(cast(str | None, row["model_params"])),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _to_message_response(row: dict[str, object]) -> MessageResponse:
    return MessageResponse(
        id=cast(int, row["id"]),
        conversation_id=str(row["conversation_id"]),
        role=str(row["role"]),
        content=str(row["content"]),
        reasoning=cast(str | None, row.get("reasoning")),
        created_at=str(row["created_at"]),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation_endpoint(
    current_user: CurrentUser,
) -> ConversationResponse:
    """Create a new conversation with default settings."""
    row = await create_conversation(str(current_user["id"]))
    return _to_conversation_response(row)


@router.get("")
async def list_conversations_endpoint(
    current_user: CurrentUser,
) -> list[ConversationResponse]:
    """List all conversations ordered by updated_at DESC."""
    rows = await list_conversations(str(current_user["id"]))
    return [_to_conversation_response(row) for row in rows]


@router.get("/{conversation_id}")
async def get_conversation_endpoint(
    conversation_id: str,
    current_user: CurrentUser,
) -> dict[str, object]:
    """Get a single conversation with its messages."""
    user_id = str(current_user["id"])
    row = await get_conversation(user_id, conversation_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )
    messages = await get_messages(user_id, conversation_id)
    return {
        "conversation": _to_conversation_response(row),
        "messages": [_to_message_response(m) for m in messages],
    }


@router.patch("/{conversation_id}")
async def update_conversation_endpoint(
    conversation_id: str,
    body: ConversationUpdate,
    current_user: CurrentUser,
) -> ConversationResponse:
    """Update conversation title, system_prompt, or model_params."""
    user_id = str(current_user["id"])
    existing = await get_conversation(user_id, conversation_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )
    updated = await update_conversation(
        user_id,
        conversation_id,
        title=body.title,
        system_prompt=body.system_prompt,
        model_params=body.model_params.model_dump() if body.model_params else None,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )
    return _to_conversation_response(updated)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_endpoint(
    conversation_id: str,
    current_user: CurrentUser,
) -> Response:
    """Delete a conversation and all its messages (cascade)."""
    deleted = await delete_conversation(str(current_user["id"]), conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
