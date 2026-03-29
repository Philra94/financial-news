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

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY agents ./agents
COPY cli ./cli
COPY config ./config
COPY data ./data
COPY web/backend ./web/backend
COPY pyproject.toml README.md ./
COPY --from=frontend-build /app/web/frontend/dist ./web/frontend/dist

EXPOSE 8080

CMD ["uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
