import duckdb
from typing import Dict, Any, List
from src.schemas.ValidatorAgentSchemas import ValidationResult


def loadSchema(db_path: str) -> Dict[str, Any]:
    """
    Load schema information for all tables in the database, including column details and sample data.

    Args:
        db_path (str): Path to the DuckDB database file

    Returns:
        Dict[str, Any]: Dictionary mapping table names to their schema info (columns and samples)
    """
    schemaWithSamples = {}

    conn = None
    try:
        # Use temporary connection
        conn = duckdb.connect(db_path)

        # Get all table names
        tables = conn.execute("SHOW TABLES").fetchall()
        tableNames = sorted([table[0] for table in tables])  # ✅ Sort for deterministic ordering

        for tableName in tableNames:
            # Get column information
            columns = conn.execute(
                f"DESCRIBE {tableName}").fetchall()

            columnInfo = []
            for col in columns:
                columnInfo.append({
                    'name': col[0],
                    'type': col[1],
                    'null': col[2] if len(col) > 2 else None
                })

            # Get sample data
            cursor = conn.execute(
                f"SELECT * FROM {tableName} LIMIT 3"
            )
            rows = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
            samples = [dict(zip(col_names, row)) for row in rows]

            schemaWithSamples[tableName] = {
                'columns': columnInfo,
                'samples': samples
            }

        return schemaWithSamples

    except Exception as e:
        print(f"Error loading schema: {e}")
        return {}
    finally:
        if conn:
            conn.close()


def buildSchemaContext(schema_info: Dict[str, Any]) -> str:
    """
    Build rich schema context string with sample data for LLM prompts.

    Args:
        schema_info (Dict[str, Any]): Schema information from loadSchema()

    Returns:
        str: Formatted schema context with columns and sample rows
    """
    contextParts = []

    for tableName, tableData in schema_info.items():
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

    return "\n".join(contextParts)


def buildFewShotContext(examples: List[Any]) -> str:
    """
    Build few-shot examples context for prompt.
    
    Args:
        examples: List of FewShotExample objects with question, sql, and explanation attributes
        
    Returns:
        str: Formatted few-shot examples string
    """
    exampleParts = []

    for i, ex in enumerate(examples, 1):
        exampleParts.append(f"Example {i}:")
        exampleParts.append(f"Question: {ex.question}")
        exampleParts.append(f"SQL: {ex.sql}")
        if ex.explanation:
            exampleParts.append(f"Explanation: {ex.explanation}")
        exampleParts.append("")

    return "\n".join(exampleParts)



def executeSQL(db_path: str, sql: str) -> Dict[str, Any]:
    """
    Execute SQL query and return execution metadata.

    Runs the query to check for execution success, gets a preview of results,
    and counts total rows efficiently without fetching all data.

    Args:
        db_path (str): Path to the DuckDB database file
        sql (str): SQL query to execute

    Returns:
        Dict[str, Any]: Execution results with structure:
            {
                'success': bool,
                'row_count': int,
                'sample_result': str | None,
                'error': str | None
            }
    """
    conn = None
    try:
        # Open the database in read-only mode since this helper is used for validation
        conn = duckdb.connect(db_path, read_only=True)
        # Trim whitespace and remove any trailing semicolon
        normalized_sql = sql.strip()
        if normalized_sql.endswith(";"):
            normalized_sql = normalized_sql[:-1].rstrip()

        # Running only a small sample to check for execution success and get a preview
        sample_result = conn.execute(normalized_sql).fetchmany(5)
        sample = str(sample_result[0])[:100] if sample_result else None

        # Get accurate row count efficiently without fetching all data
        count_sql = f"SELECT COUNT(*) FROM ({normalized_sql}) AS subquery"
        row_count = conn.execute(count_sql).fetchone()[0]

        return {
            'success': True,
            'row_count': row_count,
            'sample_result': sample,
            'error': None,
        }
    except Exception as e:
        return {
            'success': False,
            'row_count': 0,
            'sample_result': None,
            'error': str(e),
        }
    finally:
        if conn:
            conn.close()

def scoreCandidate(validation: ValidationResult) -> int:
    """
    Heuristic score for a single validated SQL candidate. Used inside kCandidateNode to rank multiple candidates

    Scoring breakdown:
        +50  executes without error
        +40  approved by semantic review
        +5   returns at least one row
        -3   per execution fix applied by ValidatorAgent
        -3   per semantic fix applied by ValidatorAgent
    """
    score = 0
    # BIG penalty for candidates that fail to execute
    if not validation.get('execution_ok'):
        score -= 99999999999
    else:
        score += 50
        if validation.get('approved'):
            score += 40
        if validation.get('row_count', 0) > 0:
            score += 5
        score -= validation.get('exec_fixes', 0) * 3
        score -= validation.get('semantic_fixes', 0) * 3
    return score