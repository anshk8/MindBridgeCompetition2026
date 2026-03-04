"""
visualize_graph.py — Render the LangGraph pipeline to a PNG image.

Compiles the graph topology without starting any LLM agents, then saves
graph.png in the project root using LangGraph's built-in Mermaid renderer.

Run:
    python visualize_graph.py
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.graph.GraphWorkflow import SqlGenerationPipeline

OUTPUT = os.path.join(PROJECT_ROOT, 'graph.png')


def main():
    # Pass None for agents — graph structure is independent of agent instances.
    graph = SqlGenerationPipeline(sqlAgent=None, validator=None)

    png_bytes: bytes = graph.get_graph().draw_mermaid_png()

    with open(OUTPUT, 'wb') as f:
        f.write(png_bytes)

    print(f"Graph saved → {OUTPUT}")


if __name__ == '__main__':
    main()
