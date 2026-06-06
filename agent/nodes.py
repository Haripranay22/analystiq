"""
Phase 2 — Agent Nodes

Each function is one node in the LangGraph graph.
Each node receives the full AgentState and returns a dict of only the fields it updates.

Node execution order:
  load_schema → generate_sql → execute_sql → [correct_sql →] explain_result
"""

import json
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine, inspect, text

from .prompts import CORRECTOR_SYSTEM_PROMPT, EXPLAINER_SYSTEM_PROMPT, SQL_SYSTEM_PROMPT
from .state import AgentState

load_dotenv()

# One LLM instance shared across all nodes — avoids re-initializing on every call
llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    temperature=0,          # deterministic output — SQL is not creative work
    api_key=os.getenv("OPENAI_API_KEY"),
)

# Module-level engine uses SQLAlchemy's built-in connection pool
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL not set in .env")
        _engine = create_engine(db_url)
    return _engine


# ─── Node 1 ───────────────────────────────────────────────────────────────────

def load_schema(state: AgentState) -> dict:
    """
    Reads the live database schema and formats it as a string for the LLM.

    Why we do this: without the real schema, the LLM hallucinates column names.
    By giving it the exact tables and columns that exist, SQL generation is grounded
    in reality. This is the key difference between a toy demo and a working product.
    """
    engine = _get_engine()
    inspector = inspect(engine)

    schema_parts = []
    for table_name in inspector.get_table_names():
        pk_cols = set(inspector.get_pk_constraint(table_name).get("constrained_columns", []))
        fk_map = {
            col: f"{fk['referred_table']}.{fk['referred_columns'][0]}"
            for fk in inspector.get_foreign_keys(table_name)
            for col in fk["constrained_columns"]
        }

        col_lines = []
        for col in inspector.get_columns(table_name):
            name = col["name"]
            col_type = str(col["type"])
            line = f"  - {name} ({col_type})"
            if name in pk_cols:
                line += " PK"
            if name in fk_map:
                line += f" → {fk_map[name]}"
            col_lines.append(line)

        schema_parts.append(f"Table: {table_name}\n" + "\n".join(col_lines))

    return {"schema": "\n\n".join(schema_parts)}


# ─── Node 2 ───────────────────────────────────────────────────────────────────

def generate_sql(state: AgentState) -> dict:
    """
    Calls the LLM to convert a plain English question into a SQL query.

    Why temperature=0: we want the most likely (deterministic) SQL, not a creative
    interpretation. Creativity in SQL leads to wrong answers.
    """
    messages = [
        SystemMessage(content=SQL_SYSTEM_PROMPT),
        HumanMessage(
            content=f"Database schema:\n{state['schema']}\n\nQuestion: {state['question']}"
        ),
    ]
    response = llm.invoke(messages)
    return {"sql": response.content.strip(), "error": ""}


# ─── Node 3 ───────────────────────────────────────────────────────────────────

def execute_sql(state: AgentState) -> dict:
    """
    Runs the SQL against PostgreSQL and captures either the result or the error.

    Why we catch all exceptions: SQL errors are expected (wrong column names,
    type mismatches, etc.). We store the error in state so the corrector node
    can fix it rather than crashing the whole agent.

    Results are stored as a JSON string so they can travel through the graph state
    and be safely serialized. `default=str` handles Decimal and datetime types
    that are common in fintech data.
    """
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            result_proxy = conn.execute(text(state["sql"]))
            keys = list(result_proxy.keys())
            rows = result_proxy.fetchall()
            data = [dict(zip(keys, row)) for row in rows]
        return {"result": json.dumps(data, default=str), "error": ""}
    except Exception as e:
        return {"result": "", "error": str(e)}


# ─── Node 4 ───────────────────────────────────────────────────────────────────

def correct_sql(state: AgentState) -> dict:
    """
    Self-correction: given the failed SQL and the error message, asks the LLM
    to fix the query.

    Why this works: the error message from PostgreSQL is specific enough
    (e.g. "column t.ammount does not exist") that the LLM can spot the typo
    and fix it without needing the original question again.
    """
    messages = [
        SystemMessage(content=CORRECTOR_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Database schema:\n{state['schema']}\n\n"
                f"Original question: {state['question']}\n\n"
                f"Failed SQL:\n{state['sql']}\n\n"
                f"Error message:\n{state['error']}"
            )
        ),
    ]
    response = llm.invoke(messages)
    return {
        "sql": response.content.strip(),
        "retry_count": state.get("retry_count", 0) + 1,
    }


# ─── Node 5 ───────────────────────────────────────────────────────────────────

def explain_result(state: AgentState) -> dict:
    """
    Translates the raw query result into a plain English insight.

    Why we limit to 10 rows: sending all 10,000 rows to the LLM wastes tokens
    and money. The first 10 rows contain enough signal for a meaningful summary.
    The full result is still available in state["result"] for the UI to display.
    """
    if state.get("error") and not state.get("result"):
        result_summary = f"Query failed after {state.get('retry_count', 0)} attempts.\nLast error: {state['error']}"
    else:
        data = json.loads(state.get("result", "[]"))
        result_summary = json.dumps(data[:10], default=str, indent=2)

    messages = [
        SystemMessage(content=EXPLAINER_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Question: {state['question']}\n\n"
                f"SQL used:\n{state['sql']}\n\n"
                f"Results (first 10 rows):\n{result_summary}"
            )
        ),
    ]
    response = llm.invoke(messages)
    return {"explanation": response.content.strip()}
