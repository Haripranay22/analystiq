"""
Phase 3 — FastAPI Backend

Wraps the LangGraph agent behind a clean REST API.
Two endpoints:
  GET  /health  — confirms the API and DB are reachable
  POST /query   — runs the agent and returns SQL + result + explanation
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text

from agent.graph import graph
from api.models import HealthResponse, QueryResponse, QuestionRequest

load_dotenv()

app = FastAPI(
    title="AnalystIQ API",
    description="Ask plain English questions about your fintech data. Get back SQL, results, and explanations.",
    version="0.3.0",
)


def _check_db() -> str:
    """Returns 'ok' or an error string — used by /health."""
    try:
        engine = create_engine(os.getenv("DATABASE_URL", ""))
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as e:
        return str(e)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    """
    Liveness check. Confirms the API is running and PostgreSQL is reachable.
    Use this before running queries to catch misconfigured env vars early.
    """
    db_status = _check_db()
    return HealthResponse(
        status="ok",
        agent="langgraph",
        database=db_status,
    )


@app.post("/query", response_model=QueryResponse, tags=["agent"])
def query(request: QuestionRequest):
    """
    Runs the LangGraph agent against the question.

    The agent:
    1. Loads the live database schema
    2. Generates SQL from the question
    3. Executes the SQL (with up to 3 self-correction retries on error)
    4. Returns a plain English explanation of the results
    """
    initial_state = {
        "question": request.question,
        "schema": "",
        "sql": "",
        "result": "",
        "error": "",
        "explanation": "",
        "retry_count": 0,
    }

    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent failed: {e}") from e

    return QueryResponse(
        question=final_state["question"],
        sql=final_state.get("sql", ""),
        result=final_state.get("result", ""),
        explanation=final_state.get("explanation", ""),
        retry_count=final_state.get("retry_count", 0),
        error=final_state.get("error", ""),
    )
