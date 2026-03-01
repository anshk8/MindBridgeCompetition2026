"""
graph/Nodes.py

Node implementations for the SQL generation LangGraph pipeline.
Each node is a plain function: (state, ...agents) -> dict.
Agents are bound via functools.partial in GraphWorkflow.py at compile time.

Nodes
─────
    generateSqlNode   — generates SQL + classifies intent (Clear/Ambiguous/Irrelevant)
    clarificationNode — prompts user for clarification and loops back to generateSqlNode
    irrelevantNode    — exits early for queries with no relevance to the database
    ambiguousNode     — exits early for ambiguous queries when multiConversational=False
    kCandidatesNode   — generates up to K candidates at varied temperatures, picks best

Helpers
───────
    scoreCandidate  — heuristic scorer for a ValidatorAgent result dict
    K_TEMPERATURES  — temperature schedule used across K candidates (first = default)
"""

# ────────────────────────────────────────────────────────────────── #
# Temperature schedule for K-candidate diversity                     #
# Spread from conservative → creative so at least one low-temp run   #
# is always included regardless of K.                                #
# ────────────────────────────────────────────────────────────────── #

K_TEMPERATURES = [0.7, 0.3, 1.0, 0.5, 0.9, 1.2]

import os
import ollama
from src.graph.State import SQLGenerationState
from src.schemas.SQLAgentSchemas import QueryIntent
from src.schemas.ValidatorAgentSchemas import ValidationResult


# ────────────────────────────────────────────────────────────────── #
# Scoring helper                                                     #
# ────────────────────────────────────────────────────────────────── #

def scoreCandidate(validation: ValidationResult, question: str = '') -> int:
    """
    Heuristic score for a single validated SQL candidate.

    Scoring breakdown:
        +50  executes without error
        +40  approved by semantic review
        +5   returns at least one row
        -3   per execution fix applied by ValidatorAgent
        -3   per semantic fix applied by ValidatorAgent
    """
    score = 0
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



# ────────────────────────────────────────────────────────────────── #
# Nodes                                                              #
# Agents are injected via functools.partial in GraphWorkflow.py.     #
# ────────────────────────────────────────────────────────────────── #

def generateSqlNode(state: SQLGenerationState, sqlAgent) -> dict:
    """Fast path: generate SQL and classify intent at default temperature."""
    try:
        result = sqlAgent.generate(state['question'])
        return {
            'sql':                   result.sql,
            'queryIntent':           result.intent.value,
            'clarificationQuestion': result.clarification_question,
        }
    except Exception as e:
        return {
            'sql':                   f'-- UNANSWERABLE_QUERY: SQL generation failed — {e}',
            'queryIntent':           QueryIntent.CLEAR.value,
            'clarificationQuestion': '',
        }


def _reframeQuestion(original: str, clarification_q: str, user_answer: str) -> str:
    """
    Use a lightweight LLM call to turn the original ambiguous question + the
    clarification Q&A into a single clean, unambiguous question.
    Falls back to simple concatenation if the call fails.
    """
    prompt = (
        "A user asked an ambiguous question about a bike store database. "
        "A clarification question was asked, and the user answered.\n\n"
        f"Original question: {original}\n"
        f"Clarification question: {clarification_q}\n"
        f"User's answer: {user_answer}\n\n"
        "Rewrite the original question as a single clear, specific, unambiguous question "
        "that incorporates the clarification. Output ONLY the rewritten question — no explanation, "
        "no punctuation changes, just the question."
    )
    try:
        client = ollama.Client(host=os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
        model  = os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:14b')
        response = client.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.0},
        )
        reframed = response['message']['content'].strip()
        print(f"🔄 Reframed question: {reframed}")
        return reframed
    except Exception as e:
        print(f"⚠️  Reframing failed ({e}), falling back to concatenation.")
        return f"{original} ({user_answer})"


def clarificationNode(state: SQLGenerationState) -> dict:
    """
    Multi-conversational clarification node.
    Prompts the user to resolve the ambiguity, uses an LLM to reframe the
    original question into a clean unambiguous form, then loops back to
    generateSqlNode for proper re-generation and routing.

    Sets multiConversational=False to prevent infinite clarification loops:
    if the enriched question is still Ambiguous, generateSqlNode will fall
    through to validateNode with best-effort SQL on the next pass.
    """
    clarification_q = state.get('clarificationQuestion', 'Could you clarify your question?')
    print(f"\n🤔 {clarification_q}")

    enriched_question = state['question']
    try:
        user_answer = input("Your answer: ").strip()
        if user_answer:
            enriched_question = _reframeQuestion(
                original=state['question'],
                clarification_q=clarification_q,
                user_answer=user_answer,
            )
    except (EOFError, KeyboardInterrupt):
        # Non-interactive environment — proceed with original question
        pass

    # Return enriched question only; generateSqlNode handles re-generation
    # and all downstream routing (Irrelevant / Ambiguous / Clear).
    return {
        'question':            enriched_question,
        'multiConversational': False,  # prevent re-entry on a second ambiguous result
    }


