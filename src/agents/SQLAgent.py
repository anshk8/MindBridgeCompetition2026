"""
SQL Generator Agent

Uses Chain-of-Thought reasoning and Dynamic Few-Shot Learning
to generate accurate SQL queries from natural language.

ReAct tool-use (max 2 rounds):
    Uses Ollama's native tool-calling interface. The model receives the
    same system + user prompt as always, plus a tools= list. If the model
    decides to call a tool, the result is appended and the loop continues.
    After the loop a final structured call with format=SQLResult schema
    produces the validated result — identical to the original single call.
"""

import os
import numpy as np
from typing import List, Optional
from dataclasses import dataclass
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


# Format of the few-shot examples that will help the LLM
@dataclass
class FewShotExample:
    question: str
    sql: str
    explanation: str = ""
    embedding: Optional[np.ndarray] = None


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
        examples = [
            FewShotExample(
                question="How many customers are there?",
                sql="SELECT COUNT(*) FROM customers",
                explanation="Simple COUNT aggregation on single table"
            ),
            FewShotExample(
                question="Show me all brands",
                sql="SELECT brand_id, brand_name FROM brands",
                explanation="Simple SELECT all columns from single table"
            ),
            FewShotExample(
                question="List all product categories",
                sql="SELECT category_id, category_name FROM categories",
                explanation="Simple SELECT from single table"
            ),
            FewShotExample(
                question="What are the top 5 most expensive products?",
                sql="SELECT product_name, list_price FROM products ORDER BY list_price DESC LIMIT 5",
                explanation="SELECT with ORDER BY and LIMIT"
            ),
            FewShotExample(
                question="Find customers in New York",
                sql="SELECT first_name, last_name, city, state FROM customers WHERE state = 'NY'",
                explanation="SELECT with WHERE clause for filtering"
            ),
            FewShotExample(
                question="Show me customer names with their order details",
                sql="SELECT c.first_name, c.last_name, o.order_id, o.order_date FROM customers c INNER JOIN orders o ON c.customer_id = o.customer_id",
                explanation="Two-table JOIN with column selection"
            ),
            FewShotExample(
                question="What is the average product price?",
                sql="SELECT AVG(list_price) FROM products",
                explanation="Simple aggregation function (AVG)"
            ),
            FewShotExample(
                question="How many products are in each category?",
                sql="SELECT c.category_name, COUNT(p.product_id) FROM categories c LEFT JOIN products p ON c.category_id = p.category_id GROUP BY c.category_name",
                explanation="JOIN with GROUP BY aggregation"
            ),
            FewShotExample(
                question="Which stores have the most inventory?",
                sql="SELECT s.store_name, SUM(st.quantity) as total_inventory FROM stores s JOIN stocks st ON s.store_id = st.store_id GROUP BY s.store_id, s.store_name ORDER BY total_inventory DESC",
                explanation="Multi-table JOIN with GROUP BY and ORDER BY"
            ),
            FewShotExample(
                question="Find customers who have never placed an order",
                sql="SELECT first_name, last_name, email FROM customers WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders)",
                explanation="Subquery with NOT IN for exclusion"
            ),
            FewShotExample(
                question="List all products and their available stock quantities by store",
                sql="SELECT p.product_name, s.store_name, st.quantity FROM products p JOIN stocks st ON p.product_id = st.product_id JOIN stores s ON st.store_id = s.store_id",
                explanation="Three-table JOIN"
            ),
            FewShotExample(
                question="What is the total revenue by brand?",
                sql="SELECT b.brand_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as total_revenue FROM brands b JOIN products p ON b.brand_id = p.brand_id JOIN order_items oi ON p.product_id = oi.product_id GROUP BY b.brand_name ORDER BY total_revenue DESC",
                explanation="Complex multi-table JOIN with calculated aggregation"),
            FewShotExample(
                question="What is the total value of order 1?",
                sql="SELECT o.order_id, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as order_total FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.order_id = 1 GROUP BY o.order_id",
                explanation="Order totals must be calculated from order_items: quantity * list_price * (1 - discount)"
            ),
            FewShotExample(
                question="Show customers with their total spending",
                sql="SELECT c.first_name, c.last_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as total_spent FROM customers c JOIN orders o ON c.customer_id = o.customer_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY c.customer_id, c.first_name, c.last_name",
                explanation="Customer spending requires joining through orders to order_items and calculating totals"
            ),
            FewShotExample(
                question="What is the average order value?",
                sql="SELECT AVG(order_total) FROM (SELECT o.order_id, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as order_total FROM orders o JOIN order_items oi ON o.order_id = oi.order_id GROUP BY o.order_id)",
                explanation="Average order value requires subquery to first calculate each order's total"
            ),

            FewShotExample(
                question="Show orders from March 2017",
                sql="SELECT order_id, customer_id, order_date FROM orders WHERE order_date >= '2017-03-01' AND order_date < '2017-04-01'",
                explanation="Date filtering using comparison operators or BETWEEN"
            ),
            FewShotExample(
                question="Which store has the highest total revenue?",
                sql="SELECT s.store_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS total_revenue FROM stores s JOIN orders o ON s.store_id = o.store_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY s.store_id, s.store_name ORDER BY total_revenue DESC LIMIT 1",
                explanation="Store revenue must go through orders not stocks. stocks is inventory only. Correct path: stores -> orders -> order_items"
            ),
            FewShotExample(
                question="Show total revenue per store",
                sql="SELECT s.store_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS total_revenue FROM stores s JOIN orders o ON s.store_id = o.store_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY s.store_id, s.store_name ORDER BY total_revenue DESC",
                explanation="Store revenue must go through orders not stocks. stocks is inventory only. Correct path: stores -> orders -> order_items"
            ),
        ]

        # Compute embeddings for all examples (will be used to match similar examples for queries)
        questions = [ex.question for ex in examples]
        embeddings = self.embedder.encode(questions, convert_to_numpy=True)

        for i, example in enumerate(examples):
            example.embedding = embeddings[i]

        return examples

    def findSimilarQueryExamples(self, question: str, topK: int = 3) -> List[FewShotExample]:
        """Retrieve most similar few-shot examples using semantic similarity"""
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
        Generate SQL using CoT reasoning, Few-Shot examples, and native ReAct tool-use.

        Flow:
          1. Build the same system + user prompt as the original single-shot call.
          2. Tool-use loop (max 2 rounds): call the LLM with tools=self.getTools().
             If the model calls a tool → execute it, append result, loop again.
             If no tool_calls in the response → exit the loop early.
          3. One final structured call with format=SQLResult schema (no tools) —
             identical to the original single call, but the conversation now
             contains any tool observations the model gathered.

        Returns:
            SQLResult with .sql, .intent, and .clarification_question fields.
        """
        print(f"\nGenerating Query for: {question}")

        # Step 1: Retrieve similar examples
        similarExamples = self.findSimilarQueryExamples(question, topK=3)

        # Step 2: Build contexts
        schemaContext = self.schemaContext
        fewShotContext = buildFewShotContext(similarExamples)

        #Prompts needed for generation
        systemPrompt = buildSystemPrompt()
        userPrompt   = buildUserPrompt(question, schemaContext, fewShotContext)

        messages = [
            {'role': 'system', 'content': systemPrompt},
            {'role': 'user',   'content': userPrompt},
        ]

        # ReAct tool-use loop (max 2 rounds), provides any information needed with tool calls
        for round_idx in range(2):
            print(f"🤖 ReAct round {round_idx} — calling {self.model}...")
            response = self.ollamaClient.chat(
                model=self.model,
                messages=messages,
                tools=getTools(),
                options={'temperature': temperature},
            )

            tool_calls = response['message'].get('tool_calls') or []
            if not tool_calls:
                # Model chose not to call any tool — exit loop
                break

            # Append the assistant's tool-call message
            messages.append(response['message'])

            # Execute each tool and feed results back
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
        print(f"✅ Generated SQL: {result.sql}")
        return result



