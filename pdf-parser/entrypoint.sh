#!/bin/sh
# entrypoint for pdf-parser container.
# Starts the docling-fast hybrid backend in the background, waits for it to
# accept TCP connections, then runs the FastAPI wrapper. The wrapper itself
# also exposes a /health that reflects hybrid readiness, so a brief race
# during cold start is acceptable.
set -e

OCR_LANG="${OCR_LANG:-ko,en}"
HYBRID_PORT="${HYBRID_PORT:-5002}"
HYBRID_HOST="${HYBRID_HOST:-0.0.0.0}"

echo "[entrypoint] starting docling-fast hybrid backend on ${HYBRID_HOST}:${HYBRID_PORT}"
opendataloader-pdf-hybrid \
  --host "${HYBRID_HOST}" \
  --port "${HYBRID_PORT}" \
  --force-ocr \
  --ocr-lang "${OCR_LANG}" \
  --device cpu &

# Best-effort readiness wait (TCP-level).
echo "[entrypoint] waiting for hybrid backend (max 120s)"
for i in $(seq 1 120); do
  if (echo > /dev/tcp/127.0.0.1/${HYBRID_PORT}) 2>/dev/null; then
    echo "[entrypoint] hybrid backend ready (after ${i}s)"
    break
  fi
  sleep 1
done

echo "[entrypoint] starting FastAPI wrapper on 0.0.0.0:8080"
exec uvicorn app:app --host 0.0.0.0 --port 8080 --log-level info
