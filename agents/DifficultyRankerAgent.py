"""
DifficultyRankerAgent.py

Analyses a natural language question and classifies it into one of four
difficulty tiers based on the SQL complexity it would require:

    Easy      — single-table, basic filters / aggregations
    Medium    — 2-table JOINs, grouped aggregations, simple subqueries
    Hard      — 3+ JOINs, nested subqueries, CTEs, window functions,
                complex multi-step calculations
    Ambiguous — vague, contradictory, or unanswerable against the schema

This agent acts as the entry point in the orchestration pipeline.
Downstream agents can use the returned difficulty to decide how many
candidate queries to generate (k-candidate support, once implemented).
"""

import os
import ollama
from typing import Optional

from utils.helpers import loadSchema, buildSchemaContext
from utils.prompts import (
    buildDifficultyRankerSystemPrompt,
    buildDifficultyRankerUserPrompt,
)
from schemas.DifficultyRankerSchemas import DifficultyResult, Difficulty


class DifficultyRankerAgent:
    """
    Classifies a natural language question by SQL difficulty.

    Usage
    -----
    ranker = DifficultyRankerAgent(dbPath='bike_store.db')
    result = ranker.rank("What is the revenue breakdown by category?")
    print(result.difficulty)   # Difficulty.HARD
    print(result.reasoning)
    print(result.tables_needed)
    """

    def __init__(self, dbPath: str = 'bike_store.db', model: Optional[str] = None):
        """
        Args:
            dbPath: Path to the DuckDB database file.
            model:  Ollama model name. Falls back to OLLAMA_MODEL env var,
                    then to 'qwen2.5-coder:14b'.
        """
        self.dbPath = dbPath
        self.model  = model or os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:14b')
        self.ollamaClient = ollama.Client(
            host=os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        )

        # Load schema once; reuse for every ranking call
        self.schemaInfo    = loadSchema(dbPath)
        self.schemaContext = buildSchemaContext(self.schemaInfo)

        print(f"✅ DifficultyRankerAgent initialized (model={self.model})")

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def rank(self, question: str) -> DifficultyResult:
        """
        Classify the difficulty of a natural language SQL question.

        Args:
            question: The natural language question to analyse.

        Returns:
            DifficultyResult with fields:
                .difficulty      — Difficulty enum (Easy / Medium / Hard / Ambiguous)
                .reasoning       — Step-by-step justification
                .tables_needed   — List of table names likely required
                .ambiguity_notes — Non-empty only when difficulty == Ambiguous

        """
        print(f"\n🎯 DifficultyRankerAgent classifying: '{question}'")

        system_prompt = buildDifficultyRankerSystemPrompt()
        user_prompt   = buildDifficultyRankerUserPrompt(question, self.schemaContext)

        try:
            response = self.ollamaClient.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user',   'content': user_prompt},
                ],
                format=DifficultyResult.model_json_schema(),
            )

            result = DifficultyResult.model_validate_json(
                response['message']['content']
            )

            self.logResult(result)
            return result

        except Exception as e:
            print(f"⚠️  DifficultyRankerAgent error: {e}")
            # Fail-safe: treat unknown as Medium so the pipeline continues
            return DifficultyResult(
                difficulty=Difficulty.MEDIUM,
                reasoning=f"Ranker failed ({e}); defaulting to Medium.",
                tables_needed=[],
                ambiguity_notes="",
            )

    def rankBatch(self, questions: list[str]) -> list[DifficultyResult]:
        """
        Classify a list of questions sequentially.

        Args:
            questions: List of natural language questions.

        Returns:
            List of DifficultyResult objects in the same order.
        """
        return [self.rank(q) for q in questions]

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    #TODO Remove for actual submission
    def logResult(self, result: DifficultyResult) -> None:
        """Pretty-print the classification result."""
        icon = {
            Difficulty.EASY:      "🟢",
            Difficulty.MEDIUM:    "🟡",
            Difficulty.HARD:      "🔴",
            Difficulty.AMBIGUOUS: "⚪",
        }.get(result.difficulty, "❓")

        print(f"{icon} Difficulty : {result.difficulty.value}")
        print(f"   Tables    : {', '.join(result.tables_needed) or 'N/A'}")
        print(f"   Reasoning : {result.reasoning}")
        if result.ambiguity_notes:
            print(f"   Ambiguity : {result.ambiguity_notes}")
