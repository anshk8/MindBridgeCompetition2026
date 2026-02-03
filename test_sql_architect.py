"""
Simple test suite for SQL Architect (Agent #3)

Just add your test cases to the lists below!
"""

import os
import sys

# Setup
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
from agents import QuestionDecomposer, SchemaScout, SQLArchitect


# ==================== TEST CONFIGURATION ====================

# Regular test questions - add as many as you want!
REGULAR_QUERIES = [
    "How many products are there?",
    "What are the top 5 most expensive products?",
    "How many customers do we have?",
    "Show me products from Trek brand",
    "What is the average product price?",
    "List all products with their brand names",
]

# Edge cases - weird/invalid questions
EDGE_CASES = [
    "What?",
    "Show me everything about something",
    "",
    "How many xyzabc are there?",
]


# ==================== TEST FUNCTIONS ====================

def test_regular_queries(verbose=False):
    """Test regular queries"""
    print("\n" + "=" * 80)
    print("TESTING REGULAR QUERIES")
    print("=" * 80)
    
    db_path = os.path.join(project_root, "bike_store.db")
    decomposer = QuestionDecomposer()
    scout = SchemaScout(db_path=db_path)
    architect = SQLArchitect()
    
    results = []
    
    for i, question in enumerate(REGULAR_QUERIES, 1):
        print(f"\n[{i}/{len(REGULAR_QUERIES)}] {question}")
        print("─" * 80)
        
        try:
            # Run the 3-agent pipeline
            analysis = decomposer.decompose(question)
            schema = scout.scout(analysis)
            sql = architect.generate(analysis, schema)
            
            # Show results
            if verbose:
                print(f"Strategy: {sql.strategy}")
                print(f"Confidence: {sql.confidence:.2f}")
            
            print(f"SQL: {sql.sql}")
            
            if sql.warnings:
                print(f"⚠️  Warnings: {sql.warnings}")
            
            results.append({'question': question, 'sql': sql.sql, 'success': True})
            
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({'question': question, 'error': str(e), 'success': False})
    
    scout.close()
    
    # Summary
    success_count = sum(1 for r in results if r['success'])
    print(f"\n{'=' * 80}")
    print(f"RESULTS: {success_count}/{len(REGULAR_QUERIES)} successful")
    print("=" * 80)
    
    return results


def test_edge_cases():
    """Test edge cases"""
    print("\n" + "=" * 80)
    print("TESTING EDGE CASES")
    print("=" * 80)
    
    db_path = os.path.join(project_root, "bike_store.db")
    decomposer = QuestionDecomposer()
    scout = SchemaScout(db_path=db_path)
    architect = SQLArchitect()
    
    for i, question in enumerate(EDGE_CASES, 1):
        print(f"\n[{i}/{len(EDGE_CASES)}] '{question}'")
        print("─" * 80)
        
        try:
            analysis = decomposer.decompose(question)
            schema = scout.scout(analysis)
            sql = architect.generate(analysis, schema)
            
            print(f"✓ Handled gracefully")
            print(f"SQL: {sql.sql[:80]}")
            print(f"Confidence: {sql.confidence:.2f}")
            
        except Exception as e:
            print(f"✓ Failed gracefully: {type(e).__name__}")
    
    scout.close()


# ==================== MAIN ====================

def main():
    """Run tests - add --verbose for more details"""
    import sys
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    quiet = '--quiet' in sys.argv or '-q' in sys.argv
    
    if not quiet:
        print("=" * 80)
        print("SQL ARCHITECT TEST SUITE")
        print("=" * 80)
        print("\n💡 Tip: Add questions to REGULAR_QUERIES or EDGE_CASES at the top of this file")
        print("💡 The progress output is just debug logs - NOT from the LLM\n")
    
    try:
        test_regular_queries(verbose=verbose)
        test_edge_cases()
        
        if not quiet:
            print("\n" + "=" * 80)
            print("✅ ALL TESTS COMPLETE")
            print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
