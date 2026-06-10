"""
ui/db.py — Chat persistence layer.

Reads/writes chat_threads and chat_messages directly via SQLAlchemy.
The UI calls these functions; nothing else in the UI touches the DB directly.

Column notes:
  - query_sql (not 'sql' — sql is a reserved word in PostgreSQL)
  - result_json capped at 500 rows before storage to prevent DB bloat
"""

import json
import os

from sqlalchemy import create_engine, text

MAX_STORED_ROWS = 500   # cap result_json before writing to DB
MAX_THREADS_SHOWN = 10  # sidebar pagination cap

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL", "")
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def _cap_result_json(result_json: str) -> str:
    """Truncate result JSON to MAX_STORED_ROWS rows before storing."""
    try:
        rows = json.loads(result_json or "[]")
        if len(rows) > MAX_STORED_ROWS:
            rows = rows[:MAX_STORED_ROWS]
        return json.dumps(rows)
    except Exception:
        return result_json


# ── Threads ───────────────────────────────────────────────────────────────────

def list_threads(limit: int = MAX_THREADS_SHOWN) -> list[dict]:
    """Return most recently updated threads, capped at limit."""
    with _get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT id, title, updated_at FROM chat_threads "
            "ORDER BY updated_at DESC LIMIT :limit"
        ), {"limit": limit}).fetchall()
    return [{"id": r[0], "title": r[1], "updated_at": r[2]} for r in rows]


def count_threads() -> int:
    with _get_engine().connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM chat_threads")).scalar() or 0


def create_thread(title: str = "New chat") -> int:
    """Create a new thread and return its id."""
    with _get_engine().begin() as conn:
        result = conn.execute(
            text("INSERT INTO chat_threads (title) VALUES (:title) RETURNING id"),
            {"title": title},
        )
        return result.fetchone()[0]


def rename_thread(thread_id: int, title: str) -> None:
    with _get_engine().begin() as conn:
        conn.execute(
            text("UPDATE chat_threads SET title=:title, updated_at=NOW() WHERE id=:id"),
            {"title": title, "id": thread_id},
        )


def delete_thread(thread_id: int) -> None:
    with _get_engine().begin() as conn:
        conn.execute(text("DELETE FROM chat_threads WHERE id=:id"), {"id": thread_id})


def delete_empty_threads() -> int:
    """Delete threads that have no messages. Returns count deleted."""
    with _get_engine().begin() as conn:
        result = conn.execute(text("""
            DELETE FROM chat_threads
            WHERE id NOT IN (SELECT DISTINCT thread_id FROM chat_messages)
            RETURNING id
        """))
        return len(result.fetchall())


def touch_thread(thread_id: int) -> None:
    with _get_engine().begin() as conn:
        conn.execute(
            text("UPDATE chat_threads SET updated_at=NOW() WHERE id=:id"),
            {"id": thread_id},
        )


# ── Messages ──────────────────────────────────────────────────────────────────

def get_messages(thread_id: int) -> list[dict]:
    """Return all messages in a thread in chronological order."""
    with _get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT id, role, question, query_sql, result_json, explanation,
                   elapsed_ms, error, created_at
            FROM chat_messages
            WHERE thread_id = :thread_id
            ORDER BY created_at ASC
        """), {"thread_id": thread_id}).fetchall()
    return [
        {
            "id": r[0], "role": r[1], "question": r[2],
            "sql": r[3], "result_json": r[4], "explanation": r[5],
            "elapsed_ms": r[6], "error": r[7], "created_at": r[8],
        }
        for r in rows
    ]


def save_user_message(thread_id: int, question: str) -> int:
    with _get_engine().begin() as conn:
        result = conn.execute(text("""
            INSERT INTO chat_messages (thread_id, role, question)
            VALUES (:thread_id, 'user', :question)
            RETURNING id
        """), {"thread_id": thread_id, "question": question})
        return result.fetchone()[0]


def save_assistant_message(
    thread_id: int,
    question: str,
    sql: str,
    result_json: str,
    explanation: str,
    elapsed_ms: int,
    error: str,
) -> int:
    """Persist an assistant turn. Caps result_json at 500 rows before storing."""
    capped_json = _cap_result_json(result_json)
    with _get_engine().begin() as conn:
        result = conn.execute(text("""
            INSERT INTO chat_messages
                (thread_id, role, question, query_sql, result_json,
                 explanation, elapsed_ms, error)
            VALUES
                (:thread_id, 'assistant', :question, :query_sql, :result_json,
                 :explanation, :elapsed_ms, :error)
            RETURNING id
        """), {
            "thread_id": thread_id, "question": question, "query_sql": sql,
            "result_json": capped_json, "explanation": explanation,
            "elapsed_ms": elapsed_ms, "error": error,
        })
        mid = result.fetchone()[0]
    touch_thread(thread_id)
    return mid
