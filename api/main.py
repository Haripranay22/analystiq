"""
FastAPI Backend — AnalystIQ

Endpoints:
  GET  /health        — liveness + DB check
  POST /query         — run LangGraph agent (SQL gen + execute + explain)
  GET  /schema        — live DB schema (tables + columns) for sidebar browser
  POST /execute       — run raw SELECT SQL (edit & re-run feature)
  POST /suggestions   — LLM-generated follow-up question suggestions
"""

import json
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine, inspect, text

from agent.graph import graph
from api.models import (
    ExecuteRequest,
    ExecuteResponse,
    HealthResponse,
    QueryResponse,
    QuestionRequest,
    SchemaColumn,
    SchemaResponse,
    SchemaTable,
    SuggestionsRequest,
    SuggestionsResponse,
)

load_dotenv()

app = FastAPI(
    title="AnalystIQ API",
    description="Ask plain English questions about your fintech data.",
    version="0.4.0",
)

# One engine shared across requests — SQLAlchemy pools connections internally
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL not set")
        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def _check_db() -> str:
    try:
        with _get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as e:
        return str(e)


# ── /health ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    """Liveness check — confirms API is running and PostgreSQL is reachable."""
    return HealthResponse(status="ok", agent="langgraph", database=_check_db())


# ── /query ────────────────────────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse, tags=["agent"])
def query(request: QuestionRequest):
    """
    Runs the full LangGraph agent pipeline:
    schema load → SQL generation → execution (with up to 3 self-correction
    retries) → plain English explanation.
    Returns elapsed_ms for the metadata strip in the UI.
    """
    t0 = time.monotonic()
    try:
        final_state = graph.invoke({
            "question": request.question,
            "schema": "", "sql": "", "result": "",
            "error": "", "explanation": "", "retry_count": 0,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent failed: {e}") from e

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    return QueryResponse(
        question=final_state["question"],
        sql=final_state.get("sql", ""),
        result=final_state.get("result", ""),
        explanation=final_state.get("explanation", ""),
        retry_count=final_state.get("retry_count", 0),
        error=final_state.get("error", ""),
        elapsed_ms=elapsed_ms,
    )


# ── /schema ───────────────────────────────────────────────────────────────────

@app.get("/schema", response_model=SchemaResponse, tags=["system"])
def schema():
    """
    Returns the live database schema — table names and their columns with
    types, nullability, and PK flags. Used by the sidebar schema browser.
    """
    insp = inspect(_get_engine())
    tables = []
    for table_name in sorted(insp.get_table_names()):
        pk_cols = set(insp.get_pk_constraint(table_name).get("constrained_columns", []))
        columns = [
            SchemaColumn(
                name=col["name"],
                type=str(col["type"]),
                nullable=col.get("nullable", True),
                is_pk=col["name"] in pk_cols,
            )
            for col in insp.get_columns(table_name)
        ]
        tables.append(SchemaTable(name=table_name, columns=columns))
    return SchemaResponse(tables=tables)


# ── /execute ──────────────────────────────────────────────────────────────────

_FORBIDDEN = {"insert", "update", "delete", "drop", "truncate", "alter",
              "create", "replace", "grant", "revoke", "execute", "call"}


def _is_safe_sql(sql: str) -> bool:
    """
    Lightweight read-only guard: rejects any statement that starts with or
    contains a DML/DDL keyword.  Not a substitute for a proper read-only DB
    role, but provides a clear error message in the UI.
    """
    first_word = sql.strip().split()[0].lower() if sql.strip() else ""
    if first_word in _FORBIDDEN:
        return False
    for keyword in _FORBIDDEN:
        if f" {keyword} " in f" {sql.lower()} ":
            return False
    return True


@app.post("/execute", response_model=ExecuteResponse, tags=["agent"])
def execute(request: ExecuteRequest):
    """
    Executes raw SQL submitted by the user (the 'Edit & re-run' feature).
    Rejects any non-SELECT statement with a 400 before it reaches the DB.
    Treat all input as untrusted.
    """
    if not _is_safe_sql(request.sql):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT statements are allowed. Write operations are not permitted.",
        )
    t0 = time.monotonic()
    try:
        with _get_engine().connect() as conn:
            result_proxy = conn.execute(text(request.sql))
            keys = list(result_proxy.keys())
            rows = result_proxy.fetchall()
            data = [dict(zip(keys, row)) for row in rows]
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return ExecuteResponse(
            result=json.dumps(data, default=str),
            row_count=len(data),
            elapsed_ms=elapsed_ms,
            error="",
        )
    except HTTPException:
        raise
    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return ExecuteResponse(result="[]", row_count=0, elapsed_ms=elapsed_ms, error=str(e))


# ── /suggestions ──────────────────────────────────────────────────────────────

_suggestions_llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    temperature=0.4,
    api_key=os.getenv("OPENAI_API_KEY"),
)

_SUGGESTIONS_PROMPT = """You are a helpful data analyst assistant.
Given a question the user just asked and the SQL result they received,
suggest exactly 3 natural follow-up questions they might want to ask next.
Return ONLY a JSON array of 3 strings. No preamble, no explanation.
Example: ["How does this break down by segment?", "What changed month over month?", "Which customers are outliers?"]"""


@app.post("/suggestions", response_model=SuggestionsResponse, tags=["agent"])
def suggestions(request: SuggestionsRequest):
    """
    Returns 3 LLM-generated follow-up question suggestions based on what
    the user just asked and what the results looked like.
    """
    user_msg = (
        f"Question: {request.question}\n"
        f"SQL used:\n{request.sql}\n"
        f"Result preview:\n{request.result_preview}"
    )
    try:
        response = _suggestions_llm.invoke([
            SystemMessage(content=_SUGGESTIONS_PROMPT),
            HumanMessage(content=user_msg),
        ])
        raw = response.content.strip()
        # Strip markdown code fences if the LLM wraps the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return SuggestionsResponse(suggestions=parsed[:3])
    except Exception:
        pass
    # Graceful fallback — never crash the UI over suggestions
    return SuggestionsResponse(suggestions=[
        "How does this break down by customer segment?",
        "What is the trend over the last 6 months?",
        "Which records are the top 5 by value?",
    ])
