#!/bin/sh
set -eu

alembic upgrade head

if [ "${SEED_DEMO:-false}" = "true" ]; then
  python -m app.db.seed || true
fi

exec "$@"
