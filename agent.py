"""
SQL Query Writer Agent - Ansh Kakkar Submission for Carleton MinBridge Competition

This file contains the QueryWriter class that generates SQL queries from natural language.
Implement your agent logic in this file.

Architecture:
- QueryWriter: Competition interface (this file)
- SQLAgent: Advanced SQL generator with CoT + Few-Shot Learning
- ValidatorAgent: SQL validation and correction Agent
"""

import os
from agents.SQLAgent import SQLAgent
from agents.ValidatorAgent import ValidatorAgent
from agents.DifficultyRankerAgent import DifficultyRankerAgent
from db.bike_store import get_schema_info
from utils.helpers import loadSchema, buildSchemaContext
from graph.GraphWorkflow import SqlGenerationPipeline


def get_ollama_client():
    """
    Get Ollama client configured for either Carleton server or local instance.

    Set OLLAMA_HOST environment variable to use Carleton's LLM server.
    Defaults to local Ollama instance.
    """
    import ollama
    host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    return ollama.Client(host=host)


def get_model_name():
    """
    Get the model name from environment or use default.

    Set OLLAMA_MODEL environment variable to specify which model to use.
    """
    return os.getenv('OLLAMA_MODEL', 'llama3.2')


class QueryWriter:
    """
    SQL Query Writer Agent that converts natural language to SQL queries.

    This class is the main interface for the competition evaluation.
    You must implement the generate_query method.
    """

    def __init__(self, db_path: str = 'bike_store.db'):
        """
        Initialize the QueryWriter.

        Args:
            db_path (str): Path to the DuckDB database file.
        """
        self.db_path = db_path
        self.schema = get_schema_info(db_path=db_path)
        self.client = get_ollama_client()
        self.model = get_model_name()

        # Load schema with samples for agents
        self.schema_info = loadSchema(db_path)
        self.schema_context = buildSchemaContext(self.schema_info)  # cached once

        # Initialize Agents
        self.ranker    = DifficultyRankerAgent(dbPath=db_path)
        self.agent     = SQLAgent(dbPath=db_path)
        self.validator = ValidatorAgent(dbPath=db_path)
        # Compile the LangGraph pipeline (agents are captured in node closures)
        self.graph = SqlGenerationPipeline(self.ranker, self.agent, self.validator)

        #Settings, Modifiable by user
        self.k_candidate_enabled = False   # Set False to use fast path for all queries
        self.k_candidate_count = 5
    
    def generate_query(self, prompt: str) -> str:
        """
        Generate a SQL query from a natural language prompt.

        This method is called by the evaluation system. It orchestrates:
        1. SQL generation via SQLAgent (Chain-of-Thought + Few-Shot)
        2. Validation and correction via ValidatorAgent
        3. Returns the final validated SQL query

        Args:
            prompt (str): The natural language question from the user.
                         Example: "What are the top 5 most expensive products?"

        Returns:
            str: A validated SQL query that answers the question.
                 Example: "SELECT product_name, list_price FROM products ORDER BY list_price DESC LIMIT 5"

        Note:
            - Returns ONLY the SQL query string (no markdown, no explanations)
            - Routed through a LangGraph pipeline (rank → fast path OR k-candidate path)
            - Automatically corrects issues (max 2 correction attempts via ValidatorAgent)
        """
        try:
            result = self.graph.invoke({
                'question':      prompt,
                'schemaContext': self.schema_context,
                'kEnabled':      self.k_candidate_enabled,
                'kCount':        self.k_candidate_count,
            })

            self._lastGraphResult  = result                        # full state; for tests only
            self._last_validation  = result.get('validation', {})  # legacy alias; invisible to evaluator
            return self._clean_sql(result['finalSql'])

        except Exception as e:
            print(f"⚠️  Error generating query: {e}")
            return "SELECT 1"


    def _clean_sql(self, sql: str) -> str:
        """
        Clean SQL output to meet competition requirements.

        Removes:
        - Markdown code blocks
        - Extra whitespace
        - Trailing semicolons (optional based on competition rules)
        """
        sql = sql.strip()

        # Remove markdown code blocks if present
        if '```' in sql:
            # Extract SQL from code block
            lines = sql.split('\n')
            cleaned_lines = []
            in_code_block = False

            for line in lines:
                if line.strip().startswith('```'):
                    in_code_block = not in_code_block
                    continue
                if in_code_block and not line.strip().startswith('```'):
                    cleaned_lines.append(line)

            sql = '\n'.join(cleaned_lines).strip()

        # Remove trailing semicolon (competition may not want it)
        sql = sql.rstrip(';')

        return sql

    def close(self):
        """Clean up resources (called at end of session)"""
        if hasattr(self.agent, 'close'):
            self.agent.close()
        if hasattr(self.ranker, 'close'):
            self.ranker.close()
