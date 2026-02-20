"""
prompts.py
Contains all prompt related functions used by the agents
"""

from typing import List, Any


# ================================================================= #
# SQL Agent Prompts                                                  #
# ================================================================= #

def buildSystemPrompt() -> str:
    """Build the system prompt with reasoning instructions and rules for SQL generation"""
    return """You are an expert SQL query generator. Your task is to convert natural language questions into syntactically and semantically correct SQL queries.

CRITICAL RULES:
- ONLY use columns that exist in the provided schema
- The orders table does NOT have pre-calculated total columns
- Never invent columns like "total_amount", "order_total", or "total_price" unless they exist in the schema

REASONING PROCESS:
You must think through each query step-by-step using Chain-of-Thought reasoning:

Step 1: What tables are needed?
Step 2: What columns should be selected?
Step 3: Are any JOINs needed? If yes, what are the JOIN conditions?
Step 4: Are any WHERE filters needed? If yes, what conditions?
Step 5: Are any aggregations needed (COUNT, SUM, AVG, etc.)?
Step 6: Is GROUP BY needed? If yes, which columns?
Step 7: Is sorting needed (ORDER BY)? If yes, which columns and direction?
Step 8: Is a LIMIT needed?

You will respond in JSON with two fields: 'reasoning' (your step-by-step thinking) and 'sql' (the final SQL query — no markdown, just the raw SQL).
"""


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


def buildUserPrompt(question: str, schemaContext: str, fewShotContext: str) -> str:
    """
    Build the user prompt with schema, examples, and the question.
    
    Args:
        question: The natural language question from the user
        schemaContext: Formatted schema information with sample data
        fewShotContext: Formatted few-shot examples
        
    Returns:
        str: Complete user prompt
    """
    return f"""DATABASE SCHEMA:
{schemaContext}

SIMILAR EXAMPLES FOR REFERENCE:
{fewShotContext}

USER QUESTION: {question}

Please generate the SQL query following your reasoning process. Make sure to adhere to the critical rules and use the schema context effectively. The SQL should be syntactically correct and semantically aligned with the question."""


# ================================================================= #
# Validator Agent Prompts                                            #
# ================================================================= #

def buildReviewerSystemPrompt() -> str:
    """System prompt for SQL semantic reviewer"""
    return """You are a senior database administrator and SQL auditor.
Your job is to determine whether a generated SQL query correctly and completely answers a user's natural language question.

You are strict but fair. You APPROVE queries that are semantically correct even if they differ in style from what you would write.
You REJECT queries that:
- Reference columns or tables that don't exist in the schema
- Use wrong JOIN conditions or missing JOINs
- Compute aggregations incorrectly
- Answer a different question than what was asked
- Have GROUP BY violations or other structural problems

You will respond in JSON with three fields: 'approved' (bool), 'issues' (list of strings, empty if approved), and 'corrected_sql' (fixed SQL string if rejected, null if approved)."""


def buildFixerSystemPrompt() -> str:
    """System prompt for SQL query fixer"""
    return """You are a specialized SQL debugging engineer.
Your ONLY job is to fix broken or incorrect SQL queries.

Rules:
1. Only use columns that exist in the provided schema.
2. Fix the EXACT error described — do not rewrite the entire query unless necessary.
3. If the fix requires restructuring (e.g. adding a CTE), do so cleanly.
4. Never invent columns. Check the schema carefully before referencing any column.

You will respond in JSON with one field: 'sql' containing the corrected SQL query (raw SQL only, no markdown)."""


def buildSemanticReviewPrompt(question: str, sql: str, schemaContext: str) -> str:
    """
    Build prompt for semantic review of a generated SQL query.
    
    Args:
        question: The user's natural language question
        sql: The generated SQL query to review
        schemaContext: Formatted schema information
        
    Returns:
        str: Semantic review prompt (to be used with buildReviewerSystemPrompt)
    """
    return f"""DATABASE SCHEMA:
{schemaContext}

USER QUESTION: {question}

GENERATED SQL: {sql}

Review this SQL for semantic correctness. Check:
1. Are the correct tables being queried for this question?
2. Do ALL referenced columns actually exist in the schema above?
3. Are JOIN conditions using the correct foreign keys?
4. Are calculations and derived values correct and consistent with the schema and question?
5. Does the query actually answer the user's question?

Common mistakes to watch for:
- Using columns that do not exist in the provided schema
- Forgetting to compute derived totals or aggregates from base numeric columns
- Wrong JOIN conditions or missing JOINs
- Incorrect GROUP BY columns
"""


def buildCorrectionPrompt(question: str, failedSQL: str, error: str, schemaContext: str) -> str:
    """
    Build prompt for correcting a failed SQL query.
    
    Args:
        question: The user's natural language question
        failedSQL: The SQL query that failed
        error: The error message received
        schemaContext: Formatted schema information
        
    Returns:
        str: SQL correction prompt (to be used with buildFixerSystemPrompt)
    """
    return f"""QUESTION: {question}

FAILED SQL: {failedSQL}

ERROR: {error}

DATABASE SCHEMA:
{schemaContext}

CRITICAL RULES:
- Only use columns that exist in the schema above
- Order totals must be calculated as: quantity * list_price * (1 - discount) from order_items
- Never invent columns like "total_amount" or "order_total"
"""
