"""
SQL Agent Testing Suite

This script tests the single SQLAgent that uses Chain-of-Thought reasoning
and Dynamic Few-Shot Learning to generate SQL queries.
"""

import json
import duckdb
from typing import Dict, Any
from datetime import datetime

# Import the SQL Agent
from agents.SQLAgent import SQLAgent

# ==================== NEW TEST QUERIES (NOT IN FEW-SHOT EXAMPLES) ====================

TEST_QUERIES = {
    "easy": [
        {
            "id": "E1",
            "question": "List all stores in California",
            "expected_sql": "SELECT store_name, city, state FROM stores WHERE state = 'CA'",
            "notes": "Simple WHERE filter on state column"
        },
        {
            "id": "E2",
            "question": "What is the cheapest product in the database?",
            "expected_sql": "SELECT product_name, list_price FROM products ORDER BY list_price ASC LIMIT 1",
            "notes": "MIN via ORDER BY ASC + LIMIT"
        },
        {
            "id": "E3",
            "question": "How many products were made in 2018?",
            "expected_sql": "SELECT COUNT(*) FROM products WHERE model_year = 2018",
            "notes": "COUNT with WHERE on year column"
        },
        {
            "id": "E4",
            "question": "Show all staff emails",
            "expected_sql": "SELECT first_name, last_name, email FROM staffs",
            "notes": "Simple SELECT specific columns"
        },
        {
            "id": "E5",
            "question": "What is the total quantity of all products in stock?",
            "expected_sql": "SELECT SUM(quantity) FROM stocks",
            "notes": "Simple SUM aggregation"
        }
    ],
    
    "medium": [
        {
            "id": "M1",
            "question": "Show all orders placed in January 2017",
            "expected_sql": "SELECT order_id, customer_id, order_date FROM orders WHERE order_date BETWEEN '2017-01-01' AND '2017-01-31'",
            "notes": "Date range filtering with BETWEEN"
        },
        {
            "id": "M2",
            "question": "Which brands have more than 10 products?",
            "expected_sql": "SELECT b.brand_name, COUNT(p.product_id) as product_count FROM brands b JOIN products p ON b.brand_id = p.brand_id GROUP BY b.brand_name HAVING COUNT(p.product_id) > 10",
            "notes": "JOIN with GROUP BY and HAVING clause"
        },
        {
            "id": "M3",
            "question": "List all staff members and their store names",
            "expected_sql": "SELECT s.first_name, s.last_name, st.store_name FROM staffs s JOIN stores st ON s.store_id = st.store_id",
            "notes": "Two-table JOIN with different alias pattern"
        },
        {
            "id": "M4",
            "question": "Find products priced between 1000 and 2000 dollars",
            "expected_sql": "SELECT product_name, brand_id, list_price FROM products WHERE list_price BETWEEN 1000 AND 2000",
            "notes": "BETWEEN operator for range"
        },
        {
            "id": "M5",
            "question": "How many orders has each customer placed?",
            "expected_sql": "SELECT c.first_name, c.last_name, COUNT(o.order_id) as order_count FROM customers c LEFT JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.customer_id, c.first_name, c.last_name",
            "notes": "LEFT JOIN with GROUP BY (preserves customers with 0 orders)"
        }
    ],
    
    "hard": [
        {
            "id": "H1",
            "question": "What is the average order value for each customer?",
            "expected_sql": "SELECT c.first_name, c.last_name, AVG(oi.quantity * oi.list_price * (1 - oi.discount)) as avg_order_value FROM customers c JOIN orders o ON c.customer_id = o.customer_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY c.customer_id, c.first_name, c.last_name",
            "notes": "3-table JOIN with calculated AVG on expression"
        },
        {
            "id": "H2",
            "question": "Which products have never been ordered?",
            "expected_sql": "SELECT product_name, product_id FROM products WHERE product_id NOT IN (SELECT DISTINCT product_id FROM order_items)",
            "notes": "NOT IN subquery for exclusion"
        },
        {
            "id": "H3",
            "question": "Show the top 3 customers by total purchase amount",
            "expected_sql": "SELECT c.first_name, c.last_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as total_spent FROM customers c JOIN orders o ON c.customer_id = o.customer_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY c.customer_id, c.first_name, c.last_name ORDER BY total_spent DESC LIMIT 3",
            "notes": "Multi-table JOIN with complex calculation, GROUP BY, ORDER BY, LIMIT"
        },
        {
            "id": "H4",
            "question": "For each store, show the most expensive product in stock",
            "expected_sql": "SELECT s.store_name, p.product_name, p.list_price FROM stores s JOIN stocks st ON s.store_id = st.store_id JOIN products p ON st.product_id = p.product_id WHERE (s.store_id, p.list_price) IN (SELECT st2.store_id, MAX(p2.list_price) FROM stocks st2 JOIN products p2 ON st2.product_id = p2.product_id GROUP BY st2.store_id)",
            "notes": "Correlated subquery with MAX aggregation per group"
        },
        {
            "id": "H5",
            "question": "What percentage of total revenue does each category contribute?",
            "expected_sql": "SELECT c.category_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as category_revenue, (SUM(oi.quantity * oi.list_price * (1 - oi.discount)) * 100.0 / (SELECT SUM(quantity * list_price * (1 - discount)) FROM order_items)) as revenue_percentage FROM categories c JOIN products p ON c.category_id = p.category_id JOIN order_items oi ON p.product_id = oi.product_id GROUP BY c.category_name ORDER BY revenue_percentage DESC",
            "notes": "Multi-table JOIN with subquery for percentage calculation"
        }
    ]
}

