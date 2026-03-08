"""
SQL Generator Agent
- Chain of Thought reasoning + Few-Shot Learning + ReAct loop tool-use
"""

import os
import numpy as np
from typing import List
import ollama
from sentence_transformers import SentenceTransformer
from src.utils.helpers import loadSchema, buildSchemaContext
from src.utils.prompts import (
    buildSystemPrompt,
    buildUserPrompt,
    buildFewShotContext,
    buildToolSystemPrompt,
)
from src.schemas.SQLAgentSchemas import SQLResult
from src.agents.tools.toolHelpers import getTools, executeTool
from src.utils.fewShotExamples import FewShotExample, FEW_SHOT_EXAMPLES


class SQLAgent:
    def __init__(self, dbPath: str = 'bike_store.db', schemaInfo: dict = None):
        # Model setup
        self.model = os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:14b')
        # Separate model for the tool-probe phase — llama3.1:8b has better native tool-call support
        self.toolLoopModel = os.getenv('OLLAMA_REACT_MODEL', 'llama3.1:8b')
        self.ollamaClient = ollama.Client(host=os.getenv(
            'OLLAMA_HOST', 'http://localhost:11434'))

        # Store DB path but don't keep connection open
        self.dbPath = dbPath

        # Load schema using helper function (or reuse pre-loaded)
        self.schemaInfo = schemaInfo or loadSchema(dbPath)
        self.schemaContext = buildSchemaContext(self.schemaInfo)  # cached once

        # Initialize embedder and examples
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.exampleBank = self.setupFewShotExamples()

    #setup examples for embeddings
    def setupFewShotExamples(self) -> List[FewShotExample]:
        examples = list(FEW_SHOT_EXAMPLES)

        # Compute embeddings for all examples (will be used to match similar examples for queries)
        questions = [ex.question for ex in examples]
        embeddings = self.embedder.encode(questions, convert_to_numpy=True)

        for i, example in enumerate(examples):
            example.embedding = embeddings[i]

        return examples

    def findSimilarQueryExamples(self, question: str, topK: int = 3) -> List[FewShotExample]:
        """Retrieve most similar few-shot examples using cosine similarity"""
        questionEmbedding = self.embedder.encode(
            question, convert_to_numpy=True)

        similarities = []
        for example in self.exampleBank:
            similarity = np.dot(questionEmbedding, example.embedding) / (
                np.linalg.norm(questionEmbedding) *
                np.linalg.norm(example.embedding)
            )
            similarities.append((similarity, example))

        similarities.sort(key=lambda x: x[0], reverse=True)
        return [ex for _, ex in similarities[:topK]]

    def generate(self, question: str, temperature: float = 0.7) -> SQLResult:
        """Generate SQL with a focused tool-probe call then a structured SQL generation call."""
        print(f"\nGenerating Query for: {question}")

        # ── Phase 1: Tool probe ─────────────────────────────────── #
        # Separate conversation focused only on looking up named values.
        # Tool results are collected and later injected into the SQL prompt.
        ReActLoopMessages = [
            {'role': 'system', 'content': buildToolSystemPrompt()},
            {'role': 'user',   'content': question},
        ]
        toolObservations = []  # plain-text results to inject into SQL context

        print("\nRUNNING ReAct Tool Loop (if needed) and Intent classification...")
        for _ in range(2):
            probe_response = self.ollamaClient.chat(
                model=self.toolLoopModel,
                messages=ReActLoopMessages,
                tools=getTools(),
                options={'temperature': 0.0},  # deterministic for lookups
            )

            tool_calls = probe_response['message'].get('tool_calls') or []
            if not tool_calls:
                break

            ReActLoopMessages.append(probe_response['message'])

            for tc in tool_calls:
                func_name = tc['function']['name']
                result_lines = executeTool(tc, db_path=self.dbPath, schema_info=self.schemaInfo)
                result_text = '\n'.join(result_lines)
                ReActLoopMessages.append({'role': 'tool', 'content': result_text})
                toolObservations.append(f"[{func_name}] {result_text}")

        # ── Phase 2: SQL generation ───────────────────────────── #
        # Fresh conversation with schema + few-shot + any tool observations.
        similarExamples = self.findSimilarQueryExamples(question, topK=5)
        fewShotContext  = buildFewShotContext(similarExamples)

        userPrompt = buildUserPrompt(question, self.schemaContext, fewShotContext)
        if toolObservations:
            userPrompt += '\n\nVERIFIED VALUES FROM DATABASE LOOKUP:\n' + '\n'.join(toolObservations)

        sql_messages = [
            {'role': 'system', 'content': buildSystemPrompt()},
            {'role': 'user',   'content': userPrompt},
        ]

        # Structured SQL generation call — format enforced, no tools.
        final_response = self.ollamaClient.chat(
            model=self.model,
            messages=sql_messages,
            format=SQLResult.model_json_schema(),
            options={'temperature': temperature},
        )

        result = SQLResult.model_validate_json(final_response['message']['content'])
        result.sql = result.sql.rstrip(';')
        return result



