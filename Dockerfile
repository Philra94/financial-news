FROM node:20-bookworm-slim AS frontend-build
WORKDIR /app/web/frontend

COPY web/frontend/package*.json ./
RUN npm install

COPY web/frontend ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/app
ENV BROWSER_USE_HOME=/home/app/.browser-use

COPY requirements.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid 1000 --create-home --home-dir /home/app --shell /bin/bash app

COPY agents ./agents
COPY cli ./cli
COPY .agents ./.agents
COPY config ./config
COPY data ./data
COPY web/backend ./web/backend
COPY pyproject.toml README.md ./
COPY --from=frontend-build /app/web/frontend/dist ./web/frontend/dist

RUN chown -R app:app /app /home/app

USER app

EXPOSE 8080

CMD ["uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
