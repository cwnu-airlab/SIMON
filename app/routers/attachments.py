"""Attachment upload + listing endpoints, scoped to a conversation.

Handles two attachment types:

- ``application/pdf`` — forwards to the pdf-parser sidecar, stores the
  extracted markdown in ``attachments.markdown_content``. Conversation-scoped
  (re-injected as a system message every turn by ``app/routers/chat.py``).
- ``image/{png,jpeg,webp}`` — Pillow resize / re-encode / sha256 dedup, stored
  on the backend volume. Message-scoped (linked to the user message at send
  time and reconstructed into the LLM messages array as an ``image_url`` block).
"""

from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.config import settings
from app.services import image_store
from app.services.auth import get_current_user
from app.services.database import (
    add_attachment,
    add_image_attachment,
    delete_attachment,
    find_attachment_by_hash,
    get_attachment,
    get_conversation,
    is_file_path_orphan,
    list_conversation_attachments,
)
from app.services.image_store import ImageStoreError
from app.services.pdf_parser import PdfParserError, file_hash, parse_pdf

router = APIRouter(prefix="/api/conversations", tags=["attachments"])
CurrentUser = Annotated[dict[str, object], Depends(get_current_user)]

_PDF_MAX_BYTES = 50 * 1024 * 1024
_IMAGE_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})


def _to_meta(row: dict[str, object]) -> dict[str, object]:
    """Public projection — never returns markdown_content or raw bytes.

    `message_id` is exposed (nullable) so the frontend can resurface orphan
    images (uploaded but not yet sent in a user message) as pending
    thumbnails when the conversation is reloaded after a tab refresh.
    """
    return {
        "id": row["id"],
        "filename": row["filename"],
        "pages": row.get("pages"),
        "created_at": row["created_at"],
        "attachment_type": row.get("attachment_type") or "pdf",
        "mime_type": row.get("mime_type"),
        "width": row.get("width"),
        "height": row.get("height"),
        "message_id": row.get("message_id"),
    }


async def _handle_pdf_upload(
    request: Request,
    user_id: str,
    conversation_id: str,
    file: UploadFile,
) -> dict[str, object]:
    file_bytes = await file.read()
    if len(file_bytes) > _PDF_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds 50MB limit ({len(file_bytes)} bytes)",
        )

    shared_client = getattr(request.app.state, "http_client", None)
    try:
        parsed = await parse_pdf(
            shared_client,
            file_bytes,
            file.filename or "upload.pdf",
            force_ocr=True,
        )
    except PdfParserError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    raw_markdown = parsed.get("markdown")
    raw_pages = parsed.get("pages")
    markdown_content = raw_markdown if isinstance(raw_markdown, str) else ""
    pages = raw_pages if isinstance(raw_pages, int) else None

    row = await add_attachment(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=None,
        filename=file.filename or "upload.pdf",
        file_hash=file_hash(file_bytes),
        pages=pages,
        markdown_content=markdown_content,
    )
    return _to_meta(row)


async def _handle_image_upload(
    user_id: str,
    conversation_id: str,
    file: UploadFile,
) -> dict[str, object]:
    file_bytes = await file.read()
    if len(file_bytes) > settings.image_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Image exceeds "
                f"{settings.image_max_bytes // (1024 * 1024)}MB limit "
                f"({len(file_bytes)} bytes)"
            ),
        )

    try:
        meta = image_store.resize_and_save(file_bytes, Path(settings.images_dir))
    except ImageStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Dedup: if this user already uploaded the same hash, reuse stored file_path.
    existing = await find_attachment_by_hash(user_id, str(meta["file_hash"]), "image")
    file_path = (
        str(existing["file_path"]) if existing is not None and existing.get("file_path")
        else str(meta["file_path"])
    )

    row = await add_image_attachment(
        user_id=user_id,
        conversation_id=conversation_id,
        filename=file.filename or "upload.jpg",
        file_hash=str(meta["file_hash"]),
        mime_type=str(meta["mime_type"]),
        width=int(meta["width"]) if meta.get("width") is not None else 0,
        height=int(meta["height"]) if meta.get("height") is not None else 0,
        byte_size=int(meta["byte_size"]) if meta.get("byte_size") is not None else 0,
        file_path=file_path,
    )
    return _to_meta(row)


@router.post(
    "/{conversation_id}/attachments",
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    conversation_id: str,
    request: Request,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
) -> dict[str, object]:
    user_id = str(current_user["id"])

    conversation = await get_conversation(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    content_type = (file.content_type or "").lower()
    if content_type == "application/pdf":
        return await _handle_pdf_upload(request, user_id, conversation_id, file)
    if content_type in _IMAGE_MIME_TYPES:
        return await _handle_image_upload(user_id, conversation_id, file)

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=(
            f"Expected application/pdf or image/(png|jpeg|webp), "
            f"got {file.content_type or 'unknown'}"
        ),
    )


@router.get("/{conversation_id}/attachments")
async def list_attachments_endpoint(
    conversation_id: str,
    current_user: CurrentUser,
) -> list[dict[str, object]]:
    user_id = str(current_user["id"])
    conversation = await get_conversation(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )
    rows = await list_conversation_attachments(user_id, conversation_id)
    return [_to_meta(row) for row in rows]


@router.get("/{conversation_id}/attachments/{attachment_id}/raw")
async def serve_attachment_raw(
    conversation_id: str,
    attachment_id: int,
    current_user: CurrentUser,
) -> FileResponse:
    """Serve the raw bytes of an image attachment.

    Only image attachments are served (PDFs are stored as extracted markdown,
    not as the original file). Authorization is enforced through
    ``get_attachment`` which joins on conversation ownership.
    """
    user_id = str(current_user["id"])
    conversation = await get_conversation(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    row = await get_attachment(user_id, attachment_id)
    if row is None or str(row.get("conversation_id")) != conversation_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attachment {attachment_id} not found",
        )

    if (row.get("attachment_type") or "pdf") != "image":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only image attachments can be served raw",
        )

    file_path = row.get("file_path")
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file path missing",
        )
    path = Path(str(file_path))
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file no longer on disk",
        )

    return FileResponse(
        path=path,
        media_type=str(row.get("mime_type") or "image/jpeg"),
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.delete(
    "/{conversation_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_attachment_endpoint(
    conversation_id: str,
    attachment_id: int,
    current_user: CurrentUser,
) -> Response:
    user_id = str(current_user["id"])
    conversation = await get_conversation(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    # Capture file_path before delete so we can clean up disk if it becomes orphan.
    existing = await get_attachment(user_id, attachment_id)
    deleted = await delete_attachment(user_id, attachment_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attachment {attachment_id} not found",
        )

    if (
        existing is not None
        and existing.get("attachment_type") == "image"
        and existing.get("file_path")
    ):
        path = str(existing["file_path"])
        if await is_file_path_orphan(path):
            image_store.remove_image_file(path)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
