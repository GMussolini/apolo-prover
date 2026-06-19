import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.core.config import get_config
from app.core.database import init_pools, close_pools
from app.core.logging_config import configurar_logging, logger
from app.api.health_routes import router as health_router
from app.api.auth_routes import router as auth_router
from app.api.sessoes_routes import router as sessoes_router
from app.api.chat_routes import router as chat_router
from app.api.voice_routes import router as voice_router
from app.installer.setup_usuarios import seed_usuarios_iniciais


configurar_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    from app.core.migrations.runner import aplicar_migrations
    aplicar_migrations()
    seed_usuarios_iniciais()
    await init_pools()
    logger.info("apolo_starting", anthropic=bool(cfg.anthropic_api_key), openai=bool(cfg.openai_api_key))
    yield
    await close_pools()
    logger.info("apolo_shutdown")


app = FastAPI(title="APOLO_PROVER", version="0.1.0", lifespan=lifespan)

_cfg = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cfg.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=rid, path=request.url.path)
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response
    finally:
        structlog.contextvars.clear_contextvars()


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(sessoes_router)
app.include_router(chat_router)
app.include_router(voice_router)
