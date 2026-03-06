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
)
from src.schemas.SQLAgentSchemas import SQLResult, QueryIntent
from src.agents.tools.toolHelpers import getTools, executeTool
from src.utils.fewShotExamples import FewShotExample, FEW_SHOT_EXAMPLES


class SQLAgent:
    def __init__(self, dbPath: str = 'bike_store.db', model: str = None, schemaInfo: dict = None):
        # Model setup
        self.model = model or os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:14b')
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
        """
        Generate SQL with agent

        Returns:
            SQLResult with .sql, .intent, and .clarification_question fields.
        """
        print(f"\nGenerating Query for: {question}")

        #Retrieve similar examples
        similarExamples = self.findSimilarQueryExamples(question, topK=3)

        #Build contexts
        schemaContext = self.schemaContext
        fewShotContext = buildFewShotContext(similarExamples)

        #Prompts needed for generation
        systemPrompt = buildSystemPrompt()
        userPrompt   = buildUserPrompt(question, schemaContext, fewShotContext)

        messages = [
            {'role': 'system', 'content': systemPrompt},
            {'role': 'user',   'content': userPrompt},
        ]

        # ReAct structure tool-use loop which will provides any information needed with tool calls (loops twice)
        for _ in range(2):
            response = self.ollamaClient.chat(
                model=self.model,
                messages=messages,
                tools=getTools(),
                options={'temperature': temperature},
            )

            #If not tool calls happened, break early to avoid unnecessary round
            tool_calls = response['message'].get('tool_calls') or []
            if not tool_calls:
                break

            # Append the assistant's tool-call message
            messages.append(response['message'])

            # Execute each tool and give results back to LLM
            for tc in tool_calls:
                func_name = tc['function']['name']
                result_lines = executeTool(tc, db_path=self.dbPath, schema_info=self.schemaInfo)
                print(f"🔧 Tool '{func_name}' returned {len(result_lines)} item(s)")
                messages.append({
                    'role': 'tool',
                    'content': '\n'.join(result_lines),
                })

        # Final structured call to get the SQLResult (Enriched with tool observations if any)
        final_response = self.ollamaClient.chat(
            model=self.model,
            messages=messages,
            format=SQLResult.model_json_schema(),
            options={'temperature': temperature},
        )

        result = SQLResult.model_validate_json(final_response['message']['content'])
        result.sql = result.sql.rstrip(';')
        print(f"💭 Reasoning: {result.reasoning}")

        #TODO: Remove from here, should Print Validtator as this can print incorrect SQL which is useful for debugging and shows the improvement after validation step
        print(f"✅ Generated SQL: {result.sql}")
        return result



