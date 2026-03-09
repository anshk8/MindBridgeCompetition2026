#GraphWorkflow.py: Defines the SQL generation workflow as a LangGraph StateGraph.

from functools import partial
from langgraph.graph import StateGraph, START, END

from src.schemas.SQLAgentSchemas import QueryIntent
from src.graph.State import SQLGenerationState
from src.graph.Nodes import (
    generateSqlNode, clarificationNode,
    irrelevantNode, ambiguousNode, kCandidatesNode,
)


#Helper function for the graph routing
def routeAfterGenerate(state: SQLGenerationState) -> str:
    """
    Conditional edge after generateSqlNode.
    - Irrelevant                           → irrelevantNode  (exit early)
    - Ambiguous + multiConversational=True → clarificationNode (ask user)
    - Ambiguous + multiConversational=False → ambiguousNode (exit with hint)
    - Clear                                → kCandidatesNode (always)
    """
    intent = state.get('queryIntent', QueryIntent.CLEAR.value)

    if intent == QueryIntent.IRRELEVANT.value:
        return 'irrelevantNode'

    if intent == QueryIntent.AMBIGUOUS.value:
        if state.get('multiConversational', False):
            return 'clarificationNode'
        return 'ambiguousNode'

    return 'kCandidatesNode'


#Build the LangGraph pipeline with nodes and edges and compile for use
def SqlGenerationPipeline(sqlAgent, validator):
    """
    Build and compile the SQL generation LangGraph pipeline.

    Args:
        sqlAgent:  SQLAgent instance
        validator: ValidatorAgent instance

    Returns:
        Compiled LangGraph (callable via .invoke(state_dict))
    """
    graph = StateGraph(SQLGenerationState)

    graph.add_node('generateSqlNode',   partial(generateSqlNode,   sqlAgent=sqlAgent))
    graph.add_node('clarificationNode', clarificationNode)
    graph.add_node('irrelevantNode',    irrelevantNode)
    graph.add_node('ambiguousNode',     ambiguousNode)
    graph.add_node('kCandidatesNode',   partial(kCandidatesNode,   sqlAgent=sqlAgent, validator=validator))

    # ── Edges ─────────────────────────────────────────────────────── #
    graph.add_edge(START, 'generateSqlNode')

    graph.add_conditional_edges(
        'generateSqlNode',
        routeAfterGenerate,
        {
            'clarificationNode': 'clarificationNode',
            'irrelevantNode':    'irrelevantNode',
            'ambiguousNode':     'ambiguousNode',
            'kCandidatesNode':   'kCandidatesNode',
        },
    )

    # clarificationNode enriches the question and loops back to generateSqlNode,
    # which handles all routing (Irrelevant / Ambiguous / Clear) as normal.
    graph.add_edge('clarificationNode', 'generateSqlNode')
    graph.add_edge('irrelevantNode',  END)
    graph.add_edge('ambiguousNode',   END)
    graph.add_edge('kCandidatesNode', END)

    return graph.compile()
