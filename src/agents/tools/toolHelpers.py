"""
agents/tools/toolHelpers.py

Helpers that bridge Ollama's tool-calling protocol with the actual DB
lookup functions in tools.py.

Why is executeTool needed?
──────────────────────────
When you pass `tools=` to the Ollama (or any LLM) client, the model does
NOT execute your Python functions.  It only returns a structured message
that says "I want to call <function> with <args>".  Your application must
read that message, actually run the function, and feed the result back as
a 'tool' role message.  There is no way to skip this step — frameworks
like LangChain just wrap the same loop inside an abstraction.
"""

from typing import Any, Dict, List

from src.agents.tools.tools import get_distinct_values, search_value, get_columns


# ────────────────────────────────────────────────────────────────── #
# Tool definitions (Ollama tool-calling format)                      #
# ────────────────────────────────────────────────────────────────── #

def getTools() -> List[dict]:
    """Return the three DB lookup tools in Ollama's tool-calling format."""
    return [
        {
            'type': 'function',
            'function': {
                'name': 'get_distinct_values',
                'description': (
                    'Return up to 20 distinct values from a table column. '
                    'Use to verify exact string casing/spelling for WHERE filters '
                    '(e.g. brand names, store names, state codes, category names).'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'table':  {'type': 'string', 'description': 'Table name'},
                        'column': {'type': 'string', 'description': 'Column name'},
                    },
                    'required': ['table', 'column'],
                },
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'search_value',
                'description': (
                    'Fuzzy-search all VARCHAR columns across every table for a term. '
                    'Use when unsure which table/column contains a value the user mentioned.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'term': {'type': 'string', 'description': 'Value to search for'},
                    },
                    'required': ['term'],
                },
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'get_columns',
                'description': (
                    'Return all column names and types for a table. '
                    'Use to confirm exact column names before writing SELECT or WHERE.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'table': {'type': 'string', 'description': 'Table name'},
                    },
                    'required': ['table'],
                },
            },
        },
    ]


# ────────────────────────────────────────────────────────────────── #
# Tool dispatcher                                                    #
# ────────────────────────────────────────────────────────────────── #

def executeTool(
    tool_call: dict,
    db_path: str,
    schema_info: Dict[str, Any],
) -> List[str]:
    """
    Dispatch an Ollama tool_call dict to the matching DB lookup function.

    The LLM cannot run Python code — it returns a structured message
    requesting a tool call.  This function reads that message and
    actually executes the corresponding function, returning results as
    a list of strings that are appended to the conversation as a
    'tool' role message.

    Parameters
    ----------
    tool_call   : the tool_call entry from the Ollama response message
    db_path     : path to the DuckDB database file
    schema_info : in-memory schema dict (table → column metadata)

    Returns
    -------
    List of result strings (one per row / match).
    """
    func = tool_call.get('function', {})
    name = func.get('name', '')
    args = func.get('arguments', {}) or {}

    if name == 'get_distinct_values':
        return get_distinct_values(
            db_path=db_path,
            schema_info=schema_info,
            table=args.get('table', ''),
            column=args.get('column', ''),
        )
    if name == 'search_value':
        return search_value(
            db_path=db_path,
            schema_info=schema_info,
            term=args.get('term', ''),
        )
    if name == 'get_columns':
        return get_columns(
            schema_info=schema_info,
            table=args.get('table', ''),
        )
    return [f"Error: unknown tool '{name}'. Available: get_distinct_values, search_value, get_columns"]
