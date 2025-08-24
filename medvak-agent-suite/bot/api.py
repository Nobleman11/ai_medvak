from __future__ import annotations
import os
import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger("bot.api")

AGENT_BASE = os.getenv("AGENT_INTERNAL_URL", "http://medvak_agent:8000").rstrip("/")
_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SEC", "20"))
_MAX_CONN = int(os.getenv("HTTPX_MAX_CONN", "4"))
_MAX_KEEP = int(os.getenv("HTTPX_MAX_KEEPALIVE", "2"))

_limits = httpx.Limits(max_connections=_MAX_CONN, max_keepalive_connections=_MAX_KEEP)
_client = httpx.AsyncClient(base_url=AGENT_BASE, timeout=_TIMEOUT, limits=_limits)

async def close_client():
    await _client.aclose()

# ---------- Agent API wrappers ----------

async def agent_health() -> Dict[str, Any]:
    r = await _client.get("/healthz")
    r.raise_for_status()
    return r.json()

async def agent_config() -> Dict[str, Any]:
    r = await _client.get("/config")
    r.raise_for_status()
    return r.json()

async def preview_csv(csv_text: str) -> Dict[str, Any]:
    """POST /preview {csv_text} → {version, items:[{record, uncertain, notes, confidence}]}"""
    payload = {"csv_text": csv_text}
    r = await _client.post("/preview", json=payload)
    if r.status_code >= 400:
        log.error("preview error %s: %s", r.status_code, r.text)
    r.raise_for_status()
    return r.json()

async def write_records(records: List[Dict[str, Any]], table_id: str, rel_name: Optional[str]=None) -> Dict[str, Any]:
    """POST /write {records, table_id, rel_name} → {results:[...]}"""
    payload = {"records": records, "table_id": table_id, "rel_name": rel_name}
    r = await _client.post("/write", json=payload)
    if r.status_code >= 400:
        log.error("write error %s: %s", r.status_code, r.text)
    r.raise_for_status()
    return r.json()

async def scrape(source: str, query: str, hospital: Optional[str], pages: int = 2) -> Dict[str, Any]:
    """POST /scrape {source:'zp'|'hh', query, hospital?, pages} → preview"""
    payload = {"source": source, "query": query, "hospital": hospital, "pages": pages}
    r = await _client.post("/scrape", json=payload)
    r.raise_for_status()
    return r.json()
