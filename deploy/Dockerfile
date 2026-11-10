# syntax=docker/dockerfile:1
# One Python image for api, bot, userbot and the one-shot migrate job (the command decides which).
FROM ghcr.io/astral-sh/uv:0.11.3 AS uv

FROM python:3.13-slim-trixie
COPY --from=uv /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/packages/core:/app/packages/payments:/app/apps/bot:/app/apps/userbot:/app/apps/api

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --python /usr/local/bin/python3.13

COPY packages ./packages
COPY apps/bot ./apps/bot
COPY apps/api ./apps/api
COPY apps/userbot ./apps/userbot

RUN useradd --system --uid 10001 --home-dir /app tulporgo \
    && mkdir -p /app/state && chown tulporgo:tulporgo /app/state   # offsite backup state (named volume)
USER tulporgo

# default: HTTP API; compose overrides the command for bot / userbot / migrate
CMD ["uvicorn", "tulporgo_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
