"""
SQL Generator Agent

Uses Chain-of-Thought reasoning and Dynamic Few-Shot Learning
to generate accurate SQL queries from natural language.
"""

import os
import re
import duckdb
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import ollama
from sentence_transformers import SentenceTransformer
from langchain_community.utilities import SQLDatabase
import duckdb
from typing import List, Dict, Any
from agents.ValidatorAgent import ValidatorAgent


# Format of the few-shot examples that will help the LLM
@dataclass
class FewShotExample:
    question: str
    sql: str
    explanation: str = ""
    embedding: Optional[np.ndarray] = None


class SQLAgent:
    def __init__(self, dbPath: str = 'bike_store.db', model: str = None):
        # Model setup
        self.model = model or os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:14b')
        self.ollamaClient = ollama.Client(host=os.getenv(
            'OLLAMA_HOST', 'http://localhost:11434'))

        #DuckDB connection
        self.dbPath = dbPath
        self.duckdbConn = duckdb.connect(dbPath)

        # Load schema
        self.schemaInfo = self.loadSchema()

        # Initialize embedder and examples
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.exampleBank = self.setupFewShotExamples()

        # Lightweight reviewer/validator agent (max 2 correction attempts)
        self.reviewer = ValidatorAgent(
            conn=self.duckdbConn, model=self.model, maxCorrections=2
        )

        print(f"✅ SQL Agent initialized with {len(self.exampleBank)} examples")


    def loadSchema(self) -> Dict[str, Any]:
        """Load schema using DuckDB"""
        schemaWithSamples = {}

        try:
            # Get all table names
            tables = self.duckdbConn.execute("SHOW TABLES").fetchall()
            tableNames = [table[0] for table in tables]

            for tableName in tableNames:
                # Get column information
                columns = self.duckdbConn.execute(
                    f"DESCRIBE {tableName}").fetchall()

                columnInfo = []
                for col in columns:
                    columnInfo.append({
                        'name': col[0],
                        'type': col[1],
                        'null': col[2] if len(col) > 2 else None
                    })

                # Get sample data
                cursor = self.duckdbConn.execute(
                    f"SELECT * FROM {tableName} LIMIT 3"
                )
                rows = cursor.fetchall()
                col_names = [desc[0] for desc in cursor.description]
                samples = [dict(zip(col_names, row)) for row in rows]

                schemaWithSamples[tableName] = {
                    'columns': columnInfo,
                    'samples': samples
                }

            # print("Schema with Samples from loadSchema: ",
            #       schemaWithSamples, "\n")
            return schemaWithSamples

        except Exception as e:
            print(f"Error loading schema: {e}")
            return {}

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

    def buildSchemaContext(self) -> str:
        """Build rich schema context with sample data"""
        contextParts = []

        for tableName, tableData in self.schemaInfo.items():
            contextParts.append(f"\nTable: {tableName}")
            contextParts.append("Columns:")

            for col in tableData['columns']:
                colType = col.get('type', 'UNKNOWN')
                contextParts.append(f"  - {col['name']} ({colType})")

            if tableData['samples']:
                contextParts.append("\nSample rows:")
                colNames = [col['name'] for col in tableData['columns']]
                contextParts.append("  | " + " | ".join(colNames) + " |")

                for row in tableData['samples']:
                    rowValues = [str(row.get(col, 'NULL'))[:30]
                                 for col in colNames]
                    contextParts.append("  | " + " | ".join(rowValues) + " |")

        # print("\n".join(contextParts))
        return "\n".join(contextParts)

    def _buildFewShotContext(self, examples: List[FewShotExample]) -> str:
        """Build few-shot examples context for prompt"""
        exampleParts = []

        for i, ex in enumerate(examples, 1):
            exampleParts.append(f"Example {i}:")
            exampleParts.append(f"Question: {ex.question}")
            exampleParts.append(f"SQL: {ex.sql}")
            if ex.explanation:
                exampleParts.append(f"Explanation: {ex.explanation}")
            exampleParts.append("")

        return "\n".join(exampleParts)

    def buildCoTPrompt(self, question: str, schemaContext: str, fewShotContext: str) -> str:
        """Build Chain-of-Thought prompt that forces step-by-step reasoning"""

        prompt = f"""You are an expert SQL query generator. Given a natural language question about a database, generate a syntactically and semantically correct SQL query.

DATABASE SCHEMA:
{schemaContext}

SIMILAR EXAMPLES FOR REFERENCE:
{fewShotContext}

USER QUESTION: {question}

CRITICAL INSTRUCTIONS:
- ONLY use columns that exist in the schema above
- The orders table does NOT have pre-calculated total columns
- To calculate order totals, you MUST join to order_items and compute: quantity * list_price * (1 - discount)
- Never invent columns like "total_amount", "order_total", or "total_price"

Think through this step-by-step using Chain-of-Thought reasoning. Break down the problem before writing SQL.

Step 1: What tables are needed?
Step 2: What columns should be selected?
Step 3: Are any JOINs needed? If yes, what are the JOIN conditions?
Step 4: Are any WHERE filters needed? If yes, what conditions?
Step 5: Are any aggregations needed (COUNT, SUM, AVG, etc.)?
Step 6: Is GROUP BY needed? If yes, which columns?
Step 7: Is sorting needed (ORDER BY)? If yes, which columns and direction?
Step 8: Is a LIMIT needed?

Now, generate the SQL query:

SQL:
"""
        return prompt

    def getSQL(self, llmResponse: str) -> str:
        """Extract SQL query from LLM response and normalize formatting"""
        sql = None

        # Try to find SQL after "SQL:" marker
        sqlMatch = re.search(r'SQL:\s*```(?:sql)?\s*(.*?)\s*```',
                             llmResponse, re.DOTALL | re.IGNORECASE)
        if sqlMatch:
            sql = sqlMatch.group(1).strip()

        # Try to find any code block
        if not sql:
            sqlMatch = re.search(
                r'```(?:sql)?\s*(.*?)\s*```', llmResponse, re.DOTALL)
            if sqlMatch:
                sql = sqlMatch.group(1).strip()

        # Try to find SELECT statement
        if not sql:
            sqlMatch = re.search(r'(SELECT\s+.+?)(?:\n\n|$)',
                                 llmResponse, re.DOTALL | re.IGNORECASE)
            if sqlMatch:
                sql = sqlMatch.group(1).strip()

        # Fallback: return last line if it looks like SQL
        if not sql:
            lines = llmResponse.strip().split('\n')
            for line in reversed(lines):
                if line.strip().upper().startswith('SELECT'):
                    sql = line.strip()
                    break

        # If still no SQL found, return the response as-is
        if not sql:
            sql = llmResponse.strip()

        # Normalize SQL: replace multiple spaces/newlines with single space
        sql = re.sub(r'\s+', ' ', sql)

        # Remove trailing semicolon if present
        sql = sql.rstrip(';')

        return sql

    def validateAndCorrectQuery(self, sql: str, question: str, maxAttempts: int = 3) -> str:
        """
        Execution-based validation with self-correction loop.

        Improves accuracy by 3-5%.
        """
        for attempt in range(maxAttempts):
            try:
                # Validate syntax with EXPLAIN
                self.duckdbConn.execute(f"EXPLAIN {sql}")

                # Execute query
                result = self.duckdbConn.execute(sql).fetchall()

                # Check for empty results (potential semantic error)
                if len(result) == 0 and not self._expectsEmpty(question):
                    print(
                        f"⚠️  Query returned no results (attempt {attempt + 1})")

                print(f"✅ Validated SQL (attempt {attempt + 1})")
                return sql

            except Exception as e:
                print(f"❌ Validation failed (attempt {attempt + 1}): {str(e)}")

                if attempt < maxAttempts - 1:
                    # Regenerate with error feedback
                    sql = self._regenerateWithFeedback(question, sql, str(e))
                else:
                    print(f"⚠️  Max attempts reached, returning last SQL")

        return sql

    def _regenerateWithFeedback(self, question: str, failedSQL: str, errorMessage: str) -> str:
        """Regenerate SQL with specific error feedback"""
        schemaContext = self.buildSchemaContext()

        feedbackPrompt = f"""Your previous SQL query had an error.

ORIGINAL QUESTION: {question}

YOUR SQL: {failedSQL}

ERROR MESSAGE: {errorMessage}

DATABASE SCHEMA:
{schemaContext}

Analyze the error and generate a CORRECTED SQL query:

1. What caused this error?
2. What table/column names are actually available?
3. What is the correct JOIN condition or WHERE clause?

CORRECTED SQL:
"""

        try:
            response = self.ollamaClient.chat(
                model=self.model,
                messages=[
                    {'role': 'system',
                        'content': 'You are an expert at debugging and fixing SQL queries.'},
                    {'role': 'user', 'content': feedbackPrompt}
                ]
            )
            return self.getSQL(response['message']['content'])
        except Exception as e:
            print(f"Regeneration failed: {e}")
            return failedSQL

    def expectsEmpty(self, question: str) -> bool:
        """Check if question expects empty results"""
        emptyKeywords = ['never', 'no ', 'none',
                         'zero', 'empty', 'without', 'don\'t', 'not']
        return any(kw in question.lower() for kw in emptyKeywords)

    def generate(self, question: str) -> str:
        """
        Generate SQL query with validation and self-correction.

        This is the complete workflow including the critical validation step.
        """
        print(f"\nGenerating Query for: {question}")

        # Step 1: Retrieve similar examples
        print("📚 Retrieving similar examples...")
        similarExamples = self.findSimilarQueryExamples(question, topK=3)

        # Step 2: Build contexts
        print("🏗️  Building prompt contexts...")
        schemaContext = self.buildSchemaContext()
        fewShotContext = self._buildFewShotContext(similarExamples)

        # Step 3: Build CoT prompt
        cotPrompt = self.buildCoTPrompt(
            question, schemaContext, fewShotContext)

        # Step 4: Generate initial SQL
        print(f"🤖 Generating SQL with {self.model}...")
        try:
            response = self.ollamaClient.chat(
                model=self.model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are an expert SQL query generator. Follow Chain-of-Thought reasoning.'
                    },
                    {
                        'role': 'user',
                        'content': cotPrompt
                    }
                ]
            )

            llmResponse = response['message']['content']
            sql = self.getSQL(llmResponse)

            # Step 5: Lightweight review & correction (max 2 rounds)
            print("🔍 Running ValidatorAgent review...")
            reviewResult = self.reviewer.validate(
                question=question, sql=sql, schemaContext=schemaContext
            )

            sql = reviewResult['sql']
            if reviewResult['approved']:
                print(f"✅ Reviewer APPROVED (attempts: {reviewResult['attempts']})")
            else:
                print(f"⚠️  Reviewer could not fully approve after {reviewResult['attempts']} corrections")
                if reviewResult['issues']:
                    print(f"   Issues: {reviewResult['issues'][:3]}")

            print(f"✅ Final SQL: {sql}")
            return sql

        except Exception as e:
            print(f"❌ Error generating SQL: {e}")
            raise

    def close(self):
        """Cleanup resources"""
        if hasattr(self, 'duckdbConn') and self.duckdbConn:
            self.duckdbConn.close()
