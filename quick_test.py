"""
Quick Test Script - Test Custom Questions

Paste your questions in the QUESTIONS array below and run to see results.
"""

import os
import json
from datetime import datetime
from agents.questionDecomposerAgent import QuestionDecomposer
from agents.schemaExpert import SchemaScout
from agents.SQLAgent import SQLArchitect

# ==================== PASTE YOUR QUESTIONS HERE ====================

QUESTIONS = [
    "Show me all brands",
    "How many customers are there?",
    "List all product categories",
    # Add more questions here...
]

# ===================================================================


def test_questions(questions: list):
    """Run pipeline on custom questions"""
    
    # Initialize agents
    print("🚀 Initializing agents...")
    agent1 = QuestionDecomposer()
    agent2 = SchemaScout(db_path='bike_store.db')
    agent3 = SQLArchitect()
    print("✅ Agents ready\n")
    
    results = []
    
    print("="*80)
    print(f"Testing {len(questions)} questions")
    print("="*80)
    
    for i, question in enumerate(questions, 1):
        print(f"\n{'='*80}")
        print(f"Test #{i}")
        print(f"Question: {question}")
        
        try:
            # Run pipeline
            analysis = agent1.decompose(question)
            schema = agent2.scout(analysis)
            sql = agent3.generate(analysis, schema)
            
            print(f"Generated: {sql.sql}")
            
            results.append({
                'test_num': i,
                'question': question,
                'generated_sql': sql.sql,
                'confidence': sql.confidence,
                'success': True
            })
            
        except Exception as e:
            print(f"Error: {e}")
            results.append({
                'test_num': i,
                'question': question,
                'generated_sql': 'ERROR',
                'error': str(e),
                'success': False
            })
        
        print('='*80)
    
    # Summary
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    successful = sum(1 for r in results if r['success'])
    print(f"Successful: {successful}/{len(results)}")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"quick_test_results_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to: {output_file}")
    print("="*80)
    
    # Cleanup
    agent2.close()


if __name__ == "__main__":
    if not QUESTIONS:
        print("❌ No questions found! Add questions to the QUESTIONS array.")
    else:
        test_questions(QUESTIONS)
