"""
ValidatorAgentSchemas.py

Pydantic models for structured LLM outputs used by ValidatorAgent.
Passed to ollama via format=Model.model_json_schema() to guarantee
well-formed responses without any regex parsing.
"""

from pydantic import BaseModel, Field
from typing import Optional
from typing_extensions import TypedDict, NotRequired


class ValidationResult(TypedDict):
    """
    The structured result returned by ValidatorAgent.validateSQL().
    Used as the type for the 'validation' field in SQLGenerationState
    and as the argument type for scoreCandidate().
    """
    approved:       bool           # True only if semantic review passed
    sql:            str            # final SQL (possibly corrected)
    exec_fixes:     int            # how many execution fixes were needed
    semantic_fixes: int            # how many semantic fixes were needed
    execution_ok:   bool           # does the final SQL execute?
    row_count:      int            # rows returned by the final SQL
    sample_result:  NotRequired[Optional[str]]  # first row as string, or None
    issues:         list[str]      # collected warnings / errors


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
