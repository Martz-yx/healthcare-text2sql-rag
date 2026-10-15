#!/usr/bin/env bash

# ==============================================================================
# Script: run_dbt_cron.sh
# Purpose: Production dbt cron script for Linux server hosting HIS AI in Docker.
# It detects running containers and executes dbt run & catalog updates daily.
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_DIR}"

mkdir -p "${REPO_DIR}/logs"
LOG_FILE="${REPO_DIR}/logs/dbt_cron.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ==========================================" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] STARTING DAILY DBT CRON RUN" | tee -a "${LOG_FILE}"

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

export DBT_PG_HOST="${DBT_PG_HOST:-${PG_HOST:-localhost}}"
export DBT_PG_PORT="${DBT_PG_PORT:-${PG_PORT:-5432}}"
export DBT_PG_USER="${DBT_PG_USER:-dbt_user}"
export DBT_PG_PASSWORD="${DBT_PG_PASSWORD:-${PG_PASSWORD}}"
export DBT_PG_DBNAME="${DBT_PG_DBNAME:-${PG_DBNAME:-his_db}}"

# 1. Option A: Exec inside running dbt-runner container
if docker ps --format '{{.Names}}' | grep -q "dbt-runner"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running inside active 'dbt-runner' container..." | tee -a "${LOG_FILE}"
    docker exec -t dbt-runner dbt run --profiles-dir /usr/app/dbt_project 2>&1 | tee -a "${LOG_FILE}"
    docker exec -t dbt-runner dbt compile --profiles-dir /usr/app/dbt_project --write-catalog 2>&1 | tee -a "${LOG_FILE}"

# 2. Option B: Exec inside running text2sql container
elif docker ps --format '{{.Names}}' | grep -q "text2sql"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running inside active 'text2sql' container..." | tee -a "${LOG_FILE}"
    docker exec -t text2sql dbt run --profiles-dir /usr/app/dbt_project 2>&1 | tee -a "${LOG_FILE}"
    docker exec -t text2sql dbt compile --profiles-dir /usr/app/dbt_project --write-catalog 2>&1 | tee -a "${LOG_FILE}"

# 3. Option C: Fallback standalone container
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Spawning standalone dbt container..." | tee -a "${LOG_FILE}"
    docker run --rm \
        --network host \
        -v "${REPO_DIR}/dbt_project:/usr/app/dbt_project" \
        -e DBT_PG_HOST="${DBT_PG_HOST}" \
        -e DBT_PG_PORT="${DBT_PG_PORT}" \
        -e DBT_PG_USER="${DBT_PG_USER}" \
        -e DBT_PG_PASSWORD="${DBT_PG_PASSWORD}" \
        -e DBT_PG_DBNAME="${DBT_PG_DBNAME}" \
        ghcr.io/dbt-labs/dbt-postgres:1.7.0 \
        run --project-dir /usr/app/dbt_project --profiles-dir /usr/app/dbt_project 2>&1 | tee -a "${LOG_FILE}"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] DBT CRON RUN COMPLETED SUCCESSFULLY" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ==========================================" | tee -a "${LOG_FILE}"
