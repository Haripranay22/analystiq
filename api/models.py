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


class HealthResponse(BaseModel):
    status: str
    agent: str
    database: str
