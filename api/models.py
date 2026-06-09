"""
Phase 3 — API Request / Response Models

Pydantic models define the contract between the FastAPI backend and any client
(Streamlit UI, curl, Postman). Explicit models give us automatic validation,
serialization, and OpenAPI docs for free.
"""

from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=5,
        description="Plain English question to answer against the fintech database.",
        examples=["How many customers have a credit score above 700?"],
    )


class QueryResponse(BaseModel):
    question: str = Field(description="The original question from the request.")
    sql: str = Field(description="The SQL query generated and executed by the agent.")
    result: str = Field(description="Raw query results as a JSON string.")
    explanation: str = Field(description="Plain English interpretation of the results.")
    retry_count: int = Field(
        default=0,
        description="Number of self-correction attempts made (0 = first try succeeded).",
    )
    error: str = Field(
        default="",
        description="Last SQL error message, if any. Empty string on success.",
    )
    elapsed_ms: int = Field(
        default=0,
        description="Total wall-clock time for the agent run in milliseconds.",
    )


class HealthResponse(BaseModel):
    status: str
    agent: str
    database: str


class SchemaColumn(BaseModel):
    name: str
    type: str
    nullable: bool
    is_pk: bool = False


class SchemaTable(BaseModel):
    name: str
    columns: list[SchemaColumn]


class SchemaResponse(BaseModel):
    tables: list[SchemaTable]


class ExecuteRequest(BaseModel):
    sql: str = Field(..., min_length=1, description="Raw SQL to execute (SELECT only).")


class ExecuteResponse(BaseModel):
    result: str = Field(description="Query results as a JSON string.")
    row_count: int
    elapsed_ms: int
    error: str = Field(default="")


class SuggestionsRequest(BaseModel):
    question: str
    sql: str
    result_preview: str = Field(description="First few rows of the result as a JSON string.")


class SuggestionsResponse(BaseModel):
    suggestions: list[str] = Field(description="3 follow-up question suggestions.")
