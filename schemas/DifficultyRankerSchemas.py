"""
DifficultyRankerSchemas.py

Pydantic models for structured LLM outputs used by DifficultyRankerAgent.
Passed to ollama via format=Model.model_json_schema() to guarantee
well-formed responses without any regex parsing.
"""

from pydantic import BaseModel, Field
from enum import Enum


class Difficulty(str, Enum):
    """Difficulty level for a natural language SQL question."""
    EASY      = "Easy"
    MEDIUM    = "Medium"
    HARD      = "Hard"
    AMBIGUOUS = "Ambiguous"


class DifficultyResult(BaseModel):
    """Structured output for the difficulty ranker."""
    difficulty: Difficulty = Field(
        description=(
            "The difficulty tier of the question. "
            "Easy: single-table, basic filters/aggregations. "
            "Medium: 2-table JOINs, simple subqueries, grouped aggregations. "
            "Hard: 3+ table JOINs, nested subqueries, CTEs, window functions, "
            "complex multi-step calculations. "
            "Ambiguous: vague, contradictory, or unanswerable against the schema."
        )
    )
    reasoning: str = Field(
        description=(
            "Short step-by-step explanation of why this difficulty was chosen. "
            "Mention the number of tables needed, JOIN depth, subquery nesting, "
            "aggregation complexity, and any ambiguity signals."
        )
    )
    tables_needed: list[str] = Field(
        default_factory=list,
        description="Names of the database tables likely required to answer this question."
    )
    ambiguity_notes: str = Field(
        default="",
        description=(
            "If difficulty is Ambiguous, describe what is unclear or missing. "
            "Empty string for non-ambiguous queries."
        )
    )
