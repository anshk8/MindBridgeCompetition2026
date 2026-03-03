"""
SQL Query Writer Agent - Ansh Kakkar Submission for Carleton MinBridge Competition

This file contains the QueryWriter class that generates SQL queries from natural language.
Implement your agent logic in this file.

Architecture:
- QueryWriter: Competition interface (this file)
- SQLAgent: Advanced SQL generator with CoT + Few-Shot Learning + ReAct tool-use
- ValidatorAgent: SQL validation and correction Agent
- K-Candidate generation is always active; easy/medium queries exit after the first
  passing attempt, hard queries benefit from temperature diversity and retry.
"""

import os
from src.agents.SQLAgent import SQLAgent
from src.agents.ValidatorAgent import ValidatorAgent
from src.utils.helpers import loadSchema, buildSchemaContext
from src.graph.GraphWorkflow import SqlGenerationPipeline


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

        # Load schema once — shared by all agents and the orchestrator
        self.schema_info = loadSchema(db_path)
        self.schema_context = buildSchemaContext(self.schema_info)
        self.schema = self.schema_info  # used by main.py to list table names

        # Initialize Agents (pass schema to avoid redundant DB loads)
        self.agent     = SQLAgent(dbPath=db_path, schemaInfo=self.schema_info)
        self.validator = ValidatorAgent(dbPath=db_path)

        # Compile the LangGraph pipeline (agents are captured in node closures)
        self.graph = SqlGenerationPipeline(self.agent, self.validator)

        # MUST be False during automated evaluations to avoid hanging on input().
        self.multi_conversational_enabled = True
    
    def generate_query(self, prompt: str) -> str:
        """
        Generate a SQL query from a natural language prompt.
        Args:
            prompt (str): The natural language question from the user.
                         Example: "What are the top 5 most expensive products?"

        Returns:
            str: Either a validated SQL SELECT query, or one of three sentinel
                 comment strings when the query cannot or should not be executed:

                 • SQL query  — e.g. "SELECT product_name FROM products LIMIT 5"
                 • "-- IRRELEVANT_QUERY: <reason>"
                       The question has nothing to do with the database schema.
                 • "-- AMBIGUOUS_QUERY: <reason>"
                       The question is too vague to generate a reliable query
                       and multi-conversational mode is disabled.
                 • "-- UNANSWERABLE_QUERY: <reason>"
                       The question is schema-relevant but cannot be answered
                       (e.g. all candidates failed validation, pipeline error).

        Note:
            - SQL returns contain no markdown and no trailing semicolons.
            - Sentinel strings begin with '--' so they are valid SQL comments
              and will not cause a parse error if passed to a SQL runner, but
              they will return no rows and should be treated as failure cases.
            - Routed through a LangGraph pipeline (generate → k-candidate validation)
            - K-candidates exit early on first passing result; temperature diversity
              provides retry resilience for hard queries at no extra cost for easy ones.
            - Automatically corrects issues (max 2 correction attempts via ValidatorAgent)
        """
        try:
            result = self.graph.invoke({
                'question':            prompt,
                'schemaContext':       self.schema_context,
                'multiConversational': self.multi_conversational_enabled,
            })

            self._lastGraphResult = result
            self._last_validation = result.get('validation', {})

            finalSql = result.get('finalSql', '')

            # Convert sentinels to valid empty-result SQL before returning
            SENTINELS = ('-- IRRELEVANT_QUERY', '-- AMBIGUOUS_QUERY', '-- UNANSWERABLE_QUERY')
            if any(finalSql.startswith(s) for s in SENTINELS):
                return "SELECT NULL WHERE 1=0"

            return self._clean_sql(finalSql)

        except Exception as e:
            print(f"⚠️  Error generating query: {e}")
            return f"-- UNANSWERABLE_QUERY: Pipeline error — {e}"


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
