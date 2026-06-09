"""
ui/api_client.py — Thin HTTP client for the AnalystIQ FastAPI backend.

All API calls from the UI go through this module.
When the frontend is later rebuilt in Next.js, this file is the only
thing that changes — the rest of the UI logic stays the same.

Base URL is read from the environment:
  - LOCAL:  API_URL=http://127.0.0.1:8000  (set in .env)
  - CLOUD:  API_URL set in Streamlit secrets dashboard
  - DEFAULT: http://127.0.0.1:8000
"""

import os
from typing import Any

import requests

# Read from env / Streamlit secrets (secrets are loaded into os.environ
# by the env-setup block at the top of app.py before this module is used)
_BASE = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
_TIMEOUT = 120  # seconds — agent can take a while on complex queries


class APIError(Exception):
    """Raised when the backend returns a non-2xx response."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API {status_code}: {detail}")


def _post(path: str, payload: dict) -> dict:
    try:
        resp = requests.post(f"{_BASE}{path}", json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        raise APIError(0, "Cannot reach the API. Is uvicorn running?")
    except requests.exceptions.HTTPError as e:
        detail = e.response.json().get("detail", str(e)) if e.response else str(e)
        raise APIError(e.response.status_code if e.response else 0, detail)


def _get(path: str) -> dict:
    try:
        resp = requests.get(f"{_BASE}{path}", timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        raise APIError(0, "Cannot reach the API. Is uvicorn running?")
    except requests.exceptions.HTTPError as e:
        detail = e.response.json().get("detail", str(e)) if e.response else str(e)
        raise APIError(e.response.status_code if e.response else 0, detail)


# ── Public interface ──────────────────────────────────────────────────────────

def health() -> dict[str, str]:
    """GET /health — returns {status, agent, database}."""
    return _get("/health")


def query(question: str) -> dict[str, Any]:
    """
    POST /query — runs the full agent pipeline.
    Returns: {question, sql, result, explanation, retry_count, error, elapsed_ms}
    """
    return _post("/query", {"question": question})


def get_schema() -> dict[str, Any]:
    """GET /schema — returns {tables: [{name, columns: [{name, type, nullable, is_pk}]}]}."""
    return _get("/schema")


def execute_sql(sql: str) -> dict[str, Any]:
    """
    POST /execute — runs raw SELECT SQL (edit & re-run feature).
    Returns: {result, row_count, elapsed_ms, error}
    """
    return _post("/execute", {"sql": sql})


def get_suggestions(question: str, sql: str, result_preview: str) -> list[str]:
    """
    POST /suggestions — returns 3 follow-up question strings.
    Never raises — returns empty list on failure so UI degrades gracefully.
    """
    try:
        data = _post("/suggestions", {
            "question": question,
            "sql": sql,
            "result_preview": result_preview,
        })
        return data.get("suggestions", [])
    except APIError:
        return []
