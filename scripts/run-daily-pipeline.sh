#!/usr/bin/env bash
set -euo pipefail

LOG_DIR=/opt/financial-news/data/logs
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily-pipeline.log"

exec 9>/tmp/financial-news-daily.lock
if ! flock -n 9; then
  echo "[$(date -Iseconds)] Skipping daily pipeline because another run is active." >> "$LOG_FILE"
  exit 0
fi

{
  echo "[$(date -Iseconds)] Starting daily pipeline"
  docker compose -f /opt/docker-compose.yaml up -d financial-news >/dev/null
  docker exec financial-news python3 -m cli.main run --date "$(date +%F)"
  echo "[$(date -Iseconds)] Daily pipeline completed"
} >> "$LOG_FILE" 2>&1
