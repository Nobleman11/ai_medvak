from __future__ import annotations
import os
import re
from typing import List, Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.tools.schema import Record, PreviewItem
from agent.tools.ingest_csv import parse_csv_text
from agent.tools.preview import preview_records
from agent.tools.write import write_records
from agent.tools.scrape_zp import scrape_zarplata
from agent.tools.scrape_hh import scrape_hh

from agent.config import settings

# Chat LLM (для small talk; NLU ниже — правилaми, без токенов)
from openai import OpenAI
_oai = OpenAI(api_key=settings.OPENAI_API_KEY)

api = APIRouter()

# ────────────────────────────── DTO ──────────────────────────────────
class PreviewRequest(BaseModel):
    csv_text: Optional[str] = None
    text: Optional[str] = None

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

# ─ Chat / Intent
class Intent(BaseModel):
    action: Literal["scrape","parse_csv","small_talk","help","none"] = "none"
    source: Optional[Literal["zp","hh"]] = None
    query: Optional[str] = None
    hospital: Optional[str] = None
    pages: Optional[int] = None

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    intent: Optional[Intent] = None

# ────────────────────────────── helpers ───────────────────────────────
_ALIASES = None
def _load_aliases() -> dict:
    from agent.tools.normalize import load_aliases
    global _ALIASES
    if _ALIASES is None:
        _ALIASES = load_aliases(settings.ALIASES_FILE)
    return _ALIASES

def _match_hospital(text: str) -> Optional[str]:
    """
    Простое сопоставление по алиасам: если ключ встречается в тексте,
    возвращаем канон.
    """
    aliases = _load_aliases()
    low = text.lower()
    for k, v in aliases.items():
        if k.lower() in low:
            return v
    # очень простая эвристика на «в больнице …»
    m = re.search(r"в\s+(?:больнице|гкб|дгкб|одкб)\s*([^\n,;]+)", low)
    if m:
        return m.group(0).strip()
    return None

def _parse_pages(text: str, default_pages: int) -> int:
    m = re.search(r"(?:на|по)\s*(\d+)\s*(?:стр|страниц[а-я]*)", text)
    if m:
        try:
            return max(1, min(10, int(m.group(1))))  # безопасность: 1..10
        except ValueError:
            pass
    return default_pages

def _parse_source(text: str) -> Optional[str]:
    t = text.lower()
    if any(w in t for w in ("зарплата", "zarplata", "zp", "зарплата.ру", "зарплата ру")):
        return "zp"
    if any(w in t for w in ("hh", "headhunter", "хх", "хэдхантер")):
        return "hh"
    return None

def _parse_query(text: str) -> Optional[str]:
    t = text.lower()
    # Основной кейс: медсестра/медсестёр/медицинская сестра
    if "медсестр" in t:
        return "медсестра"
    # fallback: попытаться вытащить слово после "ваканси"
    m = re.search(r"ваканси[яи]\s+([^\s,.;]+)", t)
    if m:
        return m.group(1)
    return None

def parse_intent_free_text(msg: str) -> Intent:
    """
    Лёгкий NLU без токенов: правила + алиасы.
    """
    t = msg.strip()
    if not t:
        return Intent(action="none")

    # CSV в тексте?
    if "," in t and "Title" in t and "Должность" in t:
        return Intent(action="parse_csv")

    # Скрейп сайтов?
    src = _parse_source(t)
    qry = _parse_query(t)
    hosp = _match_hospital(t)
    pages = _parse_pages(t, settings.WEB_DEFAULT_PAGES)

    if src and (qry or "найти" in t or "поиск" in t):
        return Intent(action="scrape", source=src, query=(qry or "медсестра"), hospital=hosp, pages=pages)

    # Small talk / help
    if any(w in t.lower() for w in ("привет", "как дела", "как ты", "спасибо", "помощь", "что умеешь")):
        return Intent(action="small_talk")
    return Intent(action="none")

# ────────────────────────────── endpoints ────────────────────────────
@api.post("/preview", response_model=PreviewResponse)
def post_preview(req: PreviewRequest):
    csv_payload = req.csv_text or req.text
    if not csv_payload:
        raise HTTPException(400, detail="Provide 'csv_text' or 'text' with CSV content.")
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

@api.post("/chat", response_model=ChatResponse)
def post_chat(req: ChatRequest):
    if os.getenv("CHAT_ENABLED", "0") != "1":
        raise HTTPException(400, detail="Chat is disabled. Set CHAT_ENABLED=1")

    intent = parse_intent_free_text(req.message)

    # 1) Если явный скрейп распознан — вернём структурированно (бот решит, запускать ли /scrape)
    if intent.action == "scrape":
        src_text = "zarplata.ru" if intent.source == "zp" else "hh.ru"
        reply = (
            f"Понял запрос: поиск на {src_text}\n"
            f"• роль: {intent.query}\n"
            f"• больница: {intent.hospital or '—'}\n"
            f"• страниц: {intent.pages}\n"
            "Могу собрать PREVIEW. Убедитесь, что выбрана таблица (/use_table)."
        )
        if not settings.WEB_SCRAPE_ENABLED:
            reply += "\n⚠️ Веб-скрейп сейчас выключен (WEB_SCRAPE_ENABLED=0)."
        return ChatResponse(reply=reply, intent=intent)

    # 2) CSV-текст?
    if intent.action == "parse_csv":
        return ChatResponse(
            reply="Вижу, что это CSV. Пришлите файлом или используйте /parse <CSV-текст>, и я сделаю PREVIEW.",
            intent=intent
        )

    # 3) Small talk
    sys_prompt = (
        "Ты — помощник HR-бота клиники. Отвечай кратко и дружелюбно. "
        "Если спрашивают про вакансии/поиск — подскажи, что можно написать: "
        "«найди на зарплата ру медсестёр в ОДКБ на 2 страницы», "
        "и что перед записью нужна команда /use_table <TABLE_ID>."
    )
    resp = _oai.chat.completions.create(
        model=settings.AGENT_MODEL,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": req.message.strip()},
        ],
        temperature=0.4,
        max_tokens=200,
    )
    answer = resp.choices[0].message.content.strip()
    return ChatResponse(reply=answer, intent=intent)

@api.get("/config")
def get_config():
    return {
        "tz": settings.TZ,
        "model": settings.AGENT_MODEL,
        "nocodb_base": settings.NOCODB_BASE,
        "web_scrape_enabled": settings.WEB_SCRAPE_ENABLED,
        "auto_write_enabled": settings.AUTO_WRITE_ENABLED,
        "preview_page_size": settings.PREVIEW_PAGE_SIZE,
        "agent_map_path": settings.AGENT_MAP_PATH,
    }
