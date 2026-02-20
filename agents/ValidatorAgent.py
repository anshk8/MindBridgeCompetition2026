"""
ValidatorAgent.py - SQL Validation Pipeline

Phase 1: Execution correction  (max 2 LLM fix attempts)
Phase 2: Semantic review        (max 2 LLM review+fix attempts)

Flow:
    execute → [fix loop max 2] → semantic review → [fix loop max 2] → return
"""

import os
import ollama
from typing import Dict, Any, Optional
from utils.helpers import executeSQL
from utils.prompts import (
    buildSemanticReviewPrompt,
    buildCorrectionPrompt,
    buildReviewerSystemPrompt,
    buildFixerSystemPrompt,
)
from schemas.ValidatorAgentSchemas import ReviewResult, FixResult


class ValidatorAgent:

    #Constants for max attempts in each phase
    MAX_EXEC_FIXES     = 2   # max LLM calls to fix execution errors
    MAX_SEMANTIC_FIXES = 2   # max LLM review+fix cycles

    def __init__(self, dbPath: str):
        self.dbPath = dbPath
        self.model  = os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:14b')
        self.ollamaClient = ollama.Client(
            host=os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        )


    def validateSQL(self, question: str, sql: str, schemaContext: str) -> Dict[str, Any]:
        """
        Two-phase validation pipeline.

        Phase 1 — Execution:
            Try to execute SQL. If it fails, ask LLM to fix it.
            Repeat at most MAX_EXEC_FIXES times.
            If still failing → return failure result immediately.

        Phase 2 — Semantic review:
            SQL executes. Ask LLM if it correctly answers the question.
            If rejected, ask LLM for a corrected version and re-execute.
            Repeat at most MAX_SEMANTIC_FIXES times.

        Returns:
            approved        bool   — True only if semantic review passed
            sql             str    — final SQL (possibly corrected)
            exec_fixes      int    — how many execution fixes were needed
            semantic_fixes  int    — how many semantic fixes were needed
            execution_ok    bool   — does final SQL execute?
            row_count       int    — rows returned by final SQL
            sample_result   str    — first row as string (or None)
            issues          list   — collected warnings / errors
        """
        issues: list[str] = []

        # ── Phase 1: Get the SQL to execute ──────────────────────────── #
        sql, exec_fixes, exec_result = self.verifyExecution(
            question, sql, schemaContext, issues
        )

        if not exec_result['success']:
            # Still broken after all fixes — give up
            return self.returnFailedFallback(sql, exec_fixes, 0, exec_result, issues)

        # ── Phase 2: Semantic review ──────────────────────────────────── #
        sql, semantic_fixes, approved, exec_result = self.reviewSqlOutput(
            question, sql, schemaContext, exec_result, issues
        )

        return {
            'approved':       approved,
            'sql':            sql,
            'exec_fixes':     exec_fixes,
            'semantic_fixes': semantic_fixes,
            'execution_ok':   exec_result['success'],
            'row_count':      exec_result.get('row_count', 0),
            'sample_result':  exec_result.get('sample_result'),
            'issues':         issues,
        }

    # ------------------------------------------------------------------ #
    # Phase 1 — Execution                                                 #
    # ------------------------------------------------------------------ #

    def verifyExecution(
        self,
        question: str,
        sql: str,
        schemaContext: str,
        issues: list,
    ):
        """
        Try to execute SQL; fix with LLM on failure.
        Returns (final_sql, fixes_used, last_exec_result).
        """

        attempt = 0
        while attempt <= self.MAX_EXEC_FIXES:  # ✅ Changed < to <= so we try the last fix
            result = executeSQL(self.dbPath, sql)

            if result['success']:
                if attempt > 0:
                    print(f"✅ Execution fix succeeded after {attempt} fix(es)")
                return sql, attempt, result

            # Execution failed
            error_msg = result['error']
            issues.append(f"Exec error (attempt {attempt}): {error_msg}")
            print(f"❌ Execution failed (attempt {attempt}): {error_msg}")

            # Check if we can still fix
            if attempt >= self.MAX_EXEC_FIXES:
                break  # No more fixes allowed

            # Ask LLM to fix it
            fixed = self.fixSQL(question, sql, error_msg, schemaContext)
            if not fixed or fixed == sql:
                print("⚠️  LLM could not produce a different SQL — stopping exec fixes")
                break
            sql = fixed

            attempt += 1

        return sql, attempt, result

    # ------------------------------------------------------------------ #
    # Phase 2 — Semantic Review                                           #
    # ------------------------------------------------------------------ #

    def reviewSqlOutput(
        self,
        question: str,
        sql: str,
        schemaContext: str,
        exec_result: Dict,
        issues: list,
    ):
        """
        Review SQL semantics; fix and re-execute if rejected.
        Returns (final_sql, fixes_used, approved, last_exec_result).
        """
        for attempt in range(self.MAX_SEMANTIC_FIXES + 1):  
            review = self.semanticReview(question, sql, schemaContext)

            if review['approved']:
                print(f"✅ Semantic review approved (attempt {attempt})")
                return sql, attempt, True, exec_result

            # Rejected
            issues.extend(review.get('issues', []))
            print(f"⚠️  Semantic review rejected (attempt {attempt}): {review.get('issues')}")

            if attempt == self.MAX_SEMANTIC_FIXES:
                break  # No more fixes allowed

            # Get corrected SQL — prefer reviewer's suggestion, else ask LLM
            fixed = review.get('suggestion') or self.fixSQL(
                question, sql,
                "; ".join(review.get('issues', ['Semantic issues'])),
                schemaContext,
            )

            if not fixed or fixed == sql:
                print("⚠️  No new SQL from semantic fix — stopping")
                break

            # Re-execute the new SQL before next review
            new_result = executeSQL(self.dbPath, fixed)
            if not new_result['success']:
                issues.append(f"Semantic fix failed execution: {new_result['error']}")
                print(f"❌ Semantic fix broke execution — reverting")
                break  # Don't use a broken fix

            sql = fixed
            exec_result = new_result

        return sql, attempt, False, exec_result

    # ------------------------------------------------------------------ #
    # LLM helpers                                                         #
    # ------------------------------------------------------------------ #

    def semanticReview(self, question: str, sql: str, schemaContext: str) -> Dict[str, Any]:
        """Ask LLM if SQL correctly answers the question."""
        prompt = buildSemanticReviewPrompt(question, sql, schemaContext)
        try:
            response = self.ollamaClient.chat(
                model=self.model,
                format=ReviewResult.model_json_schema(),
                messages=[
                    {'role': 'system', 'content': buildReviewerSystemPrompt()},
                    {'role': 'user',   'content': prompt},
                ],
            )
            result = ReviewResult.model_validate_json(response['message']['content'])
            suggestion = None
            if result.corrected_sql:
                suggestion = result.corrected_sql.rstrip(';')
            return {'approved': result.approved, 'issues': result.issues, 'suggestion': suggestion}
        except Exception as e:
            print(f"⚠️  Semantic review error: {e}")
            # Fail open — don't block valid SQL just because reviewer errored
            return {'approved': True, 'issues': [f'Review error: {e}'], 'suggestion': None}

    def fixSQL(
        self, question: str, failedSQL: str, error: str, schemaContext: str
    ) -> Optional[str]:
        """Ask LLM to fix a broken or rejected SQL query."""
        prompt = buildCorrectionPrompt(question, failedSQL, error, schemaContext)
        try:
            response = self.ollamaClient.chat(
                model=self.model,
                format=FixResult.model_json_schema(),
                messages=[
                    {'role': 'system', 'content': buildFixerSystemPrompt()},
                    {'role': 'user',   'content': prompt},
                ],
            )
            result = FixResult.model_validate_json(response['message']['content'])
            return result.sql.rstrip(';')
        except Exception as e:
            print(f"⚠️  LLM fix error: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Result builder                                                       #
    # ------------------------------------------------------------------ #

    def returnFailedFallback(
        self,
        sql: str,
        exec_fixes: int,
        semantic_fixes: int,
        exec_result: Dict,
        issues: list,
    ) -> Dict[str, Any]:
        """Build a failure result dict when execution never succeeded."""
        return {
            'approved':       False,
            'sql':            sql,
            'exec_fixes':     exec_fixes,
            'semantic_fixes': semantic_fixes,
            'execution_ok':   False,
            'row_count':      0,
            'sample_result':  None,
            'issues':         issues,
        }