# ==================== AGENT TESTER ====================

class SQLAgentTester:
    """
    Tests the single SQLAgent with various queries.
    """
    
    def __init__(self, db_path: str = 'bike_store.db'):
        """Initialize the SQL Agent"""
        print("🚀 Initializing SQL Agent...")
        self.agent = SQLAgent(dbPath=db_path)
        self.db_path = db_path
        # Use the agent's connection instead of creating a new one
        self.conn = self.agent.duckdbConn
    
    def validate_sql_execution(self, sql: str) -> Dict[str, Any]:
        """
        Validate SQL by executing it and checking results.
        
        Returns execution status and row count.
        """
        validation = {
            'executes': False,
            'row_count': 0,
            'error': None,
            'sample_result': None
        }
        
        try:
            result = self.conn.execute(sql).fetchall()
            validation['executes'] = True
            validation['row_count'] = len(result)
            
            # Get sample result (first row)
            if result:
                validation['sample_result'] = str(result[0])[:100]
            
        except Exception as e:
            validation['error'] = str(e)
        
        return validation
    
    def run_test(self, test_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single query through the SQL Agent.
        
        Returns detailed results.
        """
        question = test_query['question']
        
        result = {
            'test_id': test_query['id'],
            'question': question,
            'expected_sql': test_query.get('expected_sql', 'N/A'),
            'generated_sql': None,
            'success': False,
            'error': None,
            'validation': None
        }
        
        try:
            # Generate SQL using the agent
            generated_sql = self.agent.generate(question)
            result['generated_sql'] = generated_sql
            
            # Validate the generated SQL
            validation = self.validate_sql_execution(generated_sql)
            result['validation'] = validation
            result['success'] = validation['executes']
            
            if not validation['executes']:
                result['error'] = validation['error']
            
        except Exception as e:
            result['generated_sql'] = 'ERROR DURING GENERATION'
            result['error'] = str(e)
            result['success'] = False
        
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
        print("🧪 SQL AGENT COMPREHENSIVE TEST SUITE")
        print("="*80)
        print(f"Testing {sum(len(TEST_QUERIES[d]) for d in difficulties)} queries")
        print(f"Difficulties: {', '.join(difficulties)}")
        print("="*80)
        print("\n⚠️  NOTE: These are NEW queries not in the few-shot examples")
        print("    This will test true generalization capability!\n")
        print("="*80)
        
        for difficulty in difficulties:
            queries = TEST_QUERIES.get(difficulty, [])
            
            print(f"\n\n{'🟢 EASY' if difficulty == 'easy' else '🟡 MEDIUM' if difficulty == 'medium' else '🔴 HARD'} QUERIES")
            print("="*80)
            
            for test_query in queries:
                result = self.run_test(test_query)
                result['difficulty'] = difficulty
                all_results.append(result)
                
                # Print result
                print(f"\n[{test_query['id']}] {test_query['question']}")
                print(f"Notes: {test_query['notes']}")
                print(f"\nExpected SQL:")
                print(f"  {test_query['expected_sql'][:200]}...")
                print(f"\nGenerated SQL:")
                print(f"  {result['generated_sql'][:200] if result['generated_sql'] else 'N/A'}...")
                
                if result['success']:
                    validation = result['validation']
                    print(f"\n✅ Status: SUCCESS")
                    print(f"   Returned {validation['row_count']} rows")
                    if validation['sample_result']:
                        print(f"   Sample: {validation['sample_result']}")
                else:
                    print(f"\n❌ Status: FAILED")
                    if result['error']:
                        print(f"   Error: {result['error'][:150]}")
                
                print('-'*80)
        
        # Generate summary report
        self._print_summary_report(all_results)
        
        return all_results
    
    def _print_summary_report(self, results: list):
        """Print summary report of all tests"""
        print("\n\n" + "="*80)
        print("📊 TEST SUMMARY REPORT")
        print("="*80)
        
        total_tests = len(results)
        successful = sum(1 for r in results if r['success'])
        failed = total_tests - successful
        
        print(f"\nTotal Tests: {total_tests}")
        print(f"  ✅ Successful: {successful} ({successful/total_tests*100:.1f}%)")
        print(f"  ❌ Failed: {failed} ({failed/total_tests*100:.1f}%)")
        
        # Breakdown by difficulty
        print("\n\nBreakdown by Difficulty:")
        for difficulty in ['easy', 'medium', 'hard']:
            diff_results = [r for r in results if r['difficulty'] == difficulty]
            if diff_results:
                diff_success = sum(1 for r in diff_results if r['success'])
                diff_total = len(diff_results)
                pct = (diff_success / diff_total * 100) if diff_total > 0 else 0
                
                emoji = '🟢' if difficulty == 'easy' else '🟡' if difficulty == 'medium' else '🔴'
                print(f"  {emoji} {difficulty.upper()}: {diff_success}/{diff_total} successful ({pct:.1f}%)")
        
        # Expected benchmarks
        print("\n\n🎯 Target Benchmarks (based on research):")
        print("  Easy: 90-100% | Medium: 70-85% | Hard: 50-70%")
        
        # Failed tests detail
        if failed > 0:
            print("\n\n❌ Failed Tests:")
            for result in results:
                if not result['success']:
                    print(f"\n  [{result['test_id']}] {result['question']}")
                    print(f"    Difficulty: {result['difficulty'].upper()}")
                    if result['error']:
                        print(f"    Error: {result['error'][:120]}")
        
        # Success stories (show a few successful hard queries)
        successful_hard = [r for r in results if r['success'] and r['difficulty'] == 'hard']
        if successful_hard:
            print("\n\n✅ Successfully Solved Hard Queries:")
            for result in successful_hard[:3]:  # Show first 3
                print(f"  [{result['test_id']}] {result['question']}")
                print(f"    Rows returned: {result['validation']['row_count']}")
        
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
        if hasattr(self.agent, 'close'):
            self.agent.close()
        # Don't close conn since it's the agent's connection

# ==================== MAIN ====================

def main():
    """Run the test suite"""
    print("\n" + "="*80)
    print("🧪 SQL AGENT COMPREHENSIVE TESTING")
    print("="*80)
    print("\nThis will test the SQL Agent with 15 NEW queries:")
    print("  🟢 5 Easy queries (90-100% target)")
    print("  🟡 5 Medium queries (70-85% target)")  
    print("  🔴 5 Hard queries (50-70% target)")
    print("\n⚠️  IMPORTANT: These queries are NOT in the few-shot examples!")
    print("   This tests true generalization, not memorization.")
    print("\nYou'll see:")
    print("  - Generated SQL for each query")
    print("  - Execution validation")
    print("  - Row counts and sample results")
    print("  - Detailed error messages for failures")
    print("="*80 + "\n")
    
    input("Press ENTER to start testing...")
    
    tester = SQLAgentTester()
    
    try:
        # Run all tests
        results = tester.run_test_suite(difficulties=['easy', 'medium', 'hard'])
        
        print("\n✅ Testing complete!")
        print("\n💡 Tips for improvement if accuracy is low:")
        print("   1. Add more diverse few-shot examples")
        print("   2. Try different Ollama models (llama3.3, deepseek-coder)")
        print("   3. Increase validation attempts in _validateAndCorrect()")
        print("   4. Add more specific examples for failing patterns")
        
    finally:
        tester.close()

if __name__ == "__main__":
    main()
