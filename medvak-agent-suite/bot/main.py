from __future__ import annotations
import logging
import os
from telegram.ext import Application

import handlers
from api import close_client

logging.basicConfig(
    level=os.getenv("BOT_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is not set")

    app = Application.builder().token(BOT_TOKEN).build()
    handlers.register(app)

    # корректно закрыть httpx клиент при остановке
    import atexit, asyncio
    atexit.register(lambda: asyncio.run(close_client()))

    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
