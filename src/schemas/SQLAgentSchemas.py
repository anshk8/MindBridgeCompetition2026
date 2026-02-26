"""
SQLAgentSchemas.py

Pydantic models for structured LLM outputs used by SQLAgent.
Passed to ollama via format=Model.model_json_schema() to guarantee
well-formed responses without any regex parsing.
"""

from pydantic import BaseModel, Field


class SQLResult(BaseModel):
    """Structured output for the SQL generator."""
    reasoning: str = Field(
        description="Step-by-step Chain-of-Thought reasoning used to arrive at the SQL query"
    )
    sql: str = Field(
        description="The final SQL SELECT query. No markdown, no explanation — just the SQL."
    )
