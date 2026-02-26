"""
graph/Nodes.py

Node implementations for the SQL generation LangGraph pipeline.
Each node is a plain function: (state, ...agents) -> dict.
Agents are bound via functools.partial in GraphWorkflow.py at compile time.

Nodes
─────
    rankNode         — classifies question difficulty via DifficultyRankerAgent
    generateSqlNode  — generates a single SQL query via SQLAgent  (fast path)
    validateNode     — validates/corrects SQL via ValidatorAgent   (fast path)
    kCandidatesNode  — generates K candidates, scores, picks best  (hard path)

Helpers
───────
    scoreCandidate  — heuristic scorer for a ValidatorAgent result dict
    K_TEMPERATURES  — temperature schedule used across K candidates
"""

from src.graph.State import SQLGenerationState


# ────────────────────────────────────────────────────────────────── #
# Scoring helper                                                     #
# ────────────────────────────────────────────────────────────────── #

def scoreCandidate(validation: dict) -> int:
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
# Temperature schedule for K-candidate diversity                     #
# Spread from conservative → creative so at least one low-temp run   #
# is always included regardless of K.                                #
# ────────────────────────────────────────────────────────────────── #

K_TEMPERATURES = [0.3, 0.7, 1.0, 0.5, 0.9, 1.2]


# ────────────────────────────────────────────────────────────────── #
# Nodes                                                              #
# Agents are injected via functools.partial in GraphWorkflow.py.     #
# ────────────────────────────────────────────────────────────────── #

def rankNode(state: SQLGenerationState, ranker) -> dict:
    """Classify question difficulty and record which tables are needed."""
    result = ranker.rank(state['question'])
    return {
        'difficulty':   result.difficulty.value,
        'tablesNeeded': result.tables_needed,
    }


def generateSqlNode(state: SQLGenerationState, sqlAgent) -> dict:
    """Fast path: generate a single SQL query at default temperature."""
    sql = sqlAgent.generate(state['question'])
    return {'sql': sql}


def validateNode(state: SQLGenerationState, validator) -> dict:
    """
    Fast path: validate execution + semantics, apply corrections if needed.
    Falls back to 'SELECT 1' if SQL cannot be made to execute.
    """
    validation = validator.validateSQL(
        question=state['question'],
        sql=state['sql'],
        schemaContext=state['schemaContext'],
    )
    finalSql = validation['sql']
    if not validation['approved'] and not validation['execution_ok']:
        finalSql = 'SELECT 1'
    return {
        'validation': validation,
        'finalSql':   finalSql,
    }


def kCandidatesNode(state: SQLGenerationState, sqlAgent, validator) -> dict:
    """
    Heavy path: generate K SQL candidates at varied temperatures, validate
    each, score them, and return the best.
    Exits early if a perfect candidate (executes + approved) is found.
    """
    k = state['kCount']

    candidates = []

    for i in range(k):
        temp = K_TEMPERATURES[i % len(K_TEMPERATURES)]

        try:
            sql = sqlAgent.generate(state['question'], temperature=temp)
        except Exception as e:
            continue

        validation = validator.validateSQL(
            question=state['question'],
            sql=sql,
            schemaContext=state['schemaContext'],
        )

        s = scoreCandidate(validation)

        candidates.append({
            'sql':        validation['sql'],  # may have been corrected by validator
            'validation': validation,
            'score':      s,
        })

        # Early exit: perfect score — no need to generate more
        if validation['execution_ok'] and validation['approved']:
            break

    if not candidates:
        fallback = {
            'approved': False, 'sql': 'SELECT 1',
            'exec_fixes': 0, 'semantic_fixes': 0,
            'execution_ok': False, 'row_count': 0,
            'sample_result': None,
            'issues': ['All candidates failed to generate'],
        }
        return {'sql': 'SELECT 1', 'validation': fallback, 'finalSql': 'SELECT 1'}

    best = max(candidates, key=lambda c: c['score'])

    finalSql = best['sql']
    if not best['validation']['approved'] and not best['validation']['execution_ok']:
        finalSql = 'SELECT 1'

    return {
        'sql':        best['sql'],
        'validation': best['validation'],
        'finalSql':   finalSql,
    }
