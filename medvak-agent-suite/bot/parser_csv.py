from __future__ import annotations
import re

from telegram import Message

# Мини-набор полей, по которым распознаём "похоже на наш CSV"
_REQUIRED_HEADERS = {"Title", "Должность"}
# Доп. маркеры — русские поля для повышения уверенности
_RU_HEADERS = {"Отделение", "Работник", "График", "Тип_смены", "Время_работы"}

def sanitize_csv_text(text: str) -> str:
    """
    Приводим CSV к читабельному виду:
    - убираем BOM
    - нормализуем переносы строк
    - обрезаем хвостовые пробелы
    """
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # защищаем от случайных двойных пустых строк
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_probable_csv_text(text: str) -> bool:
    """
    Эвристика: есть запятые, есть хотя бы один обязательный заголовок,
    и хотя бы один из русских заголовков.
    """
    t = text[:2000]  # достаточно заголовков и пары строк
    if "," not in t:
        return False
    has_req = any(h in t for h in _REQUISITE_SET)
    has_ru = any(h in t for h in _RU_HEADERS)
    return has_req and has_ru


# Вынесено, чтобы mypy не ругался на порядок определения
_REQUISITE_SET = _REQUIRED_HEADERS


async def read_document_text(msg: Message) -> str | None:
    """
    Скачивает присланный документ и возвращает содержимое как текст (UTF-8 / CP1251 fallback).
    Возвращает None, если это не документ.
    """
    doc = msg.document
    if not doc:
        return None
    file = await doc.get_file()
    data = await file.download_as_bytearray()

    for enc in ("utf-8", "cp1251"):
        try:
            raw = data.decode(enc)
            return sanitize_csv_text(raw)
        except UnicodeDecodeError:
            continue
    # Последняя попытка — 'latin-1' без ошибок
    return sanitize_csv_text(data.decode("latin-1", errors="replace"))
