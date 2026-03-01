"""
agents/tools/db_tools.py

Lightweight, read-only database lookup tools used by the ReAct loop
inside SQLAgent.generate().  Each function takes the minimum arguments
it needs and returns a plain Python object (list / str) that is safe
to serialise into an LLM prompt.

Security notes
──────────────
• All queries are parameterless SELECT DISTINCTs with hard LIMIT caps.
• Table / column names are validated against the in-memory schema dict
  before being interpolated — no arbitrary user strings hit the DB.
"""

import duckdb
from typing import Any, Dict, List


# ────────────────────────────────────────────────────────────────── #
# Tool 1: get_distinct_values                                        #
# ────────────────────────────────────────────────────────────────── #

def get_distinct_values(
    db_path: str,
    schema_info: Dict[str, Any],
    table: str,
    column: str,
    limit: int = 20,
) -> List[str]:
    """
    Return up to *limit* distinct values from *table*.*column*.

    Used by the LLM to verify exact string casing / spelling before
    writing a WHERE filter (e.g. brand_name = 'Trek' vs 'trek').

    Returns a list of stringified values, or a single-element list
    containing an error message if the lookup fails.
    """
    # ── Validate against schema (prevents SQL injection) ──────────── #
    if table not in schema_info:
        return [f"Error: table '{table}' does not exist. Valid tables: {', '.join(sorted(schema_info))}"]

    valid_columns = {col['name'] for col in schema_info[table]['columns']}
    if column not in valid_columns:
        return [f"Error: column '{column}' does not exist in '{table}'. Valid columns: {', '.join(sorted(valid_columns))}"]

    # ── Execute ───────────────────────────────────────────────────── #
    conn = None
    try:
        conn = duckdb.connect(db_path, read_only=True)
        rows = conn.execute(
            f'SELECT DISTINCT "{column}" FROM "{table}" ORDER BY "{column}" LIMIT {limit}'
        ).fetchall()
        return [str(row[0]) for row in rows]
    except Exception as e:
        return [f"Error: {e}"]
    finally:
        if conn:
            conn.close()


# ────────────────────────────────────────────────────────────────── #
# Tool 2: search_value                                               #
# ────────────────────────────────────────────────────────────────── #

def search_value(
    db_path: str,
    schema_info: Dict[str, Any],
    term: str,
    limit_per_column: int = 5,
) -> List[str]:
    """
    Fuzzy-search all VARCHAR / TEXT columns across every table for *term*.

    Returns a list of "table.column: [matching_values]" strings so the
    LLM knows exactly where a user-mentioned value lives.
    Returns ["No matches found"] when nothing matches.
    """
    if not term or not term.strip():
        return ["Error: search term must not be empty"]

    text_types = {'VARCHAR', 'TEXT', 'CHAR', 'STRING', 'NVARCHAR'}
    matches: List[str] = []
    conn = None

    try:
        conn = duckdb.connect(db_path, read_only=True)

        for table, info in schema_info.items():
            for col in info['columns']:
                col_type = col.get('type', '').upper()
                # DuckDB types can include length, e.g. VARCHAR(255)
                base_type = col_type.split('(')[0].strip()
                if base_type not in text_types:
                    continue

                col_name = col['name']
                try:
                    rows = conn.execute(
                        f"SELECT DISTINCT \"{col_name}\" FROM \"{table}\" "
                        f"WHERE \"{col_name}\" ILIKE '%{term}%' LIMIT {limit_per_column}"
                    ).fetchall()
                    if rows:
                        vals = [str(r[0]) for r in rows]
                        matches.append(f"{table}.{col_name}: {vals}")
                except Exception:
                    # Skip columns that error (e.g. unsupported ILIKE type)
                    continue

        return matches if matches else ["No matches found"]

    except Exception as e:
        return [f"Error: {e}"]
    finally:
        if conn:
            conn.close()


# ────────────────────────────────────────────────────────────────── #
# Tool 3: get_columns                                                #
# ────────────────────────────────────────────────────────────────── #

def get_columns(
    schema_info: Dict[str, Any],
    table: str,
) -> List[str]:
    """
    Return every column name (with type) for *table*.

    Pure in-memory lookup — no DB query needed since the schema is
    already loaded at startup.
    """
    if table not in schema_info:
        return [f"Error: table '{table}' does not exist. Valid tables: {', '.join(sorted(schema_info))}"]

    return [
        f"{col['name']} ({col.get('type', 'UNKNOWN')})"
        for col in schema_info[table]['columns']
    ]
