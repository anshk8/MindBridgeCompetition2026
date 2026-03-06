#State.py: Defines the shared state structure that goes through the LangGraph pipeline.

from typing import Literal
from typing_extensions import TypedDict, NotRequired
from src.schemas.ValidatorAgentSchemas import ValidationResult

#The shared state that flows through the LangGraph pipeline.
class SQLGenerationState(TypedDict):
    """

    Set at entry (required):
        question              — the natural language question
        schemaContext         — pre-built schema string (computed once in QueryWriter)
        multiConversational   — whether to route on intent (clarify / reject irrelevant)

    Set by generateSqlNode:
        sql                   — the generated SQL string
        queryIntent           — "Clear" | "Ambiguous" | "Irrelevant"
        clarificationQuestion — follow-up question if intent is Ambiguous

    Set by kCandidatesNode:
        sql                   — best selected SQL string
        validation            — full validation result dict from ValidatorAgent

    Set at the final step of each path:
        finalSql        — cleaned SQL ready to return to the competition evaluator
    """

    # ── Entry fields (required) ────────────────────────────────────── #
    question: str
    schemaContext: str
    multiConversational: bool

    # ── After generation / validation ─────────────────────────────── #
    sql: NotRequired[str]
    queryIntent: NotRequired[Literal['Clear', 'Ambiguous', 'Irrelevant']]
    clarificationQuestion: NotRequired[str]
    validation: NotRequired[ValidationResult]
    finalSql: NotRequired[str]
