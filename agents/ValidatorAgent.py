"""
ValidatorAgent.py - Lightweight SQL Semantic Validator

Reviews generated SQL for correctness:
1. Syntax validation (by attempting to execute the query)
2. Execution check (runs query, verifies results)
3. Semantic review (LLM checks if query answers the question)

Max 2 correction attempts to avoid indefinite loops.
"""

import os
import re
import duckdb
import ollama
from typing import Dict, Any, Optional
from utils.helpers import expectsEmpty


class ValidatorAgent:
    """
    Lightweight reviewer that validates and optionally corrects SQL queries.

    Checks:
    - SQL executes without errors
    - Results are non-empty (when expected)
    - Semantic correctness via LLM review

    Will attempt to correct a failing query up to `maxCorrections` times.
    """

    def __init__(self, dbPath: str, maxCorrections: int = 2):
        self.dbPath = dbPath
        self.model = os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:14b')
        self.ollamaClient = ollama.Client(
            host=os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        )
        self.maxCorrections = maxCorrections
    
    def _get_connection(self):
        """Get a temporary database connection"""
        return duckdb.connect(self.dbPath)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, question: str, sql: str, schemaContext: str) -> Dict[str, Any]:
        """
        Full validation pipeline.

        Returns:
            {
                'approved': bool,
                'sql': str,              # final (possibly corrected) SQL
                'attempts': int,         # number of correction rounds used
                'execution_ok': bool,
                'row_count': int,
                'issues': list[str],
                'sample_result': str | None
            }
        """
        correctionsUsed = 0
        currentSQL = sql
        issues: set[str] = set()
        lastExecutedSQL = None
        lastExecResult = None

        while True:
            # --- Step 1: Execute (only if SQL changed) ---
            if currentSQL != lastExecutedSQL:
                lastExecResult = self._executeSQL(currentSQL)
                lastExecutedSQL = currentSQL
            execResult = lastExecResult

            if not execResult['success']:
                issues.add(f"Execution error: {execResult['error']}")
                
                # Can we make another correction?
                if correctionsUsed >= self.maxCorrections:
                    break
                
                # Ask LLM to fix
                corrected = self._correctQuery(
                    question, currentSQL, execResult['error'], schemaContext
                )
                if corrected and corrected != currentSQL:
                    currentSQL = corrected
                    correctionsUsed += 1
                    continue
                else:
                    break  # LLM couldn't produce a different query

            # --- Step 2: Quick sanity checks ---
            rowCount = execResult['row_count']
            if rowCount == 0 and not expectsEmpty(question):
                issues.add("Query returned 0 rows (expected results)")
                # Don't burn a correction round for this — it may still be correct

            # --- Step 3: Semantic review via LLM ---
            review = self._semanticReview(question, currentSQL, schemaContext)

            if review['approved']:
                merged_issues = list(issues.union(review.get('issues', [])))
                return {
                    'approved': True,
                    'sql': currentSQL,
                    'attempts': correctionsUsed,
                    'execution_ok': True,
                    'row_count': rowCount,
                    'issues': merged_issues}

            # Not approved — check if we can make another correction
            issues.update(review.get('issues', []))
            
            if correctionsUsed >= self.maxCorrections:
                break
            
            suggestion = review.get('suggestion')
            if suggestion:
                currentSQL = suggestion
                correctionsUsed += 1
            else:
                # Fall back to generic correction
                corrected = self._correctQuery(
                    question, currentSQL,
                    "; ".join(review.get('issues', ['Semantic issues detected'])),
                    schemaContext,
                )
                if corrected and corrected != currentSQL:
                    currentSQL = corrected
                    correctionsUsed += 1
                else:
                    break

        # Exhausted attempts — return best effort (reuse last execution if available)
        if currentSQL == lastExecutedSQL and lastExecResult:
            finalExec = lastExecResult
        else:
            finalExec = self._executeSQL(currentSQL)
        
        return {
            'approved': False,
            'sql': currentSQL,
            'attempts': correctionsUsed,
            'execution_ok': finalExec['success'],
            'row_count': finalExec.get('row_count', 0),
            'issues': list(issues),
            'sample_result': finalExec.get('sample_result'),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _executeSQL(self, sql: str) -> Dict[str, Any]:
        """Try running the SQL and return execution metadata."""
        conn = None
        try:
            conn = self._get_connection()
            
            # Running only a small sample to check for execution success and get a preview, without fetching all data
            sample_result = conn.execute(sql).fetchmany(5)
            sample = str(sample_result[0])[:100] if sample_result else None
            
            # Get accurate row count efficiently without fetching all data
            count_sql = f"SELECT COUNT(*) FROM ({sql}) AS subquery"
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

    def _semanticReview(self, question: str, sql: str, schemaContext: str) -> Dict[str, Any]:
        """Ask the LLM whether the SQL semantically answers the question."""
        prompt = f"""You are a senior database administrator reviewing SQL queries.

DATABASE SCHEMA:
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

Respond EXACTLY in this format (no extra text):
VERDICT: APPROVED or REJECTED
ISSUES: <comma-separated list of problems, or "None">
CORRECTED_SQL: <corrected SQL if rejected, or "None">
"""
        try:
            response = self.ollamaClient.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': 'You are an expert SQL reviewer. Be concise.'},
                    {'role': 'user', 'content': prompt},
                ],
            )
            return self._parseReview(response['message']['content'])
        except Exception as e:
            print(f"⚠️  Semantic review failed: {e}")
            return {'approved': False, 'issues': ["Semantic review failed"], 'suggestion': None}

    def _parseReview(self, text: str) -> Dict[str, Any]:
        """Parse the structured LLM review response."""
        approved = False
        issues: list[str] = []
        suggestion: Optional[str] = None

        # Parse VERDICT
        verdict_match = re.search(r'VERDICT:\s*(APPROVED|REJECTED)', text, re.IGNORECASE)
        if verdict_match:
            approved = verdict_match.group(1).strip().upper() == 'APPROVED'

        # Parse ISSUES
        issues_match = re.search(r'ISSUES:\s*(.+?)(?=\nCORRECTED_SQL|$)', text, re.DOTALL | re.IGNORECASE)
        if issues_match:
            raw = issues_match.group(1).strip()
            if raw.lower() != 'none':
                issues = [i.strip() for i in raw.split(',') if i.strip()]

        # Parse CORRECTED_SQL
        sql_match = re.search(r'CORRECTED_SQL:\s*```(?:sql)?\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
        if not sql_match:
            sql_match = re.search(r'CORRECTED_SQL:\s*(SELECT\s+.+?)(?:\n\n|$)', text, re.DOTALL | re.IGNORECASE)
        if not sql_match:
            sql_match = re.search(r'CORRECTED_SQL:\s*(.+?)$', text, re.DOTALL | re.IGNORECASE)

        if sql_match:
            raw_sql = sql_match.group(1).strip()
            if raw_sql.lower() != 'none' and 'SELECT' in raw_sql.upper():
                suggestion = re.sub(r'\s+', ' ', raw_sql).rstrip(';')

        return {'approved': approved, 'issues': issues, 'suggestion': suggestion}

    def _correctQuery(self, question: str, failedSQL: str, error: str, schemaContext: str) -> Optional[str]:
        """Ask the LLM to fix a broken query given the error."""
        prompt = f"""Fix the following SQL query.

QUESTION: {question}
FAILED SQL: {failedSQL}
ERROR: {error}

DATABASE SCHEMA:
{schemaContext}

CRITICAL RULES:
- Only use columns that exist in the schema above.
- Order totals must be calculated as: quantity * list_price * (1 - discount) from order_items.
- Never invent columns like "total_amount" or "order_total".

Return ONLY the corrected SQL, nothing else.
"""
        try:
            response = self.ollamaClient.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': 'You fix SQL queries. Reply with ONLY the corrected SQL.'},
                    {'role': 'user', 'content': prompt},
                ],
            )
            return self._extractSQL(response['message']['content'])
        except Exception as e:
            print(f"⚠️  Correction failed: {e}")
            return None

    def _extractSQL(self, text: str) -> Optional[str]:
        """Pull a SQL statement out of LLM output."""
        # Code block
        m = re.search(r'```(?:sql)?\s*(.*?)\s*```', text, re.DOTALL)
        if m:
            sql = m.group(1).strip()
        else:
            m = re.search(r'(SELECT\s+.+?)(?:\n\n|$)', text, re.DOTALL | re.IGNORECASE)
            sql = m.group(1).strip() if m else None

        if sql:
            sql = re.sub(r'\s+', ' ', sql).rstrip(';')
        return sql
