"""
Agent Pipeline Testing Suite

This script tests the complete three-agent pipeline:
- Agent #1: Question Decomposer (Natural Language Understanding)
- Agent #2: Schema Scout (Database Intelligence)
- Agent #3: SQL Architect (Query Generation)

Shows input/output at each stage to identify where errors occur.
"""

import os
import json
import sys
from typing import Dict, Any
from datetime import datetime

# Import all three agents
from agents.questionDecomposerAgent import QuestionDecomposer, QuestionAnalysis
from agents.schemaExpert import SchemaScout, SchemaContext
from agents.SQLAgent import SQLArchitect, SQLQuery


# ==================== TEST QUERIES ====================

TEST_QUERIES = {
    "easy": [
        {
            "id": "E1",
            "question": "Show me all brands",
            "expected_sql": "SELECT * FROM brands",
            "notes": "Simple SELECT, single table, no conditions"
        },
        {
            "id": "E2",
            "question": "How many customers are there?",
            "expected_sql": "SELECT COUNT(*) FROM customers",
            "notes": "Simple COUNT aggregation"
        },
        {
            "id": "E3",
            "question": "List all product categories",
            "expected_sql": "SELECT category_name FROM categories",
            "notes": "Simple SELECT with specific column"
        },
        {
            "id": "E4",
            "question": "What stores do we have?",
            "expected_sql": "SELECT store_name, city, state FROM stores",
            "notes": "Simple SELECT, multiple columns"
        },
        {
            "id": "E5",
            "question": "Show me products with price greater than 500",
            "expected_sql": "SELECT product_name, list_price FROM products WHERE list_price > 500",
            "notes": "Simple filtering with WHERE clause"
        }
    ],
    
    "medium": [
        {
            "id": "M1",
            "question": "What are the top 5 most expensive products?",
            "expected_sql": "SELECT product_name, list_price FROM products ORDER BY list_price DESC LIMIT 5",
            "notes": "ORDER BY + LIMIT"
        },
        {
            "id": "M2",
            "question": "Find customers in New York",
            "expected_sql": "SELECT first_name, last_name, city, state FROM customers WHERE state = 'NY'",
            "notes": "Filtering with string comparison"
        },
        {
            "id": "M3",
            "question": "How many products are in each category?",
            "expected_sql": "SELECT c.category_name, COUNT(p.product_id) FROM categories c LEFT JOIN products p ON c.category_id = p.category_id GROUP BY c.category_name",
            "notes": "GROUP BY with JOIN"
        },
        {
            "id": "M4",
            "question": "What is the average product price?",
            "expected_sql": "SELECT AVG(list_price) FROM products",
            "notes": "Aggregation function (AVG)"
        },
        {
            "id": "M5",
            "question": "Show me customer names with their order details",
            "expected_sql": "SELECT c.first_name, c.last_name, o.order_id, o.order_date FROM customers c JOIN orders o ON c.customer_id = o.customer_id",
            "notes": "Multi-table JOIN"
        }
    ],
    
    "hard": [
        {
            "id": "H1",
            "question": "Which store has the most inventory?",
            "expected_sql": "SELECT s.store_name, SUM(st.quantity) as total_inventory FROM stores s JOIN stocks st ON s.store_id = st.store_id GROUP BY s.store_id, s.store_name ORDER BY total_inventory DESC LIMIT 1",
            "notes": "JOIN + GROUP BY + ORDER BY + LIMIT"
        },
        {
            "id": "H2",
            "question": "What is the total revenue by brand?",
            "expected_sql": "SELECT b.brand_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as total_revenue FROM brands b JOIN products p ON b.brand_id = p.brand_id JOIN order_items oi ON p.product_id = oi.product_id GROUP BY b.brand_name ORDER BY total_revenue DESC",
            "notes": "Multi-table JOIN + complex aggregation"
        },
        {
            "id": "H3",
            "question": "Find customers who have never placed an order",
            "expected_sql": "SELECT first_name, last_name, email FROM customers WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders)",
            "notes": "Subquery with NOT IN"
        },
        {
            "id": "H4",
            "question": "List all products and their available stock quantities by store",
            "expected_sql": "SELECT p.product_name, s.store_name, st.quantity FROM products p JOIN stocks st ON p.product_id = st.product_id JOIN stores s ON st.store_id = s.store_id",
            "notes": "Three-table JOIN"
        },
        {
            "id": "H5",
            "question": "Show the top 10 customers by total purchase amount",
            "expected_sql": "SELECT c.first_name, c.last_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as total_spent FROM customers c JOIN orders o ON c.customer_id = o.customer_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY c.customer_id, c.first_name, c.last_name ORDER BY total_spent DESC LIMIT 10",
            "notes": "Complex multi-table JOIN + aggregation + LIMIT"
        }
    ]
}


# ==================== AGENT PIPELINE RUNNER ====================