def irrelevantNode(state: SQLGenerationState) -> dict:
    """
    Exit node for queries with no relation to the bike store database.
    Returns a sentinel finalSql so the caller knows to surface the message.
    """
    print("\n\u274c Query has no relevance to the bike store database.")
    return {
        'finalSql': '-- IRRELEVANT_QUERY: This question cannot be answered from the bike store database.',
    }


def ambiguousNode(state: SQLGenerationState) -> dict:
    """
    Exit node for ambiguous queries when multiConversational=False
    (or on a second clarification pass where mc was reset to False).
    Exits cleanly with a hint so the caller knows to ask the user to rephrase.
    """
    clarification_q = state.get('clarificationQuestion', 'Could you be more specific?')
    print(f"\n\u2753 Query was ambiguous — try being more specific.")
    print(f"   Hint: {clarification_q}")
    return {
        'finalSql': f'-- AMBIGUOUS_QUERY: {clarification_q}',
    }


def kCandidatesNode(state: SQLGenerationState, sqlAgent, validator) -> dict:
    """
    Generate up to K SQL candidates at varied temperatures (K = len(K_TEMPERATURES)),
    validate each, score them, and return the best.
    Exits early as soon as a perfect candidate (executes + approved) is found,
    so easy/medium queries almost always cost exactly one generation.

    The SQL produced by generateSqlNode is reused as the first candidate so
    we never call sqlAgent.generate() twice for the same question at the same
    temperature.
    """
    k = len(K_TEMPERATURES)
    candidates = []

    # ── Step 0: reuse the SQL already produced by generateSqlNode ────────
    # This avoids a redundant second generation for the same question.
    initial_sql = state.get('sql', '').strip()
    if initial_sql:
        print("♻️  Reusing generate result as first candidate...")
        validation = validator.validateSQL(
            question=state['question'],
            sql=initial_sql,
            schemaContext=state['schemaContext'],
        )
        s = scoreCandidate(validation)
        candidates.append({'sql': validation['sql'], 'validation': validation, 'score': s})
        # Early exit: perfect first candidate — skip all further generations
        if validation['execution_ok'] and validation['approved']:
            best = candidates[0]
            return {
                'sql':        best['sql'],
                'validation': best['validation'],
                'finalSql':   best['sql'],
            }

    # ── Steps 1..k-1: generate additional candidates at varied temps ─────
    start_idx = 1 if initial_sql else 0
    for i in range(k - start_idx):
        temp = K_TEMPERATURES[i + start_idx]

        try:
            result = sqlAgent.generate(state['question'], temperature=temp)
        except Exception:
            continue

        # Skip non-Clear or blank candidates — validating them wastes LLM calls
        # and could trigger spurious fix loops on Irrelevant/Ambiguous SQL.
        if result.intent.value != QueryIntent.CLEAR.value or not result.sql.strip():
            continue

        sql = result.sql

        validation = validator.validateSQL(
            question=state['question'],
            sql=sql,
            schemaContext=state['schemaContext'],
        )

        s = scoreCandidate(validation)
        candidates.append({
            'sql':        validation['sql'],
            'validation': validation,
            'score':      s,
        })

        # Early exit: perfect score — no need to generate more
        if validation['execution_ok'] and validation['approved']:
            break

    if not candidates:
        sentinel = '-- UNANSWERABLE_QUERY: All K candidates failed to generate'
        fallback = {
            'approved': False, 'sql': sentinel,
            'exec_fixes': 0, 'semantic_fixes': 0,
            'execution_ok': False, 'row_count': 0,
            'sample_result': None,
            'issues': ['All candidates failed to generate'],
        }
        return {'sql': sentinel, 'validation': fallback, 'finalSql': sentinel}

    best = max(candidates, key=lambda c: c['score'])

    finalSql = best['sql']
    if not best['validation']['approved'] and not best['validation']['execution_ok']:
        issues_summary = '; '.join(best['validation'].get('issues', [])[:3]) or 'No viable candidate'
        finalSql = f'-- UNANSWERABLE_QUERY: {issues_summary}'

    return {
        'sql':        best['sql'],
        'validation': best['validation'],
        'finalSql':   finalSql,
    }
