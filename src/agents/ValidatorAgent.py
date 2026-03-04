#ValidatorAgent.py: Validate Execution and Semantics of SQL Queries with LLM Feedback Loops


import os
import ollama
from typing import Dict, Any, Optional
from src.utils.helpers import executeSQL
from src.utils.prompts import (
    buildSemanticReviewPrompt,
    buildCorrectionPrompt,
    buildReviewerSystemPrompt,
    buildFixerSystemPrompt,
)
from src.schemas.ValidatorAgentSchemas import ReviewResult, FixResult, ValidationResult
from src.utils.constants import MAX_EXEC_FIXES, MAX_SEMANTIC_FIXES

class ValidatorAgent:
    def __init__(self, dbPath: str):
        self.dbPath = dbPath
        self.model  = os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:14b')
        self.ollamaClient = ollama.Client(
            host=os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        )


    def validateSQL(self, question: str, sql: str, schemaContext: str) -> ValidationResult:
        """
        Two-phase validation pipeline:
        1. Execution Verify
        2. Semantic Review

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

        # Get the SQL to execute
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


    def verifyExecution(
        self,
        question: str,
        sql: str,
        schemaContext: str,
        issues: list,
    ):
        """
        Try to execute SQL and fix with LLM on failure.
        Returns (final_sql, fixes_used, last_exec_result).
        """

        attempt = 0
        while attempt <= MAX_EXEC_FIXES:  
            result = executeSQL(self.dbPath, sql)

            if result['success']:
                return sql, attempt, result

            # Execution failed
            error_msg = result['error']
            issues.append(f"Exec error (attempt {attempt}): {error_msg}")

            # No more fixes allowed
            if attempt >= MAX_EXEC_FIXES:
                break  

            # Fix SQL with LLM
            fixed = self.fixSQL(question, sql, error_msg, schemaContext)
            if not fixed or fixed == sql:
                break
            sql = fixed

            attempt += 1

        return sql, attempt, result


    def reviewSqlOutput(
        self,
        question: str,
        sql: str,
        schemaContext: str,
        exec_result: Dict,
        issues: list,
    ):
        """
        Review SQL to ensure it matches question intent
        Returns (final_sql, fixes_used, approved, last_exec_result).
        """
        for attempt in range(MAX_SEMANTIC_FIXES + 1):  
            review = self.semanticReview(question, sql, schemaContext)

            # Approved as-is
            if review['approved']:
                return sql, attempt, True, exec_result

            # Rejected
            issues.extend(review.get('issues', []))

            # No more fixes allowed
            if attempt == MAX_SEMANTIC_FIXES:
                break  

            # Get corrected SQL — prefer reviewer's suggestion, else ask LLM
            fixed = review.get('suggestion') or self.fixSQL(
                question, sql,
                "; ".join(review.get('issues', ['Semantic issues'])),
                schemaContext,
            )

            #Nothing was fixed avoid executing
            if not fixed or fixed == sql:
                break

            # Execute fixed SQL before next review
            new_result = executeSQL(self.dbPath, fixed)

            # If the fix broke execution, revert and skip further fixes
            if not new_result['success']:
                issues.append(f"Semantic fix failed execution: {new_result['error']}")
                break  

            sql = fixed
            exec_result = new_result

        return sql, attempt, False, exec_result

    def semanticReview(self, question: str, sql: str, schemaContext: str) -> Dict[str, Any]:
        """Ask LLM to review if outputted SQL correctly answers the question of the user."""
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
            return {'approved': False, 'issues': [f'Review error: {e}'], 'suggestion': None}

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
            return None


    #This is to have a faliure fallback
    def returnFailedFallback(
        self,
        sql: str,
        exec_fixes: int,
        semantic_fixes: int,
        exec_result: Dict,
        issues: list,
    ) -> ValidationResult:
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
