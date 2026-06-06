"""
AgentState — the single object that flows through every node in the graph.

Every node receives the full state and returns a dict of only the fields it changes.
LangGraph merges the returned dict back into the state automatically.

Think of state as a baton passed between runners in a relay race.
"""

from typing import TypedDict


class AgentState(TypedDict):
    question: str       # user's plain English question — never changes after input
    schema: str         # database schema string — set once by load_schema node
    sql: str            # generated SQL — updated by generate_sql and correct_sql
    result: str         # query result as JSON string — set by execute_sql
    error: str          # SQL error message — set by execute_sql, cleared on success
    explanation: str    # plain English answer — set by explain_result
    retry_count: int    # how many self-correction attempts have happened
