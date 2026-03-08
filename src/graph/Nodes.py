#Nodes.py: Defines the nodes used in the LangGraph workflow for SQL generation.


import os
import ollama
from src.graph.State import SQLGenerationState
from src.schemas.SQLAgentSchemas import QueryIntent
from src.utils.helpers import scoreCandidate
from src.utils.constants import K_TEMPERATURES


def generateSqlNode(state: SQLGenerationState, sqlAgent) -> dict:
    """Generate SQL and classify intent at default temperature."""
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


def generateReframedQuestion(original: str, clarification_q: str, user_answer: str) -> str:
    """
    Use a lightweight LLM call to turn a original ambiguous question + the
    clarification info into a single clean, unambiguous question.
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
        #If it fails we just concat the original question with the user's answer to give the next node more to work with, but we don't want this step to be a hard failure point since it's just an enrichment rather than a core part of the pipeline.
        return f"{original} ({user_answer})"


def clarificationNode(state: SQLGenerationState) -> dict:
    """
    Multi-conversational clarification node when user query is ambiguous.
    Prompts the user to resolve the ambiguity and generate a reframed question. ONLY when multiconversational is enabled. 

    """
    clarification_q = state.get('clarificationQuestion', 'Could you clarify your question?')
    print(f"\n🤔 {clarification_q}")

    enriched_question = state['question']
    try:
        user_answer = input("Your answer: ").strip()
        if user_answer:
            enriched_question = generateReframedQuestion(
                original=state['question'],
                clarification_q=clarification_q,
                user_answer=user_answer,
            )
    except Exception:
        print(f"Failed to get user input")
      
    return {
        'question':            enriched_question,
        'multiConversational': False,  
    }


def irrelevantNode(state: SQLGenerationState) -> dict:
    """
    Exit node for queries with no relation to the bike store database.
    """
    print("\n Query has no relevance to the bike store database.")
    return {
        'finalSql': '-- IRRELEVANT_QUERY: This question cannot be answered from the bike store database.',
    }


def ambiguousNode(state: SQLGenerationState) -> dict:
    """
    Handle Ambiguous queries when multi-conversational clarification is disabled. Exit and provide a hint to the user.
    """
    clarification_q = state.get('clarificationQuestion', 'Could you be more specific?')
    print(f"\n\u2753 Query was ambiguous — try being more specific.")
    print(f"   Hint: {clarification_q}")
    return {
        'finalSql': f'-- AMBIGUOUS_QUERY: {clarification_q}',
    }


def kCandidatesNode(state: SQLGenerationState, sqlAgent, validator) -> dict:
    """
    Generate up to K SQL candidates and return the best one that executes and is semantically approved.

    The loop breaks as soon as a candidate both executes and is semantically
    approved. Prevents using lots of LLM calls for easy/medium questions while still allowing hard questions to benefit.
    """
    initial_sql = state.get('sql', '').strip()

    # First slot reuses existing SQL; remaining slots generate at varied temps.
    generation_plan = [(K_TEMPERATURES[0], initial_sql)] + [(t, None) for t in K_TEMPERATURES[1:]]

    print(f"\nGenerating SQL Candidate(s)...")
    candidates = []
    for temp, prebuilt_sql in generation_plan:
        if prebuilt_sql is not None:
            # The Irrelevant, Amgiguous Queries start with --- ONLY, we skip these
            if prebuilt_sql.startswith('--'):
                continue
            sql = prebuilt_sql
        else:
            try:
                result = sqlAgent.generate(state['question'], temperature=temp)
            except Exception:
                continue

            # Re-generations can bypass the graph router with different temps, so AMBIGUOUS/IRRELEVANT must be filtered here directly.
            if result.intent.value != QueryIntent.CLEAR.value or not result.sql.strip():
                continue
            sql = result.sql

        validation = validator.validateSQL(
            question=state['question'],
            sql=sql,
            schemaContext=state['schemaContext'],
        )
        candidates.append({
            'sql':        validation['sql'],
            'validation': validation,
            'score':      scoreCandidate(validation),
        })

        # If candidate executes and is approved, break early
        if validation['execution_ok'] and validation['approved']:
            break

    #Fallback
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

    #take best candidate by score and return its SQL and details
    best = max(candidates, key=lambda c: c['score'])

    if not best['validation']['execution_ok']:
        issues_summary = '; '.join(best['validation'].get('issues', [])[:3]) or 'No viable candidate'
        finalSql = f'-- UNANSWERABLE_QUERY: {issues_summary}'
    else:
        finalSql = best['sql']

    return {
        'sql':        best['sql'],
        'validation': best['validation'],
        'finalSql':   finalSql,
    }
