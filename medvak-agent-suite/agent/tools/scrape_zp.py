from __future__ import annotations
import os
from typing import List
from .schema import Record

def scrape_zarplata(query: str, hospital: str | None = None, pages: int = 2) -> List[Record]:
    """
    Заглушка: онлайн-скрейп выключен по умолчанию.
    Включить можно, установив WEB_SCRAPE_ENABLED=1 и реализовав httpx-парсинг.
    """
    if os.getenv("WEB_SCRAPE_ENABLED", "0") != "1":
        raise RuntimeError("WEB scraping is disabled. Set WEB_SCRAPE_ENABLED=1 to enable.")
    # TODO: httpx + парсер разметки zarplata.ru, нормализация в Record
    return []
