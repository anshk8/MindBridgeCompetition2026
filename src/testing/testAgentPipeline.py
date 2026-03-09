"""
testAgentPipeline.py 

Invokes QueryWriter.generate_query() exactly as the competition evaluator would,
then prints the final LangGraph state and saves all results to a JSON file.
"""

import sys
import os
import json
import time
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent import QueryWriter
from src.testing.queriesToTest import ALL_QUERIES
from src.testing.queriesToTest import MIXED_QUERIES
from src.testing.queriesToTest import TEST_MULTICONVERSATION_QUERIES
from src.testing.queriesToTest import FINAL_TEST_BANK

# ── Configure which categories to run ─────────────────────────────── #
# CATEGORIES = ['easy', 'medium', 'hard', 'hard_advanced', 'ambiguous', 'nonsense']
# CATEGORIES = ['medium','hard_advanced', 'ambiguous', 'nonsense']  # focus on more challenging categories for testing
# CATEGORIES = ['clarification', 'irrelevant']  # focus on challenging categories for testing

#For FINAL_TEST_BANK
CATEGORIES = ['all']  

def run(categories: list[str] = CATEGORIES) -> list[dict]:
    writer = QueryWriter()
    writer.multi_conversational_enabled = False   # match competition evaluation mode

    results = []

    for category in categories:
        queries = FINAL_TEST_BANK.get(category, [])
        if not queries:
            continue

        print(f'\n── {category.upper()} ({"─" * (60 - len(category))})')

        for q in queries:
            t0 = time.monotonic()
            sql = writer.generate_query(q['question'])
            elapsed_min = round((time.monotonic() - t0) / 60, 4)
            state: dict = getattr(writer, '_lastGraphResult', {}) or {}
            validation: dict = state.get('validation') or {}

            record = {
                'id':            q['id'],
                'category':      category,
                'question':      q['question'],
                'expected_sql':  q.get('expected_sql'),
                'generated_sql': sql,
                'time_minutes':  elapsed_min,
                'graph_state': {
                    'queryIntent':    state.get('queryIntent'),
                    'finalSql':       state.get('finalSql'),
                    'approved':       validation.get('approved'),
                    'execution_ok':   validation.get('execution_ok'),
                    'row_count':      validation.get('row_count'),
                    'exec_fixes':     validation.get('exec_fixes'),
                    'semantic_fixes': validation.get('semantic_fixes'),
                    'issues':         validation.get('issues', []),
                },
            }
            results.append(record)

            gs = record['graph_state']
            print(f"\n[{q['id']}] {q['question']}")
            print(f"  intent   : {gs['queryIntent']}")
            print(f"  sql      : {sql[:120]}")
            print(f"  approved : {gs['approved']}  |  exec_ok: {gs['execution_ok']}  |  rows: {gs['row_count']}")
            print(f"  time     : {elapsed_min} min")
            if gs['exec_fixes'] or gs['semantic_fixes']:
                print(f"  fixes    : exec={gs['exec_fixes']}  semantic={gs['semantic_fixes']}")
            if gs['issues']:
                print(f"  issues   : {gs['issues'][:2]}")

    fname = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path = os.path.join(PROJECT_ROOT, fname)
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f'\nResults saved → {fname}\n')

    return results


if __name__ == '__main__':
    run()

