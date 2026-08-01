"""Aggregate OASIS SQLite records without exposing content or identities."""

from __future__ import annotations

import sqlite3
from typing import Any


ACTION_TABLES = ("post", "like", "dislike", "comment")


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return bool(
        connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name=?",
            (table,),
        ).fetchone()[0]
    )


def _table_count(connection: sqlite3.Connection, table: str) -> int:
    if not _table_exists(connection, table):
        return 0
    return int(
        connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    )


def _participating_actor_count(connection: sqlite3.Connection) -> int:
    """Count content actors, excluding signup and recommendation traces."""

    available = [
        table for table in ACTION_TABLES if _table_exists(connection, table)
    ]
    if not available:
        return 0
    union = " UNION ".join(
        f'SELECT user_id FROM "{table}" WHERE user_id IS NOT NULL'
        for table in available
    )
    return int(
        connection.execute(
            f"SELECT COUNT(DISTINCT user_id) FROM ({union})"
        ).fetchone()[0]
    )


def aggregate_oasis_sqlite(
    connection: sqlite3.Connection,
) -> dict[str, Any]:
    """Return aggregate-only metrics from one ephemeral OASIS database."""

    likes = _table_count(connection, "like")
    dislikes = _table_count(connection, "dislike")
    comments = _table_count(connection, "comment")
    return {
        "posts": _table_count(connection, "post"),
        "recommendation_records": _table_count(connection, "rec"),
        "interactions": likes + dislikes + comments,
        "participants": _participating_actor_count(connection),
        "likes": likes,
        "dislikes": dislikes,
        "comments": comments,
        "trace_records": _table_count(connection, "trace"),
    }
