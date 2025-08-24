# medvak-agent-suite

Два сервиса:
- `agent/` — ASGI (FastAPI). Эндпоинты: `/preview`, `/write`, `/scrape`, `/healthz`.
- `bot/` — Telegram-бот. Принимает CSV (файл/текст) → показывает PREVIEW и по подтверждению пишет в NocoDB.

## Быстрый старт

```bash
cd ops
cp .env.example .env
# отредактируйте .env (токены, таблицы)
docker compose up -d --build
