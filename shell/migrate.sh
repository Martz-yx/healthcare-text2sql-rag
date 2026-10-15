#!/usr/bin/env bash

set -a
[ -f .env ] && . .env
set +a

FLYWAY_DB_HOST="${CHAINLIT_DB_HOST:-localhost}"
FLYWAY_DB_PORT="${CHAINLIT_DB_PORT:-5432}"
FLYWAY_DB_NAME="${CHAINLIT_DB_NAME:-chainlit}"
FLYWAY_DB_USER="${CHAINLIT_DB_USER:-chainlit}"
FLYWAY_DB_PW="${CHAINLIT_DB_PASSWORD:-changeme}"

JDBC_URL="jdbc:postgresql://${FLYWAY_DB_HOST}:${FLYWAY_DB_PORT}/${FLYWAY_DB_NAME}?ApplicationName=his_ai_flyway"

flywayBaseline() {
    docker run --rm --network host \
        -v "$(pwd)/flyway:/flyway/sql" \
        flyway/flyway baseline \
        -url="$JDBC_URL" -user="$FLYWAY_DB_USER" -password="$FLYWAY_DB_PW" \
        -locations=filesystem:/flyway/sql
}

flywayMigrate() {
    docker run --rm --network host \
        -v "$(pwd)/flyway:/flyway/sql" \
        flyway/flyway migrate \
        -url="$JDBC_URL" -user="$FLYWAY_DB_USER" -password="$FLYWAY_DB_PW" \
        -locations=filesystem:/flyway/sql
}

flywayInfo() {
    docker run --rm --network host \
        -v "$(pwd)/flyway:/flyway/sql" \
        flyway/flyway info \
        -url="$JDBC_URL" -user="$FLYWAY_DB_USER" -password="$FLYWAY_DB_PW" \
        -locations=filesystem:/flyway/sql
}

if [[ $# -eq 0 ]] ; then
    echo 'Usage: bash shell/migrate.sh <command>
    info      — show migration status
    baseline  — set baseline for existing database
    migrate   — run pending migrations'

elif [[ $1 == info ]]; then
    flywayInfo

elif [[ $1 == baseline ]]; then
    flywayBaseline

elif [[ $1 == migrate ]]; then
    flywayMigrate

fi

unset $(grep -v '^#' .env | sed -E 's/(.*)=.*/\1/' | xargs) 2>/dev/null
