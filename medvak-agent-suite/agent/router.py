from __future__ import annotations
from typing import List, Optional, Literal

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from tools.schema import Record, PreviewItem
from tools.ingest_csv import parse_csv_text
from tools.preview import preview_records
from tools.write import write_records
from tools.scrape_zp import scrape_zarplata
from tools.scrape_hh import scrape_hh

from config import settings

api = APIRouter()

# ────────────────────────────── DTO ──────────────────────────────────
class PreviewRequest(BaseModel):
    csv_text: Optional[str] = None
    text: Optional[str] = None  # можно бросать CSV и сюда — попробуем разобрать

class PreviewResponse(BaseModel):
    version: str = "map-local"
    items: List[PreviewItem] = []

class WriteRequest(BaseModel):
    records: List[Record]
    table_id: str
    rel_name: Optional[str] = None

class ScrapeRequest(BaseModel):
    source: Literal["zp", "hh"]
    query: str
    hospital: Optional[str] = None
    pages: int = 2

# ────────────────────────────── endpoints ────────────────────────────
@api.post("/preview", response_model=PreviewResponse)
def post_preview(req: PreviewRequest):
    csv_payload = req.csv_text or req.text
    if not csv_payload:
        raise HTTPException(400, detail="Provide 'csv_text' or 'text' with CSV content.")

    # Разбираем CSV → Record[]
    records = parse_csv_text(csv_payload)
    items = preview_records(records)
    return PreviewResponse(items=items)

@api.post("/write")
def post_write(req: WriteRequest):
    if not req.records:
        raise HTTPException(400, detail="No records provided")
    results = write_records(records=req.records, table_id=req.table_id, rel_name=req.rel_name)
    return {"results": results}

@api.post("/scrape", response_model=PreviewResponse)
def post_scrape(req: ScrapeRequest):
    if not settings.WEB_SCRAPE_ENABLED:
        raise HTTPException(400, detail="WEB scraping is disabled. Set WEB_SCRAPE_ENABLED=1")

    if req.source == "zp":
        recs = scrape_zarplata(req.query, hospital=req.hospital, pages=req.pages)
    else:
        recs = scrape_hh(req.query, hospital=req.hospital, pages=req.pages)

    items = preview_records(recs)
    return PreviewResponse(items=items)

@api.get("/config")
def get_config():
    # безопасный дамп основных флагов
    return {
        "tz": settings.TZ,
        "model": settings.AGENT_MODEL,
        "nocodb_base": settings.NOCODB_BASE,
        "web_scrape_enabled": settings.WEB_SCRAPE_ENABLED,
        "auto_write_enabled": settings.AUTO_WRITE_ENABLED,
        "preview_page_size": settings.PREVIEW_PAGE_SIZE,
        "agent_map_path": settings.AGENT_MAP_PATH,
    }
