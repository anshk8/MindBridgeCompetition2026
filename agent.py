"""
SQL Query Writer Agent - Ansh Kakkar Submission for Carleton MindBridge Competition

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

        # Load schema once to avoid redundant DB calls
        self.schema_info = loadSchema(db_path)
        self.schema_context = buildSchemaContext(self.schema_info)
        self.schema = self.schema_info  # used by main.py to list table names

        # Initialize Agents (passing schema to avoid redundant DB loads)
        self.agent     = SQLAgent(dbPath=db_path, schemaInfo=self.schema_info)
        self.validator = ValidatorAgent(dbPath=db_path)

        # Compile the LangGraph pipeline (agents are captured in node closures)
        self.graph = SqlGenerationPipeline(self.agent, self.validator)

        # MUST be False during automated evaluations to avoid hanging on input().
        self.multi_conversational_enabled = False
    
    def generate_query(self, prompt: str) -> str:
        """
        Generate a SQL query from a natural language prompt.
        Args:
            prompt (str): The natural language question from the user.
                         Example: "What are the top 5 most expensive products?"

        Returns:
            str: A valid SQL query string. Always executable:
                 • SQL query  — e.g. "SELECT product_name FROM products LIMIT 5"
                 • "SELECT 1 WHERE 1=0"  — returned for irrelevant, ambiguous,
                   or unanswerable queries; executes successfully with 0 rows.
        """

        #Initiate generation by invoking the graph with the initial state
        try:
            result = self.graph.invoke({
                'question':            prompt,
                'schemaContext':       self.schema_context,
                'multiConversational': self.multi_conversational_enabled,
            })

            self._lastGraphResult = result
            self._last_validation = result.get('validation', {})

            finalSql = result.get('finalSql', '')

            # Convert sentinels to valid empty-result SQL so the evaluator always receives executable SQL (returns 0 rows, no crash).
            SENTINELS = ('-- IRRELEVANT_QUERY', '-- AMBIGUOUS_QUERY', '-- UNANSWERABLE_QUERY')
            if any(finalSql.startswith(s) for s in SENTINELS):
                if finalSql.startswith('-- UNANSWERABLE_QUERY'):
                    print(f"\n Query could not be answered")
                return 'SELECT 1 WHERE 1=0'

            return self._clean_sql(finalSql)

        except Exception as e:
            print(f"⚠️  Error generating query: {e}")
            return 'SELECT 1 WHERE 1=0'


    def _clean_sql(self, sql: str) -> str:
        """
        Clean SQL output by removing...
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
