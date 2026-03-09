"""
visualize_graph.py — Render the LangGraph pipeline to a PNG image. Image gets put inside ROOT directory as graph.png
Run:
    python visualize_graph.py / python3 visualize_graph.py
"""

import os
from src.graph.GraphWorkflow import SqlGenerationPipeline

# Walk up from src/graph/visualization/ to the repo root (contains src/)
_HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(_HERE, 'graph.png')


def main():
    # Pass None for agents — graph structure is independent of agent instances.
    graph = SqlGenerationPipeline(sqlAgent=None, validator=None)

    png_bytes: bytes = graph.get_graph().draw_mermaid_png()

    with open(OUTPUT, 'wb') as f:
        f.write(png_bytes)

    print(f"Graph saved → {OUTPUT}")


if __name__ == '__main__':
    main()
