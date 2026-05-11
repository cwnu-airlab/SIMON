import json
import logging
from typing import Annotated, TypedDict, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.config import settings
from app.models.chat import ChatRequest
from app.services import image_store
from app.services.auth import get_current_user
from app.services.database import (
    add_message,
    create_conversation,
    get_conversation,
    get_messages,
    list_conversation_attachments,
    list_image_attachments_by_message,
    update_attachment_message_id,
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


def _format_attachments_block(attachments: list[dict[str, object]]) -> str:
    """Render conversation-scoped attachments as a single system block.

    Caps total markdown bytes at ``settings.pdf_max_markdown_chars`` and appends
    a ``[truncated, capped at <N> chars]`` marker on overflow so the model
    knows context was clipped.
    """
    if not attachments:
        return ""

    cap = settings.pdf_max_markdown_chars
    lines: list[str] = [
        "The user has attached the following documents to this conversation.",
        "Use them as authoritative context when answering.",
        "",
    ]
    used = 0
    truncated = False
    for att in attachments:
        filename = str(att.get("filename", "attachment.pdf"))
        pages = att.get("pages")
        page_label = f" ({pages} pages)" if isinstance(pages, int) else ""
        header = f"=== {filename}{page_label} ==="
        footer = f"=== end of {filename} ==="
        body = str(att.get("markdown_content", ""))

        # Reserve at least the header + footer + 2 newlines worth of room.
        overhead = len(header) + len(footer) + 4
        remaining = cap - used - overhead if cap > 0 else len(body)
        if cap > 0 and remaining <= 0:
            truncated = True
            break

        if cap > 0 and len(body) > remaining:
            body = body[:remaining]
            truncated = True
            lines.extend([header, body, footer, ""])
            used += len(body) + overhead
            break

        lines.extend([header, body, footer, ""])
        used += len(body) + overhead

    if truncated:
        lines.append(f"[truncated, capped at {cap} chars]")

    return "\n".join(lines)


def _user_content_with_images(
    text: str,
    image_attachments: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Build an OpenAI-compatible content array for a multimodal user turn."""
    blocks: list[dict[str, object]] = [{"type": "text", "text": text}]
    for att in image_attachments:
        file_path = att.get("file_path")
        if not isinstance(file_path, str) or not file_path:
            continue
        try:
            data_url = image_store.load_image_b64(file_path)
        except OSError:
            # Skip attachments whose file disappeared from disk; the
            # conversation continues without that image rather than 500-ing.
            continue
        blocks.append(
            {
                "type": "image_url",
                "image_url": {"url": data_url},
            }
        )
    return blocks


def _build_llm_messages(
    system_prompt: str,
    attachments: list[dict[str, object]],
    history: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Assemble the final messages payload for vLLM.

    - ``system_prompt`` (if any) is the first system message.
    - PDF attachments collapse into one extra system block (handled by
      ``_format_attachments_block``).
    - History messages without ``image_attachments`` keep ``content`` as a
      string (byte-identical to pre-VLM behavior — backwards compatible).
    - History messages WITH ``image_attachments`` produce a content array of
      ``{type:"text"}`` + one ``{type:"image_url"}`` block per attached image.
    """
    pdf_attachments = [
        a for a in attachments if (a.get("attachment_type") or "pdf") == "pdf"
    ]

    # Qwen3 vLLM rejects multiple `system` messages with "System message must be
    # at the beginning." — merge user-defined system_prompt and the PDF
    # attachments block into a single leading system message.
    sys_chunks: list[str] = []
    if system_prompt:
        sys_chunks.append(system_prompt)
    if pdf_attachments:
        block = _format_attachments_block(pdf_attachments)
        if block:
            sys_chunks.append(block)

    messages: list[dict[str, object]] = []
    if sys_chunks:
        messages.append({"role": "system", "content": "\n\n".join(sys_chunks)})

    for msg in history:
        role = str(msg["role"])
        text = str(msg.get("content", ""))
        image_attachments = msg.get("image_attachments")
        if (
            role == "user"
            and isinstance(image_attachments, list)
            and image_attachments
        ):
            messages.append(
                {
                    "role": role,
                    "content": _user_content_with_images(
                        text,
                        cast(list[dict[str, object]], image_attachments),
                    ),
                }
            )
        else:
            messages.append({"role": role, "content": text})

    # Sanitize for Qwen3's strict user/assistant alternation: drop empty-content
    # assistant rows left behind by aborted streams that produced no tokens, and
    # collapse any consecutive same-role runs by keeping the most recent. Without
    # this, a fast abort leaves trailing user → next send is user→user → vLLM 400.
    sanitized: list[dict[str, object]] = []
    for msg in messages:
        role = msg["role"]
        if role == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str) and not content.strip():
                continue
        if (
            sanitized
            and sanitized[-1]["role"] == role
            and role in ("user", "assistant")
        ):
            sanitized[-1] = msg
        else:
            sanitized.append(msg)

    return sanitized


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
    user_message = await add_message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="user",
        content=body.message,
    )

    # Bind any pending image attachments to this user message so they show up
    # in history reconstruction below.
    attachment_ids = body.attachment_ids or []
    if attachment_ids:
        _ = await update_attachment_message_id(
            user_id,
            attachment_ids,
            cast(int, user_message["id"]),
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
    images_by_msg = await list_image_attachments_by_message(user_id, conversation_id)
    history: list[dict[str, object]] = []
    for raw in history_rows:
        msg = dict(raw)
        msg_id = msg.get("id")
        if isinstance(msg_id, int) and msg_id in images_by_msg:
            msg["image_attachments"] = images_by_msg[msg_id]
        history.append(msg)

    attachment_rows = await list_conversation_attachments(user_id, conversation_id)
    attachments = cast(list[dict[str, object]], attachment_rows)
    llm_messages = _build_llm_messages(
        system_prompt=latest_conversation.get("system_prompt") or "",
        attachments=attachments,
        history=history,
    )
    model_params = _parse_model_params(latest_conversation.get("model_params"))

    llm_service = LLMService()

    async def event_stream():
        start_payload = json.dumps({"conversation_id": conversation_id, "type": "start"})
        yield f"data: {start_payload}\n\n".encode()

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        saw_reasoning = False

        try:
            async for line in llm_service.stream_chat_completion(
                messages=llm_messages,
                model_params=model_params,
            ):
                if await request.is_disconnected():
                    logger.info("Client disconnected for conversation %s", conversation_id)
                    break
                reasoning_delta, content_delta, is_done = _extract_stream_deltas(line)
                if reasoning_delta:
                    saw_reasoning = True
                    reasoning_parts.append(reasoning_delta)
                if content_delta:
                    content_parts.append(content_delta)
                yield line
                if is_done:
                    break
        except Exception as exc:
            logger.error(
                "Streaming failed for conversation %s: %s",
                conversation_id, exc, exc_info=True,
            )
            error_payload = json.dumps({"error": "Failed to stream completion"})
            yield f"event: error\ndata: {error_payload}\n\n".encode()
        finally:
            assistant_content = "".join(content_parts)
            assistant_reasoning = "".join(reasoning_parts)
            if saw_reasoning and assistant_content.startswith("\n\n"):
                assistant_content = assistant_content[2:]
            if assistant_content or assistant_reasoning:
                try:
                    _ = await add_message(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        role="assistant",
                        content=assistant_content,
                        reasoning=assistant_reasoning or None,
                    )
                except Exception:
                    logger.exception(
                        "Failed to persist partial assistant for conversation %s",
                        conversation_id,
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
