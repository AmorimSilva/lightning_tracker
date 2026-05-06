from __future__ import annotations

import gzip
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote
from typing import Any, Iterable

import pandas as pd

try:
    import pg8000.dbapi as pgdb
except Exception:  # pragma: no cover - optional at import time
    pgdb = None


def get_postgres_dsn() -> str | None:
    dsn = os.environ.get("LIGHTNING_TRACKER_PG_DSN", "").strip()
    return dsn or None


def _connect(dsn: str):
    if pgdb is None:
        raise RuntimeError("pg8000 não está disponível")
    return pgdb.connect(**_dsn_kwargs(dsn))


def _dsn_kwargs(dsn: str) -> dict[str, Any]:
    text = (dsn or "").strip()
    if not text:
        raise ValueError("DSN vazio")

    if "://" in text:
        parsed = urlparse(text)
        return {
            "host": parsed.hostname,
            "port": parsed.port,
            "database": parsed.path.lstrip("/") or None,
            "user": unquote(parsed.username) if parsed.username else None,
            "password": unquote(parsed.password) if parsed.password else None,
        }

    parts: dict[str, Any] = {}
    for chunk in text.split():
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        parts[key.strip()] = value.strip()
    return {
        "host": parts.get("host"),
        "port": int(parts["port"]) if parts.get("port") else None,
        "database": parts.get("dbname") or parts.get("database"),
        "user": parts.get("user"),
        "password": parts.get("password"),
    }


def load_points_from_postgres(
    *,
    dsn: str,
    kind: str,
    start_utc: datetime,
    end_utc: datetime,
) -> pd.DataFrame:
    if pgdb is None:
        return pd.DataFrame(columns=["time", "lat", "lon"])

    kind = kind.lower().strip()
    if kind not in {"flash", "event"}:
        raise ValueError("kind must be 'flash' or 'event'")

    query = """
        select event_time, latitude, longitude
        from lightning_events
        where kind = %s
          and event_time >= %s
          and event_time <= %s
        order by event_time asc
    """
    with _connect(dsn) as conn:
        cur = conn.cursor()
        try:
            cur.execute(query, (kind, start_utc, end_utc))
            rows = cur.fetchall()
        finally:
            cur.close()

    if not rows:
        return pd.DataFrame(columns=["time", "lat", "lon"])

    df = pd.DataFrame(rows, columns=["time", "latitude", "longitude"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.rename(columns={"latitude": "lat", "longitude": "lon"})


def store_daily_table_in_postgres(
    *,
    dsn: str,
    taker_id: int,
    taker_name: str,
    date: datetime,
    csv_text: str,
    metadata: dict[str, Any],
) -> None:
    if pgdb is None:
        return

    csv_blob = gzip.compress(csv_text.encode("utf-8"))
    with _connect(dsn) as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                insert into daily_tables
                  (taker_id, taker_name, date, csv_blob, csv_text, metadata, filesize)
                values (%s, %s, %s, %s, %s, %s, %s)
                on conflict (taker_id, date)
                do update set
                    taker_name = excluded.taker_name,
                    csv_blob = excluded.csv_blob,
                    csv_text = excluded.csv_text,
                    metadata = excluded.metadata,
                    filesize = excluded.filesize,
                    generated_at = now()
                """,
                (
                    taker_id,
                    taker_name,
                    date.date(),
                    csv_blob,
                    csv_text,
                    json.dumps(metadata),
                    len(csv_text.encode("utf-8")),
                ),
            )
        finally:
            cur.close()
            conn.commit()


def load_daily_tables(
    *,
    dsn: str,
    taker_name: str,
    limit: int,
) -> list[dict[str, Any]]:
    if pgdb is None:
        return []

    query = """
        select id, taker_id, taker_name, date, generated_at, csv_text, metadata, filesize
        from daily_tables
        where taker_name = %s
        order by generated_at desc
        limit %s
    """
    with _connect(dsn) as conn:
        cur = conn.cursor()
        try:
            cur.execute(query, (taker_name, max(1, limit)))
            rows = cur.fetchall()
        finally:
            cur.close()

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append({
            "id": row[0],
            "taker_id": row[1],
            "taker_name": row[2],
            "date": row[3],
            "generated_at": row[4],
            "csv_text": row[5],
            "metadata": row[6],
            "filesize": row[7],
        })
    return result
