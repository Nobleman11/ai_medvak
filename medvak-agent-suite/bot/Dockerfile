FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml /app/
RUN pip install --no-cache-dir -U pip && pip install -e .

COPY . /app

CMD ["python", "main.py"]
