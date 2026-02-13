"""
SQL Query Writer Agent - Competition Submission

This module implements the required QueryWriter interface for the competition.
It wraps the sophisticated SQLAgent that uses Chain-of-Thought reasoning
and Dynamic Few-Shot Learning for accurate SQL generation.

Architecture:
- QueryWriter: Competition interface (this file)
- SQLAgent: Advanced SQL generator with CoT + Few-Shot Learning
- ValidatorAgent: SQL validation and correction (optional)
"""

import os
import duckdb
from typing import Dict, Any
from db.bike_store import get_schema_info
from agents.SQLAgent import SQLAgent


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
        
        # Initialize the sophisticated SQL Agent
        # This handles all the heavy lifting:
        # - Schema introspection with sample data
        # - Embedding model for few-shot retrieval
        # - Chain-of-Thought prompt construction
        # - SQL generation with validation
        print(f"🚀 Initializing QueryWriter with {os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:7b')}...")
        self.agent = SQLAgent(dbPath=db_path)
        
        # Load schema for compatibility with main.py expectations
        self.schema = self._load_schema()
        
        print("✅ QueryWriter ready!")

    def generate_query(self, prompt: str) -> str:
        """
        Generate a SQL query from a natural language prompt.

        This method is called by the evaluation system. It must:
        1. Accept a natural language question as input
        2. Return a valid SQL query string

        Args:
            prompt (str): The natural language question from the user.
                         Example: "What are the top 5 most expensive products?"

        Returns:
            str: A valid SQL query that answers the question.
                 Example: "SELECT product_name, list_price FROM products ORDER BY list_price DESC LIMIT 5"

        Note:
            - Returns ONLY the SQL query string (no markdown, no explanations)
            - Query is validated for syntax and semantics
            - Uses Chain-of-Thought reasoning internally for accuracy
            - Automatically retrieves similar examples via semantic search
        """
        try:
            # Generate SQL using the sophisticated agent
            # This internally:
            # 1. Embeds the question
            # 2. Retrieves 3 most similar few-shot examples
            # 3. Builds rich schema context with sample data
            # 4. Constructs Chain-of-Thought prompt
            # 5. Generates SQL with LLM
            # 6. Validates and self-corrects if needed
            sql = self.agent.generate(prompt)
            
            # Ensure clean output for competition evaluation
            sql = self._clean_sql(sql)
            
            return sql
            
        except Exception as e:
            # Log error but don't crash
            print(f"⚠️  Error generating query: {e}")
            # Return a safe fallback query that won't crash the evaluator
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
    
    def _load_schema(self) -> Dict[str, Any]:
        """
        Load database schema for compatibility with main.py.
        
        Returns dict mapping table names to column information.
        """
        try:
            conn = duckdb.connect(self.db_path)
            schema = {}
            
            # Get all table names
            tables = conn.execute("SHOW TABLES").fetchall()
            
            for table in tables:
                table_name = table[0]
                # Get column information
                columns = conn.execute(f"DESCRIBE {table_name}").fetchall()
                schema[table_name] = [
                    {'name': col[0], 'type': col[1]}
                    for col in columns
                ]
            
            conn.close()
            return schema
            
        except Exception as e:
            print(f"⚠️  Warning: Could not load schema: {e}")
            return {}
    
    def close(self):
        """Clean up resources (called at end of session)"""
        if hasattr(self.agent, 'close'):
            self.agent.close()
