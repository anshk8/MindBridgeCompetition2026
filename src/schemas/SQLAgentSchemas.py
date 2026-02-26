"""
SQLAgentSchemas.py

Pydantic models for structured LLM outputs used by SQLAgent.
Passed to ollama via format=Model.model_json_schema() to guarantee
well-formed responses without any regex parsing.
"""

from enum import Enum
from pydantic import BaseModel, Field, model_validator


class QueryIntent(str, Enum):
    """Intent classification of the user's question."""
    CLEAR      = "Clear"       # Directly answerable from the schema
    AMBIGUOUS  = "Ambiguous"   # Schema-related but contains a vague term
    IRRELEVANT = "Irrelevant"  # No connection to the bike store database


class SQLResult(BaseModel):
    """Structured output for the SQL generator."""
    reasoning: str = Field(
        description="Step-by-step Chain-of-Thought reasoning used to arrive at the SQL query"
    )
    intent: QueryIntent = Field(
        description=(
            "Clear: the question is unambiguous and answerable from the schema. "
            "Ambiguous: the question relates to the database but contains a vague term "
            "(e.g. 'best', 'recent', 'top') that could produce multiple different queries. "
            "Irrelevant: the question has no connection to the bike store database whatsoever."
        )
    )
    clarification_question: str = Field(
        default="",
        description=(
            "If intent is Ambiguous, a short direct question to ask the user to resolve "
            "the vagueness (e.g. 'What do you mean by best — highest revenue, most items, "
            "or fastest delivery?'). Empty string for Clear or Irrelevant."
        )
    )
    sql: str = Field(
        description=(
            "The final SQL SELECT query. No markdown, no explanation — just the raw SQL. "
            "If intent is Irrelevant, set to empty string. "
            "If intent is Ambiguous, generate a best-effort SQL using the most likely interpretation."
        )
    )
    @model_validator(mode='after')
    def clarification_required_when_ambiguous(self) -> 'SQLResult':
        """
        When intent is Ambiguous the clarification_question MUST be non-empty.
        If the LLM left it blank, attempt to extract it from the reasoning text;
        otherwise fall back to a generic prompt so the node always has something
        meaningful to show the user.
        """
        if self.intent == QueryIntent.AMBIGUOUS and not self.clarification_question.strip():
            # Try to pull a question out of the reasoning (the LLM often writes it there)
            for line in self.reasoning.splitlines():
                line = line.strip()
                if '?' in line and len(line) > 10:
                    self.clarification_question = line.lstrip('- ').strip()
                    break
            # Final fallback
            if not self.clarification_question.strip():
                self.clarification_question = (
                    'Could you clarify what you mean? '
                    '(e.g. specify a metric like revenue, count, or date range)'
                )
        return self