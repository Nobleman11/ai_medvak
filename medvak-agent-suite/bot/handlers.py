from __future__ import annotations
import io
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from . import api

log = logging.getLogger("bot.handlers")

# In-memory состояние (на пользователя)
STATE: Dict[int, Dict[str, Any]] = {}
DEFAULT_REL = os.getenv("VAC_REQ_ODKB_REL", "Требования")  # просто имя поля-связи, если будет нужно
ENV_ODKB_TABLE = os.getenv("VACANCIES_TABLE_ODKB_ID", "")  # не дефолт — только подсказка

# ─────────────────────────────── utils ───────────────────────────────

def _ensure_state(user_id: int) -> Dict[str, Any]:
    st = STATE.get(user_id)
    if not st:
        st = {"table_id": None, "rel_name": DEFAULT_REL, "preview": []}
        STATE[user_id] = st
    return st

def _render_item_card(item: Dict[str, Any], idx: int) -> Tuple[str, InlineKeyboardMarkup]:
    rec = item.get("record", {})
    uncertain = item.get("uncertain", [])
    conf = item.get("confidence", 0)

    title = rec.get("Title") or "(без заголовка)"
    dept = rec.get("Отделение")
    role = rec.get("Должность")
    worker = ", ".join(rec.get("Работник", []) or [])
    schedule = ", ".join(rec.get("График", []) or [])
    shift = ", ".join(rec.get("Тип_смены", []) or [])
    time_ = ", ".join(rec.get("Время_работы", []) or [])
    salary = rec.get("Зарплата")
    contact = rec.get("Контактное_лицо")
    status = rec.get("Статус")

    lines = [
        f"🔎 #{idx+1} • conf={conf}",
        f"🧾 {title}",
        f"🏥 Отделение: {dept or '—'}",
        f"👤 Должность: {role or '—'}",
        f"👥 Работник: {worker or '—'}",
        f"📅 График: {schedule or '—'}",
        f"🕒 Смены: {shift or '—'}",
        f"⏱ Время: {time_ or '—'}",
        f"💰 Зарплата: {salary or '—'}",
        f"☎️ Контакт: {contact or '—'}",
        f"📌 Статус: {status or '—'}",
    ]
    if uncertain:
        ulist = "; ".join([f"{u.get('field')} ⇒ {', '.join(u.get('suggest', []) or [])}" for u in uncertain])
        lines.append(f"⚠️ Непопадания: {ulist}")

    kb = [
        [InlineKeyboardButton("✅ Записать эту", callback_data=f"write_one:{idx}"),
         InlineKeyboardButton("⏭ Пропустить", callback_data=f"skip_one:{idx}")]
    ]
    return "\n".join(lines), InlineKeyboardMarkup(kb)

async def _require_table(update: Update, context: ContextTypes.DEFAULT_TYPE, st: Dict[str, Any]) -> bool:
    if st.get("table_id"):
        return True
    hint = f"\n\nНапример: /use_table {ENV_ODKB_TABLE}" if ENV_ODKB_TABLE else ""
    await update.effective_message.reply_text(
        "Не задана таблица для записи. Укажите её командой:\n/use_table <TABLE_ID>" + hint
    )
    return False

# ─────────────────────────────── commands ────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = _ensure_state(update.effective_user.id)
    cfg = await api.agent_config()
    msg = [
        "👋 Привет! Я готов превратить CSV в PREVIEW и записать в NocoDB.",
        "Отправьте CSV-файл или текст CSV, затем используйте /preview или /confirm.",
        "",
        "Полезное:",
        "• /use_table <TABLE_ID> — выбрать таблицу для записи",
        f"• /use_rel <REL_NAME> — имя связи требований (сейчас: {st.get('rel_name')})",
        "• /parse — если текст CSV в сообщении",
        "• /confirm — записать ВСЕ текущие карточки",
        "• /status — статус агента",
    ]
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
    """Если CSV в тексте (после команды) — превью."""
    text = update.message.text or ""
    csv_text = text.partition(" ")[2].strip()
    if not csv_text:
        await update.message.reply_text("Пришлите текст CSV после команды, либо отправьте CSV-файл (я поймаю).")
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
        await update.message.reply_text("Нет подготовленных карточек. Отправьте CSV или используйте /parse.")
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
    # вытаскиваем records
    records = [it.get("record", {}) for it in items]
    res = await api.write_records(records, table_id=st["table_id"], rel_name=st.get("rel_name"))
    await update.message.reply_text(f"Результат записи: {res}")

# ───────────────────────────── documents/text ─────────────────────────

async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пришёл CSV-файл — читаем до ~1 МБ и отдаём в /preview."""
    doc = update.message.document
    if not doc:
        return
    if not (doc.file_name or "").lower().endswith((".csv", ".txt")):
        await update.message.reply_text("Пришлите CSV или TXT файл.")
        return
    file = await doc.get_file()
    bio = await file.download_as_bytearray()
    try:
        csv_text = bio.decode("utf-8")
    except UnicodeDecodeError:
        csv_text = bio.decode("cp1251", errors="replace")
    data = await api.preview_csv(csv_text)
    items = data.get("items", [])
    st = _ensure_state(update.effective_user.id)
    st["preview"] = items
    await update.message.reply_text(f"Файл принят. Карточек: {len(items)}")
    await _send_preview_batch(update, context, items)

async def on_plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Если прислали CSV без команды — тоже пробуем превью (без спама)."""
    text = (update.message.text or "").strip()
    if "," in text and "Title" in text and "Должность" in text:
        data = await api.preview_csv(text)
        items = data.get("items", [])
        st = _ensure_state(update.effective_user.id)
        st["preview"] = items
        await update.message.reply_text(f"Распознал CSV. Карточек: {len(items)}")
        await _send_preview_batch(update, context, items)

# ───────────────────────────── callbacks ──────────────────────────────

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

# ───────────────────────────── helpers ────────────────────────────────

async def _send_preview_batch(update: Update, context: ContextTypes.DEFAULT_TYPE, items: List[Dict[str, Any]]):
    """Отправляем карточки пачкой (до 10 сообщений, чтобы не заспамить)."""
    chat_id = update.effective_chat.id
    if not items:
        await context.bot.send_message(chat_id, "Пусто.")
        return
    limit = min(len(items), 10)
    for i in range(limit):
        text, kb = _render_item_card(items[i], i)
        await context.bot.send_message(chat_id, text, reply_markup=kb)

# ───────────────────────────── wiring ─────────────────────────────────

def register(app):
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("use_table", cmd_use_table))
    app.add_handler(CommandHandler("use_rel", cmd_use_rel))
    app.add_handler(CommandHandler("parse", cmd_parse))
    app.add_handler(CommandHandler("preview", cmd_preview))
    app.add_handler(CommandHandler("confirm", cmd_confirm))

    app.add_handler(CallbackQueryHandler(on_callback))
    # документы .csv/.txt
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    # попытка распознать CSV-плейнтекст без команд
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_plain_text))
