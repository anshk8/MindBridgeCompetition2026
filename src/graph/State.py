from typing import Literal
from typing_extensions import TypedDict, NotRequired

#The shared state that flows through the LangGraph pipeline.
class SQLGenerationState(TypedDict):
    """

    Set at entry (required):
        question              — the natural language question
        schemaContext         — pre-built schema string (computed once in QueryWriter)
        kEnabled              — whether K-candidate mode is active
        kCount                — how many candidates to generate when enabled
        multiConversational   — whether to route on intent (clarify / reject irrelevant)

    Set by rank_node:
        difficulty      — "Easy" | "Medium" | "Hard" | "Ambiguous"
        tablesNeeded    — list of table names the ranker identified

    Set by generate_node / k_candidates_node:
        sql                   — the generated (or best selected) SQL string
        queryIntent           — "Clear" | "Ambiguous" | "Irrelevant"
        clarificationQuestion — follow-up question if intent is Ambiguous
        validation            — full validation result dict from ValidatorAgent

    Set at the final step of each path:
        finalSql        — cleaned SQL ready to return to the competition evaluator
    """

    # ── Entry fields (required) ────────────────────────────────────── #
    question: str
    schemaContext: str
    kEnabled: bool
    kCount: int
    multiConversational: bool

    # ── After rank_node ────────────────────────────────────────────── #
    difficulty: NotRequired[Literal['Easy', 'Medium', 'Hard', 'Ambiguous'] | None]
    tablesNeeded: NotRequired[list[str]]

    # ── After generation / validation ─────────────────────────────── #
    sql: NotRequired[str]
    queryIntent: NotRequired[Literal['Clear', 'Ambiguous', 'Irrelevant']]
    clarificationQuestion: NotRequired[str]
    validation: NotRequired[dict]
    finalSql: NotRequired[str]
