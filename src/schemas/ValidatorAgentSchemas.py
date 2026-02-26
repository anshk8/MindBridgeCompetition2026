"""
ValidatorAgentSchemas.py

Pydantic models for structured LLM outputs used by ValidatorAgent.
Passed to ollama via format=Model.model_json_schema() to guarantee
well-formed responses without any regex parsing.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ReviewResult(BaseModel):
    """Structured output for the SQL semantic reviewer."""
    approved: bool = Field(
        description="True if the SQL correctly answers the question, False if it should be rejected"
    )
    issues: list[str] = Field(
        default_factory=list,
        description="List of problems found with the SQL. Empty list if approved."
    )
    corrected_sql: Optional[str] = Field(
        default=None,
        description="A corrected SQL query if rejected, or null if approved."
    )

class FixResult(BaseModel):
    """Structured output for the SQL fixer."""
    sql: str = Field(
        description="The corrected SQL SELECT query. No markdown, no explanation — just the SQL."
    )
