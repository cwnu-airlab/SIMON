import contextlib
import logging

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, chat, conversations, openai

logger = logging.getLogger(__name__)

http_client: httpx.AsyncClient | None = None


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client

    await init_db()
    logger.info("Application startup")
    client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
    http_client = client
    app.state.http_client = client
    try:
        yield
    finally:
        client = getattr(app.state, "http_client", None)
        if isinstance(client, httpx.AsyncClient):
            await client.aclose()
        app.state.http_client = None
        http_client = None
        logger.info("Application shutdown")


app = FastAPI(title="SIMON", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.origin.rstrip("/")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(openai.router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    vllm_status = "disconnected"
    if http_client is not None:
        try:
            response = await http_client.get(
                f"{settings.vllm_base_url}/v1/models",
                timeout=5.0,
            )
            if response.status_code == 200:
                vllm_status = "connected"
        except httpx.HTTPError as e:
            logger.warning(f"vLLM health check failed: {e}")

    return {
        "status": "ok",
        "vllm_status": vllm_status,
        "model": settings.vllm_model,
    }
