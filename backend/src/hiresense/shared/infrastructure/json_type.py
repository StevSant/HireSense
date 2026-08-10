from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# Cross-dialect JSON column type: renders JSONB on PostgreSQL (matching the
# columns created by the original migrations) while falling back to plain JSON
# on other dialects (e.g. the SQLite-backed test harness). Use this for columns
# whose live Postgres type is JSONB so the ORM metadata matches the DB.
JSONB_OR_JSON = JSON().with_variant(JSONB(), "postgresql")
