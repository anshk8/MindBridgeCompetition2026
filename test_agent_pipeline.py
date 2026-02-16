"""
SQL Agent Testing Suite

Tests the QueryWriter (competition interface) which orchestrates
SQLAgent + ValidatorAgent pipeline.
The SQLAgent generates SQL via CoT + Dynamic Few-Shot Learning,
then the ValidatorAgent reviews for syntax, execution, and semantics
(max 2 correction rounds).
"""

import json
import duckdb
from typing import Dict, Any
from datetime import datetime

from agent import QueryWriter

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
    ],
    "hard_advanced": [
    {
        "id": "H6",
        "question": "Which staff members manage other staff, and how many people does each manager supervise?",
        "expected_sql": "SELECT m.first_name, m.last_name, m.staff_id, COUNT(s.staff_id) as direct_reports FROM staffs m JOIN staffs s ON m.staff_id = CAST(s.manager_id AS BIGINT) GROUP BY m.staff_id, m.first_name, m.last_name ORDER BY direct_reports DESC",
        "notes": "Self-join on staffs table with hierarchy, tests manager_id relationship"
    },
    {
        "id": "H7",
        "question": "For each brand, show the number of products and the average price, but only for brands that have products in at least 3 different categories",
        "expected_sql": "SELECT b.brand_name, COUNT(DISTINCT p.product_id) as product_count, AVG(p.list_price) as avg_price FROM brands b JOIN products p ON b.brand_id = p.brand_id GROUP BY b.brand_id, b.brand_name HAVING COUNT(DISTINCT p.category_id) >= 3 ORDER BY product_count DESC",
        "notes": "Multiple aggregations with HAVING clause on COUNT DISTINCT, tests complex filtering"
    },
    {
        "id": "H8",
        "question": "List customers who placed orders in 2016 but not in 2017",
        "expected_sql": "SELECT c.first_name, c.last_name, c.email FROM customers c WHERE c.customer_id IN (SELECT DISTINCT customer_id FROM orders WHERE YEAR(order_date) = 2016) AND c.customer_id NOT IN (SELECT DISTINCT customer_id FROM orders WHERE YEAR(order_date) = 2017)",
        "notes": "Multiple subqueries with set operations (IN and NOT IN), tests temporal filtering"
    },
    {
        "id": "H9",
        "question": "What is the month-over-month revenue growth for 2017?",
        "expected_sql": "SELECT MONTH(o.order_date) as month, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as monthly_revenue FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE YEAR(o.order_date) = 2017 GROUP BY MONTH(o.order_date) ORDER BY month",
        "notes": "Date aggregation by month with calculated revenue, tests temporal grouping (note: full MoM growth would need LAG window function)"
    },
    {
        "id": "H10",
        "question": "Find products that are stocked in all stores",
        "expected_sql": "SELECT p.product_name, p.product_id FROM products p WHERE (SELECT COUNT(DISTINCT st.store_id) FROM stocks st WHERE st.product_id = p.product_id) = (SELECT COUNT(*) FROM stores)",
        "notes": "Correlated subquery testing 'for all' logic (division), tests universal quantification"
    }
]

    
}

# ==================== AGENT TESTER ====================

class SQLAgentTester:
    """
    Tests the QueryWriter (which orchestrates SQLAgent + ValidatorAgent).
    This tests the actual competition interface.
    """
    
    def __init__(self, db_path: str = 'bike_store.db'):
        """Initialize the QueryWriter (competition interface)"""
        print("🚀 Initializing QueryWriter (SQLAgent + ValidatorAgent pipeline)...")
        self.writer = QueryWriter(db_path=db_path)
        self.db_path = db_path
        
    def _get_connection(self):
        """Get a temporary database connection for validation"""
        import duckdb
        return duckdb.connect(self.db_path)
    
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
        
        conn = None
        try:
            conn = self._get_connection()
            result = conn.execute(sql).fetchall()
            validation['executes'] = True
            validation['row_count'] = len(result)
            
            # Get sample result (first row)
            if result:
                validation['sample_result'] = str(result[0])[:100]
            
        except Exception as e:
            validation['error'] = str(e)
        finally:
            if conn:
                conn.close()
        
        return validation
    
    def run_test(self, test_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single query through the QueryWriter.
        
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
            'validation': None,
            'reviewer_approved': None,
            'reviewer_attempts': 0,
            'reviewer_issues': [],
        }
        
        try:
            # Generate SQL using QueryWriter (orchestrates SQLAgent + ValidatorAgent)
            final_sql = self.writer.generate_query(question)
            result['generated_sql'] = final_sql

            # NOTE: QueryWriter.generate_query already runs validation/correction.
            # To avoid redundant LLM calls and inconsistent reviewer stats, we do
            # not call self.writer.validator.validate(...) again here. If
            # reviewer metadata is needed, it should be exposed by QueryWriter.
            result['reviewer_approved'] = None
            result['reviewer_attempts'] = 0
            result['reviewer_issues'] = []

            # Validate execution
            validation = self.validate_sql_execution(final_sql)
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
        print("🧪 QUERYWRITER COMPREHENSIVE TEST SUITE")
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
                    approved_tag = ' (Reviewer: APPROVED)' if result.get('reviewer_approved') else ' (Reviewer: NOT APPROVED)'
                    print(f"\n\u2705 Status: SUCCESS{approved_tag}")
                    print(f"   Returned {validation['row_count']} rows")
                    if result.get('reviewer_attempts', 0) > 0:
                        print(f"   Reviewer correction attempts: {result['reviewer_attempts']}")
                    if validation['sample_result']:
                        print(f"   Sample: {validation['sample_result']}")
                else:
                    print(f"\n\u274c Status: FAILED")
                    if result['error']:
                        print(f"   Error: {result['error'][:150]}")
                    if result.get('reviewer_issues'):
                        print(f"   Reviewer issues: {result['reviewer_issues'][:3]}")
                
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
        # Reviewer stats
        reviewed = [r for r in results if r.get('reviewer_approved') is not None]
        reviewer_approved = sum(1 for r in reviewed if r['reviewer_approved'])
        corrections_used = sum(r.get('reviewer_attempts', 0) for r in results)
        print(f"\n\U0001f50d Reviewer Stats:")
        print(f"  Approved on first pass: {reviewer_approved}/{len(reviewed)}")
        print(f"  Total correction rounds used: {corrections_used}")        
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
        if hasattr(self.writer, 'close'):
            self.writer.close()

# ==================== MAIN ====================

def main():
    """Run the test suite"""
    print("\n" + "="*80)
    print("🧪 QUERYWRITER COMPREHENSIVE TESTING")
    print("="*80)
    print("\nThis will test the QueryWriter (competition interface) with 15 NEW queries:")
    print("  🟢 5 Easy queries (90-100% target)")
    print("  🟡 5 Medium queries (70-85% target)")  
    print("  🔴 5 Hard queries (50-70% target)")
    print("\n⚠️  IMPORTANT: These queries are NOT in the few-shot examples!")
    print("   The QueryWriter uses SQLAgent (generation) + ValidatorAgent (validation).")
    print("\nYou'll see:")
    print("  - Generated SQL for each query")
    print("  - Execution validation")
    print("  - Row counts and sample results")
    print("  - Detailed error messages for failures")
    print("="*80 + "\n")
    
    input("Press ENTER to start testing...")
    
    tester = SQLAgentTester()
    
    try:
        # Run all tests (all difficulties now that medium is active)
        results = tester.run_test_suite(difficulties=['hard', 'hard_advanced'])
        
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
