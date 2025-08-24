from __future__ import annotations
import os
import logging
from typing import Any, Dict, List, Optional, Tuple

from telegram import Update
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from . import api
from .parser_csv import sanitize_csv_text, is_probable_csv_text
from .keyboards import preview_item_kb

log = logging.getLogger("bot.handlers")

# Состояние на пользователя (минимум — выбранная таблица и текущий PREVIEW)
STATE: Dict[int, Dict[str, Any]] = {}

DEFAULT_REL = os.getenv("VAC_REQ_ODKB_REL", "Требования")
ENV_ODKB_TABLE = os.getenv("VACANCIES_TABLE_ODKB_ID", "")
CHAT_ENABLED = os.getenv("CHAT_ENABLED", "0") == "1"
WEB_SCRAPE_ENABLED = os.getenv("WEB_SCRAPE_ENABLED", "0") == "1"
WEB_DEFAULT_PAGES = int(os.getenv("WEB_DEFAULT_PAGES", "2"))


def _ensure_state(user_id: int) -> Dict[str, Any]:
    st = STATE.get(user_id)
    if not st:
        st = {"table_id": None, "rel_name": DEFAULT_REL, "preview": []}
        STATE[user_id] = st
    return st


def _render_item_card(item: Dict[str, Any], idx: int) -> Tuple[str, 'InlineKeyboardMarkup']:
    rec = item.get("record", {})
    uncertain = item.get("uncertain", [])
    conf = item.get("confidence", 0)

    title = rec.get("Title") or "(без заголовка)"
    dept = rec.get("Отделение") or "—"
    role = rec.get("Должность") or "—"
    worker = ", ".join(rec.get("Работник", []) or []) or "—"
    schedule = ", ".join(rec.get("График", []) or []) or "—"
    shift = ", ".join(rec.get("Тип_смены", []) or []) or "—"
    time_ = ", ".join(rec.get("Время_работы", []) or []) or "—"
    salary = rec.get("Зарплата") or "—"
    contact = rec.get("Контактное_лицо") or "—"
    status = rec.get("Статус") or "—"

    lines = [
        f"🔎 #{idx+1} • conf={conf}",
        f"🧾 {title}",
        f"🏥 Отделение: {dept}",
        f"👤 Должность: {role}",
        f"👥 Работник: {worker}",
        f"📅 График: {schedule}",
        f"🕒 Смены: {shift}",
        f"⏱ Время: {time_}",
        f"💰 Зарплата: {salary}",
        f"☎️ Контакт: {contact}",
        f"📌 Статус: {status}",
    ]
    if uncertain:
        ulist = "; ".join([f"{u.get('field')} ⇒ {', '.join(u.get('suggest', []) or [])}" for u in uncertain])
        lines.append(f"⚠️ Непопадания: {ulist}")

    return "\n".join(lines), preview_item_kb(idx)


async def _require_table(update: Update, _: ContextTypes.DEFAULT_TYPE, st: Dict[str, Any]) -> bool:
    if st.get("table_id"):
        return True
    hint = f"\n\nНапример: /use_table {ENV_ODKB_TABLE}" if ENV_ODKB_TABLE else ""
    await update.effective_message.reply_text(
        "Не задана таблица для записи. Укажите её командой:\n/use_table <TABLE_ID>" + hint
    )
    return False


# ---------------------- Commands ----------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = _ensure_state(update.effective_user.id)
    msg = [
        "👋 Привет! Я превращаю CSV в чистые записи NocoDB.",
        "Команды:",
        "• /use_table <TABLE_ID> — куда писать",
        f"• /use_rel <REL_NAME> — связь требований (сейчас: {st.get('rel_name')})",
        "• /parse <CSV-текст> — превью из текста",
        "• /preview — показать текущие карточки",
        "• /confirm — записать все карточки",
        "• /status — здоровье агента",
    ]
    if CHAT_ENABLED:
        msg.append("Чат включён — можете писать свободным текстом (например: «найди на зарплата ру медсестёр в ОДКБ на 2 страницы»).")
    await update.message.reply_text("\n".join(msg))


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    h = await api.agent_health()
    await update.message.reply_text(f"✅ agent ok: {h}")


