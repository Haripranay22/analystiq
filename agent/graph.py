"""
Phase 2 — LangGraph Graph Assembly

This file wires all nodes together into a runnable graph.
Read this file last — understand each node in nodes.py first.

The graph looks like this:

    load_schema
        │
    generate_sql
        │
    execute_sql ──── success ────► explain_result ──► END
        │
        └─── error (retry < 3) ──► correct_sql
                                       │
                                   execute_sql  (loop back)
"""

from langgraph.graph import END, StateGraph

from .nodes import correct_sql, execute_sql, explain_result, generate_sql, load_schema
from .state import AgentState

MAX_RETRIES = 3


def _route_after_execution(state: AgentState) -> str:
    """
    The only decision point in the graph.

    After execute_sql runs, we check:
    - No error → go explain the result
    - Error but retries left → go self-correct and try again
    - Error and retries exhausted → go explain the failure (graceful degradation)
    """
    if not state.get("error"):
        return "explain"
    if state.get("retry_count", 0) < MAX_RETRIES:
        return "correct"
    return "explain"


def build_graph():
    workflow = StateGraph(AgentState)

    # Register all nodes
    workflow.add_node("load_schema", load_schema)
    workflow.add_node("generate_sql", generate_sql)
    workflow.add_node("execute_sql", execute_sql)
    workflow.add_node("correct_sql", correct_sql)
    workflow.add_node("explain_result", explain_result)

    # Entry point — where every invocation starts
    workflow.set_entry_point("load_schema")

    # Fixed edges — always go this direction
    workflow.add_edge("load_schema", "generate_sql")
    workflow.add_edge("generate_sql", "execute_sql")

    # Conditional edge — the routing function decides where to go
    workflow.add_conditional_edges(
        "execute_sql",
        _route_after_execution,
        {
            "explain": "explain_result",
            "correct": "correct_sql",
        },
    )

    # After self-correction, loop back to try executing again
    workflow.add_edge("correct_sql", "execute_sql")

    # Terminal edge — graph ends after explanation
    workflow.add_edge("explain_result", END)

    return workflow.compile()


# Compiled graph — import this wherever you need to run the agent
graph = build_graph()
