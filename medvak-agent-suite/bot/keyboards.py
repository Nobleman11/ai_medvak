from __future__ import annotations
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def preview_item_kb(idx: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для одной карточки PREVIEW.
    Совпадает с callback_data, которую ожидают handlers.py:
    - write_one:{idx}
    - skip_one:{idx}
    """
    kb = [
        [
            InlineKeyboardButton("✅ Записать эту", callback_data=f"write_one:{idx}"),
            InlineKeyboardButton("⏭ Пропустить",    callback_data=f"skip_one:{idx}"),
        ]
    ]
    return InlineKeyboardMarkup(kb)


def simple_ok_kb() -> InlineKeyboardMarkup:
    """Универсальная клавиатура 'Ок' (на будущее)."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("Ок", callback_data="ok")]])
