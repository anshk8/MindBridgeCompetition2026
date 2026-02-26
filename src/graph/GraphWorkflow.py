"""
graph/GraphWorkflow.py

Assembles and compiles the LangGraph pipeline for SQL query generation.
This file is responsible only for graph topology (nodes, edges, routing).
All node logic lives in graph/Nodes.py.

Graph topology
──────────────
                       routeFromStart()
              START ──────────────────────────────────────────┐
                │                                             │
         (kEnabled=True)                              (kEnabled=False)
                │                                             │
                ▼                                             │
      ┌──────────────────┐                                    │
      │    rankNode       │                                    │
      └────────┬─────────┘                                    │
               │                                              │
     routeAfterRank()                                         │
     ┌──────────┴──────────┐                                  │
     │                     │                                  │
(Easy/Medium/Ambiguous)  (Hard)                               │
     │                     ▼                                  │
     │       ┌──────────────────────┐                         │
     │       │   kCandidatesNode    │                         │
     │       │  (K diverse queries, │                         │
     │       │   score & pick best) │                         │
     │       └──────────┬───────────┘                         │
     │                  │                                      │
     ▼                  │                                      │
┌──────────────────┐    │           ◄──────────────────────────┘
│ generateSqlNode  │    │
└────────┬─────────┘    │
         │              │
  routeAfterGenerate()  │
  ┌──────┬──────┬───────┤
  │      │      │       │
Irrel. Ambig Ambig.  Clear
       (mc=T) (mc=F)    │
  │      │      │       ▼
  │      │      │  ┌─────────────┐
  │      │    exit │ validateNode │
  │      │         └──────┬──────┘
  │      ▼                │
  │ clarification         │
  │    Node               │
  │      │ (loop back)    │
  ▼      ▼                ▼
END    genSql            END
"""

from functools import partial
from langgraph.graph import StateGraph, START, END

from src.schemas.DifficultyRankerSchemas import Difficulty
from src.schemas.SQLAgentSchemas import QueryIntent
from src.graph.State import SQLGenerationState
from src.graph.Nodes import (
    rankNode, generateSqlNode, clarificationNode,
    irrelevantNode, ambiguousNode, validateNode, kCandidatesNode,
)


# ────────────────────────────────────────────────────────────────── #
# Routing                                                            #
# ────────────────────────────────────────────────────────────────── #

def routeFromStart(state: SQLGenerationState) -> str:
    """
    Conditional edge from START.
    If kEnabled is False there is no point ranking difficulty — go straight
    to the fast path.  Only visit rankNode when k-candidates are active.
    """
    if state['kEnabled']:
        return 'rankNode'
    return 'generateSqlNode'


def routeAfterRank(state: SQLGenerationState) -> str:
    """
    Conditional edge after rankNode.
    Routes to the K-candidate heavy path when the question is Hard and
    kEnabled is True; otherwise takes the single-query fast path.
    """
    if state['kEnabled'] and state['difficulty'] == Difficulty.HARD.value:
        return 'kCandidatesNode'
    return 'generateSqlNode'


def routeAfterGenerate(state: SQLGenerationState) -> str:
    """
    Conditional edge after generateSqlNode.
    - Irrelevant ALWAYS exits early (regardless of multiConversational flag)
      because sending an empty SQL to the validator causes errors.
    - Ambiguous + multiConversational=True  → clarificationNode (ask user)
    - Ambiguous + multiConversational=False → ambiguousNode (exit with hint)
    - Clear always goes to validateNode.
    """
    intent = state.get('queryIntent', QueryIntent.CLEAR.value)

    if intent == QueryIntent.IRRELEVANT.value:
        return 'irrelevantNode'

    if intent == QueryIntent.AMBIGUOUS.value:
        if state.get('multiConversational', False):
            return 'clarificationNode'
        return 'ambiguousNode'

    return 'validateNode'


# routeAfterClarification is no longer needed:
# clarificationNode enriches the question and loops back to generateSqlNode,
# which handles all routing (Irrelevant / Ambiguous / Clear) as normal.


# ────────────────────────────────────────────────────────────────── #
# Pipeline builder                                                   #
# ────────────────────────────────────────────────────────────────── #

def SqlGenerationPipeline(ranker, sqlAgent, validator):
    """
    Build and compile the SQL generation LangGraph pipeline.

    Agents are bound into each node via functools.partial so every node
    remains a plain function (no closures or factory nesting).

    Args:
        ranker:    DifficultyRankerAgent instance
        sqlAgent:  SQLAgent instance
        validator: ValidatorAgent instance

    Returns:
        Compiled LangGraph (callable via .invoke(state_dict))
    """
    graph = StateGraph(SQLGenerationState)

    graph.add_node('rankNode',          partial(rankNode,          ranker=ranker))
    graph.add_node('generateSqlNode',   partial(generateSqlNode,   sqlAgent=sqlAgent))
    graph.add_node('clarificationNode', clarificationNode)
    graph.add_node('irrelevantNode',    irrelevantNode)
    graph.add_node('ambiguousNode',     ambiguousNode)
    graph.add_node('validateNode',      partial(validateNode,      validator=validator))
    graph.add_node('kCandidatesNode',   partial(kCandidatesNode,   sqlAgent=sqlAgent, validator=validator))

    # ── Edges ─────────────────────────────────────────────────────── #
    # Skip rankNode entirely when kEnabled=False — no reason to classify
    # difficulty if we are always taking the fast path.
    graph.add_conditional_edges(
        START,
        routeFromStart,
        {
            'rankNode':        'rankNode',
            'generateSqlNode': 'generateSqlNode',
        },
    )

    graph.add_conditional_edges(
        'rankNode',
        routeAfterRank,
        {
            'generateSqlNode': 'generateSqlNode',
            'kCandidatesNode': 'kCandidatesNode',
        },
    )

    graph.add_conditional_edges(
        'generateSqlNode',
        routeAfterGenerate,
        {
            'validateNode':      'validateNode',
            'clarificationNode': 'clarificationNode',
            'irrelevantNode':    'irrelevantNode',
            'ambiguousNode':     'ambiguousNode',
        },
    )

    # clarificationNode enriches the question and loops back to generateSqlNode,
    # which handles all routing (Irrelevant / Ambiguous / Clear) as normal.
    graph.add_edge('clarificationNode', 'generateSqlNode')
    graph.add_edge('validateNode',    END)
    graph.add_edge('irrelevantNode',  END)
    graph.add_edge('ambiguousNode',   END)
    graph.add_edge('kCandidatesNode', END)

    return graph.compile()
