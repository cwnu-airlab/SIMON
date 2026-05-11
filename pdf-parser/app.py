"""PDF 파싱 마이크로서비스 — OpenDataLoader 래퍼.

엔드포인트:
- GET  /health          health + hybrid backend reachability
- POST /parse           multipart PDF → {markdown, pages, duration_ms}

환경변수:
- MAX_FILE_MB             기본 50
- MAX_PAGES               기본 100
- OCR_LANG                기본 "ko,en" (entrypoint에서만 사용)
- HYBRID_BACKEND_URL      기본 "http://localhost:5002"
"""

from __future__ import annotations

import glob
import logging
import os
import socket
import tempfile
import time
from typing import Annotated

import opendataloader_pdf
import pypdf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("invalid int for %s=%r, using %d", name, raw, default)
        return default


MAX_FILE_MB = _env_int("MAX_FILE_MB", 50)
MAX_PAGES = _env_int("MAX_PAGES", 100)
HYBRID_BACKEND_URL = os.environ.get("HYBRID_BACKEND_URL", "http://localhost:5002")
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024


app = FastAPI(title="pdf-parser", version="0.1.0")


def _hybrid_reachable() -> bool:
    """TCP-level reachability probe for the docling-fast hybrid backend."""
    try:
        # Parse out host:port from URL.
        url = HYBRID_BACKEND_URL.removeprefix("http://").removeprefix("https://")
        host, _, port_s = url.partition(":")
        port = int(port_s.split("/")[0]) if port_s else 80
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except (OSError, ValueError):
        return False


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "hybrid": "ready" if _hybrid_reachable() else "down",
    }


@app.post("/parse")
async def parse(
    file: Annotated[UploadFile, File()],
    force_ocr: Annotated[bool, Form()] = False,
) -> JSONResponse:
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Expected application/pdf, got {file.content_type}",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {MAX_FILE_MB}MB limit ({len(file_bytes)} bytes)",
        )

    started = time.monotonic()

    with tempfile.TemporaryDirectory() as tmp:
        in_path = os.path.join(tmp, file.filename or "input.pdf")
        out_dir = os.path.join(tmp, "out")
        os.makedirs(out_dir, exist_ok=True)
        with open(in_path, "wb") as f:
            f.write(file_bytes)

        # Page-count pre-flight.
        try:
            reader = pypdf.PdfReader(in_path)
            pages = len(reader.pages)
        except Exception as exc:
            logger.warning("pypdf failed to read %s: %s", file.filename, exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not read PDF: {exc}",
            ) from exc

        if pages > MAX_PAGES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"PDF exceeds {MAX_PAGES} page limit ({pages} pages)",
            )

        convert_kwargs: dict[str, object] = {
            "input_path": [in_path],
            "output_dir": out_dir,
            "format": "markdown",
            "quiet": True,
        }
        if force_ocr:
            convert_kwargs["hybrid"] = "docling-fast"
            convert_kwargs["hybrid_url"] = HYBRID_BACKEND_URL
            # `auto` triage silently drops docling-fast OCR output and emits only
            # image placeholders; `full` synthesizes markdown from the OCR JSON.
            convert_kwargs["hybrid_mode"] = "full"
            # On docling-fast 5xx, fall back to placeholder output instead of failing /parse.
            convert_kwargs["hybrid_fallback"] = True

        try:
            opendataloader_pdf.convert(**convert_kwargs)
        except Exception as exc:
            logger.error(
                "opendataloader convert failed for %s: %s",
                file.filename,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PDF conversion failed: {exc}",
            ) from exc

        md_files = sorted(glob.glob(os.path.join(out_dir, "**", "*.md"), recursive=True))
        if not md_files:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="opendataloader produced no markdown output",
            )

        with open(md_files[0], encoding="utf-8") as f:
            markdown = f.read()

    duration_ms = int((time.monotonic() - started) * 1000)

    return JSONResponse(
        {
            "markdown": markdown,
            "pages": pages,
            "duration_ms": duration_ms,
        }
    )