class AgentPipelineTester:
    """
    Runs queries through the complete agent pipeline and tracks results.
    """
    
    def __init__(self, db_path: str = 'bike_store.db'):
        """Initialize all three agents"""
        print("🚀 Initializing agents...")
        self.agent1 = QuestionDecomposer()
        self.agent2 = SchemaScout(db_path=db_path)
        self.agent3 = SQLArchitect()
        print("✅ All agents initialized\n")
    
    def run_test(self, test_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single query through the complete pipeline.
        
        Returns detailed results at each stage.
        """
        question = test_query['question']
        
        result = {
            'test_id': test_query['id'],
            'question': question,
            'expected_sql': test_query.get('expected_sql', 'N/A'),
            'notes': test_query.get('notes', ''),
            'stages': {},
            'errors': []
        }
        
        try:
            # ==================== AGENT #1: QUESTION DECOMPOSER ====================
            print(f"\n{'='*80}")
            print(f"📝 AGENT #1: QUESTION DECOMPOSER")
            print(f"{'='*80}")
            print(f"INPUT: {question}")
            
            agent1_output = self.agent1.decompose(question)
            
            result['stages']['agent1'] = {
                'input': question,
                'output': {
                    'query_type': agent1_output.query_type,
                    'entities': agent1_output.entities,
                    'filters': agent1_output.filters,
                    'aggregations': agent1_output.aggregations,
                    'ordering': agent1_output.ordering,
                    'limit': agent1_output.limit,
                    'confidence': agent1_output.confidence
                },
                'status': 'success'
            }
            
            print(f"\nOUTPUT:")
            print(f"  ├─ Query Type: {agent1_output.query_type}")
            print(f"  ├─ Entities: {agent1_output.entities}")
            print(f"  ├─ Filters: {agent1_output.filters}")
            print(f"  ├─ Aggregations: {agent1_output.aggregations}")
            print(f"  ├─ Ordering: {agent1_output.ordering}")
            print(f"  ├─ Limit: {agent1_output.limit}")
            print(f"  └─ Confidence: {agent1_output.confidence:.2f}")
            
            # ==================== AGENT #2: SCHEMA SCOUT ====================
            print(f"\n{'='*80}")
            print(f"🔭 AGENT #2: SCHEMA SCOUT")
            print(f"{'='*80}")
            print(f"INPUT: QuestionAnalysis from Agent #1")
            
            agent2_output = self.agent2.scout(agent1_output)
            
            result['stages']['agent2'] = {
                'input': 'QuestionAnalysis object',
                'output': {
                    'selected_tables': agent2_output.selected_tables,
                    'recommended_columns': agent2_output.recommended_columns,
                    'required_joins': [
                        {
                            'from': j.from_table,
                            'to': j.to_table,
                            'on': f"{j.from_column} = {j.to_column}"
                        } for j in agent2_output.required_joins
                    ],
                    'validated_filters': [
                        {
                            'table': f.table,
                            'column': f.column,
                            'operator': f.operator,
                            'value': f.value,
                            'is_valid': f.is_valid
                        } for f in agent2_output.validated_filters
                    ],
                    'confidence': agent2_output.confidence,
                    'warnings': agent2_output.warnings
                },
                'status': 'success'
            }
            
            print(f"\nOUTPUT:")
            print(f"  ├─ Selected Tables: {agent2_output.selected_tables}")
            print(f"  ├─ Recommended Columns: {agent2_output.recommended_columns}")
            print(f"  ├─ Required Joins: {len(agent2_output.required_joins)}")
            for join in agent2_output.required_joins:
                print(f"  │   └─ {join.from_table}.{join.from_column} -> {join.to_table}.{join.to_column}")
            print(f"  ├─ Validated Filters: {len(agent2_output.validated_filters)}")
            print(f"  ├─ Warnings: {agent2_output.warnings}")
            print(f"  └─ Confidence: {agent2_output.confidence:.2f}")
            
            # ==================== AGENT #3: SQL ARCHITECT ====================
            print(f"\n{'='*80}")
            print(f"🏗️  AGENT #3: SQL ARCHITECT")
            print(f"{'='*80}")
            print(f"INPUT: QuestionAnalysis + SchemaContext")
            
            agent3_output = self.agent3.generate(agent1_output, agent2_output)
            
            result['stages']['agent3'] = {
                'input': 'QuestionAnalysis + SchemaContext',
                'output': {
                    'sql': agent3_output.sql,
                    'strategy': agent3_output.strategy,
                    'confidence': agent3_output.confidence,
                    'reasoning': agent3_output.reasoning,
                    'warnings': agent3_output.warnings
                },
                'status': 'success'
            }
            
            result['generated_sql'] = agent3_output.sql
            result['final_confidence'] = agent3_output.confidence
            
            print(f"\nOUTPUT:")
            print(f"  ├─ Strategy: {agent3_output.strategy}")
            print(f"  ├─ Confidence: {agent3_output.confidence:.2f}")
            print(f"  ├─ Reasoning: {agent3_output.reasoning}")
            print(f"  ├─ Warnings: {agent3_output.warnings}")
            print(f"  └─ Generated SQL:")
            print(f"\n{self._format_sql(agent3_output.sql)}\n")
            
            result['pipeline_success'] = True
            
        except Exception as e:
            result['pipeline_success'] = False
            result['errors'].append(str(e))
            print(f"\n❌ ERROR: {e}")
        
        return result
    
    def run_test_suite(self, difficulties: list = None):
        """
        Run complete test suite.
        
        Args:
            difficulties: List of difficulties to test (default: all)
        """
        if difficulties is None:
            difficulties = ['easy', 'medium', 'hard']
        
        all_results = []
        
        print("\n" + "="*80)
        print("🧪 AGENT PIPELINE TEST SUITE")
        print("="*80)
        print(f"Testing {sum(len(TEST_QUERIES[d]) for d in difficulties)} queries")
        print(f"Difficulties: {', '.join(difficulties)}")
        print("="*80)
        
        for difficulty in difficulties:
            queries = TEST_QUERIES.get(difficulty, [])
            
            print(f"\n\n{'#'*80}")
            print(f"{'#'*80}")
            print(f"## DIFFICULTY: {difficulty.upper()}")
            print(f"{'#'*80}")
            print(f"{'#'*80}\n")
            
            for test_query in queries:
                print(f"\n{'='*80}")
                print(f"TEST ID: {test_query['id']}")
                print(f"QUESTION: {test_query['question']}")
                print(f"EXPECTED: {test_query['expected_sql']}")
                print(f"NOTES: {test_query['notes']}")
                print(f"{'='*80}")
                
                result = self.run_test(test_query)
                result['difficulty'] = difficulty
                all_results.append(result)
                
                # Show summary
                if result['pipeline_success']:
                    print(f"\n✅ TEST {test_query['id']}: PIPELINE COMPLETED")
                else:
                    print(f"\n❌ TEST {test_query['id']}: PIPELINE FAILED")
                    print(f"   Errors: {result['errors']}")
                
                print("\n" + "-"*80)
                input("Press ENTER to continue to next test...")
        
        # Generate summary report
        self._print_summary_report(all_results)
        
        return all_results
    
    def _format_sql(self, sql: str) -> str:
        """Format SQL for better readability"""
        lines = sql.strip().split('\n')
        formatted = []
        for line in lines:
            formatted.append(f"      {line}")
        return '\n'.join(formatted)
    
    def _print_summary_report(self, results: list):
        """Print summary report of all tests"""
        print("\n\n" + "="*80)
        print("📊 TEST SUMMARY REPORT")
        print("="*80)
        
        total_tests = len(results)
        successful = sum(1 for r in results if r['pipeline_success'])
        failed = total_tests - successful
        
        print(f"\nTotal Tests: {total_tests}")
        print(f"  ✅ Successful: {successful} ({successful/total_tests*100:.1f}%)")
        print(f"  ❌ Failed: {failed} ({failed/total_tests*100:.1f}%)")
        
        # Breakdown by difficulty
        print("\n\nBreakdown by Difficulty:")
        for difficulty in ['easy', 'medium', 'hard']:
            diff_results = [r for r in results if r['difficulty'] == difficulty]
            if diff_results:
                diff_success = sum(1 for r in diff_results if r['pipeline_success'])
                print(f"  {difficulty.upper()}: {diff_success}/{len(diff_results)} successful")
        
        # Agent-level confidence
        print("\n\nAverage Confidence by Stage:")
        if successful > 0:
            avg_agent1 = sum(r['stages']['agent1']['output']['confidence'] 
                           for r in results if 'agent1' in r['stages']) / total_tests
            avg_agent2 = sum(r['stages']['agent2']['output']['confidence'] 
                           for r in results if 'agent2' in r['stages']) / total_tests
            avg_agent3 = sum(r['final_confidence'] 
                           for r in results if 'final_confidence' in r) / total_tests
            
            print(f"  Agent #1 (Question Decomposer): {avg_agent1:.2f}")
            print(f"  Agent #2 (Schema Scout): {avg_agent2:.2f}")
            print(f"  Agent #3 (SQL Architect): {avg_agent3:.2f}")
        
        # Failed tests
        if failed > 0:
            print("\n\n❌ Failed Tests:")
            for result in results:
                if not result['pipeline_success']:
                    print(f"  {result['test_id']}: {result['question']}")
                    print(f"    Errors: {result['errors']}")
        
        print("\n" + "="*80)
        
        # Save results to JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"test_results_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {output_file}")
        print("="*80 + "\n")
    
    def close(self):
        """Clean up resources"""
        self.agent2.close()


# ==================== MAIN ====================

def main():
    """Run the test suite"""
    print("\n" + "="*80)
    print("🧪 AGENT PIPELINE TESTING")
    print("="*80)
    print("\nThis will test all three agents with 15 queries:")
    print("  - 5 Easy queries")
    print("  - 5 Medium queries")
    print("  - 5 Hard queries")
    print("\nYou'll see the input/output at each stage to debug issues.")
    print("="*80 + "\n")
    
    input("Press ENTER to start testing...")
    
    tester = AgentPipelineTester()
    
    try:
        # Run all tests
        results = tester.run_test_suite(difficulties=['easy', 'medium', 'hard'])
        
        print("\n✅ Testing complete!")
        
    finally:
        tester.close()


if __name__ == "__main__":
    main()