async def cmd_use_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = _ensure_state(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Использование: /use_table <TABLE_ID>")
        return
    st["table_id"] = context.args[0].strip()
    await update.message.reply_text(f"Таблица установлена: `{st['table_id']}`", parse_mode="Markdown")


async def cmd_use_rel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = _ensure_state(update.effective_user.id)
    if not context.args:
        await update.message.reply_text(f"Использование: /use_rel <REL_NAME>\nТекущее: {st['rel_name']}")
        return
    st["rel_name"] = " ".join(context.args).strip()
    await update.message.reply_text(f"Имя связи установлено: {st['rel_name']}")


async def cmd_parse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """CSV-текст после команды → превью."""
    text = update.message.text or ""
    csv_text = text.partition(" ")[2].strip()
    if not csv_text:
        await update.message.reply_text("Пришлите текст CSV после команды, либо просто отправьте CSV-файл.")
        return
    data = await api.preview_csv(csv_text)
    items = data.get("items", [])
    st = _ensure_state(update.effective_user.id)
    st["preview"] = items
    await update.message.reply_text(f"Готово. Найдено карточек: {len(items)}")
    await _send_preview_batch(update, context, items)


async def cmd_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = _ensure_state(update.effective_user.id)
    items = st.get("preview", [])
    if not items:
        await update.message.reply_text("Нет карточек. Пришлите CSV или используйте /parse.")
        return
    await _send_preview_batch(update, context, items)


async def cmd_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = _ensure_state(update.effective_user.id)
    if not await _require_table(update, context, st):
        return
    items = st.get("preview", [])
    if not items:
        await update.message.reply_text("Нечего записывать. Сначала сделайте PREVIEW.")
        return
    records = [it.get("record", {}) for it in items]
    res = await api.write_records(records, table_id=st["table_id"], rel_name=st.get("rel_name"))
    await update.message.reply_text(f"Результат записи: {res}")


# ---------------- Documents / Text ----------------

async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """CSV-файл → превью."""
    doc = update.message.document
    if not doc:
        return
    if not (doc.file_name or "").lower().endswith((".csv", ".txt")):
        await update.message.reply_text("Пришлите CSV или TXT файл.")
        return

    file = await doc.get_file()
    data = await file.download_as_bytearray()
    try:
        csv_text = data.decode("utf-8")
    except UnicodeDecodeError:
        csv_text = data.decode("cp1251", errors="replace")
    csv_text = sanitize_csv_text(csv_text)

    preview = await api.preview_csv(csv_text)
    items = preview.get("items", [])
    st = _ensure_state(update.effective_user.id)
    st["preview"] = items
    await update.message.reply_text(f"Файл принят. Карточек: {len(items)}")
    await _send_preview_batch(update, context, items)


async def on_plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Свободный текст:
      1) если похоже на CSV — сразу превью,
      2) если чат включён — отправляем /chat и, при intent=scrape, запускаем /scrape → PREVIEW,
      3) иначе подсказываем про CSV.
    """
    text = (update.message.text or "").strip()
    if not text:
        return

    # (1) Эвристика CSV
    if is_probable_csv_text(text):
        data = await api.preview_csv(sanitize_csv_text(text))
        items = data.get("items", [])
        st = _ensure_state(update.effective_user.id)
        st["preview"] = items
        await update.message.reply_text(f"Распознал CSV. Карточек: {len(items)}")
        await _send_preview_batch(update, context, items)
        return

    # (2) Чат + намерения
    if CHAT_ENABLED:
        data = await api.chat(text)  # {"reply": "...", "intent": {...}}
        reply = data.get("reply") or ""
        intent = data.get("intent") or {}
        action = intent.get("action")

        # Автозапуск скрейпа → PREVIEW
        if action == "scrape":
            if not WEB_SCRAPE_ENABLED:
                await update.message.reply_text((reply + "\n\n⚠️ Веб-скрейп выключен (WEB_SCRAPE_ENABLED=0).").strip())
                return

            src = intent.get("source") or "zp"
            qry = intent.get("query") or "медсестра"
            hosp = intent.get("hospital")
            pages = int(intent.get("pages") or WEB_DEFAULT_PAGES)

            if reply:
                await update.message.reply_text(reply)

            prev = await api.scrape(src, qry, hosp, pages)
            items = prev.get("items", [])
            st = _ensure_state(update.effective_user.id)
            st["preview"] = items
            await update.message.reply_text(
                f"Готово. Карточек в PREVIEW: {len(items)}.\n"
                f"Чтобы записать — укажите таблицу: /use_table <TABLE_ID>, затем /confirm."
            )
            await _send_preview_batch(update, context, items)
            return

        # Small talk / подсказки
        if reply:
            await update.message.reply_text(reply)
            return

    # (3) Чат выключен или ничего не распознано
    await update.message.reply_text("Я работаю с CSV и командами. Пришлите файл или используйте /parse <CSV>.")


# ---------------- Callbacks & Helpers ----------------

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    uid = update.effective_user.id
    st = _ensure_state(uid)
    items = st.get("preview", [])

    if data.startswith("write_one:"):
        if not await _require_table(update, context, st):
            return
        idx = int(data.split(":")[1])
        if idx < 0 or idx >= len(items):
            await query.edit_message_text("Элемент не найден.")
            return
        rec = items[idx].get("record", {})
        res = await api.write_records([rec], table_id=st["table_id"], rel_name=st.get("rel_name"))
        await query.edit_message_text(f"✅ Записано: {res}")
        return

    if data.startswith("skip_one:"):
        idx = int(data.split(":")[1])
        if 0 <= idx < len(items):
            items.pop(idx)
            await query.edit_message_text("⏭ Пропущено.")
        else:
            await query.edit_message_text("Элемент не найден.")
        return


async def _send_preview_batch(update: Update, context: ContextTypes.DEFAULT_TYPE, items: List[Dict[str, Any]]):
    """Отправляем до 10 карточек, чтобы не заспамить чат."""
    chat_id = update.effective_chat.id
    if not items:
        await context.bot.send_message(chat_id, "Пусто.")
        return
    limit = min(len(items), 10)
    for i in range(limit):
        text, kb = _render_item_card(items[i], i)
        await context.bot.send_message(chat_id, text, reply_markup=kb)


def register(app):
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("use_table", cmd_use_table))
    app.add_handler(CommandHandler("use_rel", cmd_use_rel))
    app.add_handler(CommandHandler("parse", cmd_parse))
    app.add_handler(CommandHandler("preview", cmd_preview))
    app.add_handler(CommandHandler("confirm", cmd_confirm))

    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_plain_text))
