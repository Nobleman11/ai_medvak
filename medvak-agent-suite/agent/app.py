from __future__ import annotations
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.router import api
from agent.config import settings

# ────────────────────────────── logging ──────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.AGENT_LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

log = logging.getLogger("medvak_agent")

# ────────────────────────────── app ──────────────────────────────────
app = FastAPI(
    title="Medvak Agent",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

# CORS: при необходимости открыть из внешнего UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.AGENT_ALLOWED_ORIGINS] if settings.AGENT_ALLOWED_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# маршруты
app.include_router(api)

# ────────────────────────────── lifecycle ────────────────────────────
@app.on_event("startup")
async def on_startup():
    log.info(
        "agent.start tz=%s model=%s web_scrape=%s map=%s",
        settings.TZ,
        settings.AGENT_MODEL,
        settings.WEB_SCRAPE_ENABLED,
        settings.AGENT_MAP_PATH,
    )
    # Тут можно проинициализировать кэш справочников, если нужно
    # (мы читаем их на лету внутри tools/preview.py)

@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": "medvak_agent"}
