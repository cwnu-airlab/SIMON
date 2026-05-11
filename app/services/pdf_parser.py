"""HTTP client for the pdf-parser sidecar microservice."""

import hashlib
import logging
from typing import cast

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class PdfParserError(RuntimeError):
    """Raised when the pdf-parser sidecar fails or rejects an upload."""


def file_hash(file_bytes: bytes) -> str:
    """SHA-256 hex digest of the upload bytes (used for future caching)."""
    return hashlib.sha256(file_bytes).hexdigest()


async def parse_pdf(
    client: httpx.AsyncClient | None,
    file_bytes: bytes,
    filename: str,
    *,
    force_ocr: bool = False,
) -> dict[str, object]:
    """Send the PDF bytes to pdf-parser:/parse and return its JSON response.

    Returns a dict like ``{"markdown": str, "pages": int, "duration_ms": int}``.
    Raises ``PdfParserError`` on size/page rejections, parse failures, or
    transport errors.
    """
    files = {"file": (filename, file_bytes, "application/pdf")}
    data = {"force_ocr": "true" if force_ocr else "false"}
    timeout = httpx.Timeout(settings.pdf_parser_timeout_sec)
    url = f"{settings.pdf_parser_url}/parse"

    try:
        if client is not None:
            resp = await client.post(url, files=files, data=data, timeout=timeout)
        else:
            async with httpx.AsyncClient(timeout=timeout) as fresh:
                resp = await fresh.post(url, files=files, data=data)
    except httpx.HTTPError as exc:
        logger.error("pdf-parser unreachable at %s: %s", url, exc, exc_info=True)
        raise PdfParserError(f"pdf-parser unreachable: {exc}") from exc

    if resp.status_code == 413:
        raise PdfParserError(f"PDF rejected by parser: {_extract_detail(resp)}")
    if resp.status_code == 415:
        raise PdfParserError(f"Unsupported content type: {_extract_detail(resp)}")
    if resp.status_code == 422:
        raise PdfParserError(f"Could not parse PDF: {_extract_detail(resp)}")
    if resp.status_code >= 500:
        raise PdfParserError(f"pdf-parser internal error: {_extract_detail(resp)}")

    try:
        _ = resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PdfParserError(str(exc)) from exc

    payload = cast(object, resp.json())
    if not isinstance(payload, dict):
        raise PdfParserError("pdf-parser returned non-object payload")
    return cast(dict[str, object], payload)


def _extract_detail(response: httpx.Response) -> str:
    try:
        body = cast(object, response.json())
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}"
    if isinstance(body, dict):
        detail = cast(dict[str, object], body).get("detail")
        if isinstance(detail, str) and detail:
            return detail
    return f"HTTP {response.status_code}"
