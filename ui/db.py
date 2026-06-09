"""
ui/db.py — Chat persistence layer.

Reads/writes chat_threads and chat_messages directly via SQLAlchemy.
The UI calls these functions; nothing else in the UI touches the DB directly.
"""

import os
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text

# Reuse the same DATABASE_URL the agent uses
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL", "")
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


# ── Threads ───────────────────────────────────────────────────────────────────

def list_threads() -> list[dict]:
    """Return all threads ordered by most recently updated."""
    with _get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT id, title, updated_at FROM chat_threads ORDER BY updated_at DESC"
        )).fetchall()
    return [{"id": r[0], "title": r[1], "updated_at": r[2]} for r in rows]


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


def touch_thread(thread_id: int) -> None:
    """Update updated_at so thread floats to the top of the list."""
    with _get_engine().begin() as conn:
        conn.execute(
            text("UPDATE chat_threads SET updated_at=NOW() WHERE id=:id"),
            {"id": thread_id},
        )


# ── Messages ──────────────────────────────────────────────────────────────────

def get_messages(thread_id: int) -> list[dict]:
    """Return all messages in a thread in order."""
    with _get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT id, role, question, sql, result_json, explanation,
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
    """Persist a user turn and return the message id."""
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
    """Persist an assistant turn and return the message id."""
    with _get_engine().begin() as conn:
        result = conn.execute(text("""
            INSERT INTO chat_messages
                (thread_id, role, question, sql, result_json, explanation, elapsed_ms, error)
            VALUES
                (:thread_id, 'assistant', :question, :sql, :result_json,
                 :explanation, :elapsed_ms, :error)
            RETURNING id
        """), {
            "thread_id": thread_id, "question": question, "sql": sql,
            "result_json": result_json, "explanation": explanation,
            "elapsed_ms": elapsed_ms, "error": error,
        })
        mid = result.fetchone()[0]
    touch_thread(thread_id)
    return mid
