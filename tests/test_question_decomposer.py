"""
Test Suite for Question Decomposer Agent

Tests various edge cases and scenarios to ensure robust question analysis.
Easy to add new test cases - just add to the TEST_CASES list.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.questionDecomposerAgent import QuestionDecomposer, QuestionAnalysis
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import json


@dataclass
class TestCase:
    """Test case with expected behavior"""
    name: str
    question: str
    expected_query_type: Optional[str] = None
    expected_entities: Optional[List[str]] = None
    expected_limit: Optional[int] = None
    expected_has_filters: Optional[bool] = None
    expected_has_aggregation: Optional[bool] = None
    expected_has_ordering: Optional[bool] = None
    should_be_ambiguous: Optional[bool] = None
    min_confidence: Optional[float] = None
    notes: str = ""


# ==================== TEST CASES ====================

TEST_CASES = [
    # ========== BASIC QUERIES ==========
    TestCase(
        name="Simple COUNT Query",
        question="How many customers are there?",
        expected_query_type="COUNT",
        expected_entities=["customers"],
        expected_has_aggregation=True,
        min_confidence=0.8,
        notes="Basic count with clear entity"
    ),
    
    TestCase(
        name="Simple SELECT with LIMIT",
        question="What are the top 5 most expensive products?",
        expected_query_type="SELECT",
        expected_entities=["products"],
        expected_limit=5,
        expected_has_ordering=True,
        min_confidence=0.7,
        notes="Should detect limit=5 and DESC ordering"
    ),
    
    TestCase(
        name="Simple FILTER Query",
        question="List all products with price greater than 500",
        expected_query_type="SELECT",
        expected_entities=["products"],
        expected_has_filters=True,
        min_confidence=0.7,
        notes="Should detect price filter"
    ),
    
    # ========== AGGREGATION QUERIES ==========
    TestCase(
        name="Aggregation with GROUP BY",
        question="What is the total revenue by brand?",
        expected_query_type="AGGREGATION",
        expected_entities=["brands"],
        expected_has_aggregation=True,
        min_confidence=0.6,
        notes="Needs SUM aggregation and GROUP BY"
    ),
    
    TestCase(
        name="Average Calculation",
        question="What is the average order value?",
        expected_query_type="AGGREGATION",
        expected_entities=["orders"],
        expected_has_aggregation=True,
        min_confidence=0.7,
        notes="Should detect AVG aggregation"
    ),
    
    # ========== JOIN QUERIES ==========
    TestCase(
        name="Implicit JOIN",
        question="Which store has the most inventory?",
        expected_query_type="SELECT",
        expected_entities=["stores", "stocks"],
        expected_has_aggregation=True,
        min_confidence=0.6,
        notes="Needs JOIN between stores and stocks"
    ),
    
    TestCase(
        name="Multi-table Query",
        question="Show me all orders from 2018",
        expected_query_type="SELECT",
        expected_entities=["orders"],
        expected_has_filters=True,
        min_confidence=0.7,
        notes="Filter on order_date"
    ),
    
    # ========== EDGE CASE: TYPOS ==========
    TestCase(
        name="Typo in Entity Name",
        question="Show me all prodcts",
        expected_entities=["products"],  # Should correct to products
        min_confidence=0.4,
        notes="LLM might correct 'prodcts' to 'products'"
    ),
    
    # ========== EDGE CASE: AMBIGUOUS ==========
    TestCase(
        name="Ambiguous - Too Vague",
        question="Show me products",
        should_be_ambiguous=True,
        min_confidence=0.5,
        notes="Too vague - which products? all?"
    ),
    
    TestCase(
        name="Ambiguous - Missing Context",
        question="What is the revenue?",
        should_be_ambiguous=True,
        min_confidence=0.5,
        notes="Revenue for what? Total? By brand? By period?"
    ),
    
    # ========== EDGE CASE: COMPLEX QUERIES ==========
    TestCase(
        name="Complex - Subquery Pattern",
        question="Find customers who have never placed an order",
        expected_query_type="COMPLEX",
        expected_entities=["customers", "orders"],
        min_confidence=0.5,
        notes="Needs NOT EXISTS or LEFT JOIN WHERE NULL"
    ),
    
    TestCase(
        name="Complex - Multiple Filters",
        question="Show Trek bikes over $500 from 2018",
        expected_entities=["products"],
        expected_has_filters=True,
        min_confidence=0.6,
        notes="Multiple filters: brand, price, year"
    ),
    
    # ========== EDGE CASE: NUMBER VARIATIONS ==========
    TestCase(
        name="Spelled Out Number",
        question="Show me top ten products",
        expected_limit=10,  # May fail if LLM doesn't parse "ten"
        min_confidence=0.5,
        notes="Number spelled out instead of digit"
    ),
    
    TestCase(
        name="Limit Without 'Top'",
        question="Give me 5 customers",
        expected_limit=5,
        expected_entities=["customers"],
        min_confidence=0.6,
        notes="Limit without 'top' keyword"
    ),
    
    # ========== EDGE CASE: ORDERING VARIATIONS ==========
    TestCase(
        name="Lowest/Cheapest",
        question="What are the cheapest 10 products?",
        expected_entities=["products"],
        expected_limit=10,
        expected_has_ordering=True,  # Should be ASC
        min_confidence=0.7,
        notes="Should detect ASC ordering for 'cheapest'"
    ),
    
    TestCase(
        name="Best Sellers",
        question="Show me the best selling products",
        expected_entities=["products"],
        expected_has_ordering=True,
        min_confidence=0.6,
        notes="'best selling' implies ordering by sales count"
    ),
    
    # ========== EDGE CASE: EMPTY/INVALID ==========
    # Note: Empty question throws exception (which is correct behavior)
    # TestCase(
    #     name="Empty Question",
    #     question="",
    #     should_be_ambiguous=True,
    #     notes="Should fail validation"
    # ),
    
    TestCase(
        name="Too Short",
        question="show products",
        min_confidence=0.5,
        notes="Very short query, minimal context"
    ),
    
    # ========== EDGE CASE: DISTINCT ==========
    TestCase(
        name="Distinct Count",
        question="How many different brands do we have?",
        expected_query_type="COUNT",
        expected_entities=["brands"],
        expected_has_aggregation=True,
        min_confidence=0.7,
        notes="Should detect COUNT DISTINCT need"
    ),
    
    # ========== EDGE CASE: DATE RANGES ==========
    TestCase(
        name="Relative Date",
        question="Show orders from last month",
        expected_entities=["orders"],
        expected_has_filters=True,
        min_confidence=0.6,
        notes="Relative date - needs DATE_SUB or similar"
    ),
    
    # ========== EDGE CASE: MULTIPLE ENTITIES ==========
    TestCase(
        name="Products and Brands",
        question="Show me products and their brands",
        expected_entities=["products", "brands"],
        min_confidence=0.7,
        notes="Should detect JOIN needed between products and brands"
    ),
]


# ==================== TEST RUNNER ====================

def run_test(decomposer: QuestionDecomposer, test_case: TestCase) -> Dict[str, Any]:
    """
    Run a single test case.
    
    Returns:
        Dictionary with test results
    """
    result = {
        'name': test_case.name,
        'passed': True,
        'failures': [],
        'analysis': None,
        'error': None
    }
    
    try:
        # Validate question first
        is_valid, issues = decomposer.validate_question(test_case.question)
        
        if not is_valid and test_case.question:  # Empty questions should fail validation
            result['failures'].append(f"Validation failed: {', '.join(issues)}")
            if test_case.expected_entities or test_case.expected_query_type:
                result['passed'] = False
            return result
        
        # Decompose question
        analysis = decomposer.decompose(test_case.question)
        result['analysis'] = analysis
        
        # Check expected query type (allow compound types like SELECT|COUNT)
        if test_case.expected_query_type:
            # Accept if expected type appears in compound type
            query_types = analysis.query_type.split('|')
            if test_case.expected_query_type not in query_types:
                result['failures'].append(
                    f"Query type mismatch: expected '{test_case.expected_query_type}', "
                    f"got '{analysis.query_type}'"
                )
                result['passed'] = False
        
        # Check expected entities
        if test_case.expected_entities:
            missing = set(test_case.expected_entities) - set(analysis.entities)
            if missing:
                result['failures'].append(
                    f"Missing entities: {missing}. Got: {analysis.entities}"
                )
                result['passed'] = False
        
        # Check expected limit
        if test_case.expected_limit is not None:
            if analysis.limit != test_case.expected_limit:
                result['failures'].append(
                    f"Limit mismatch: expected {test_case.expected_limit}, "
                    f"got {analysis.limit}"
                )
                result['passed'] = False
        
        # Check filters
        if test_case.expected_has_filters is not None:
            has_filters = len(analysis.filters) > 0
            if has_filters != test_case.expected_has_filters:
                result['failures'].append(
                    f"Filter detection mismatch: expected {test_case.expected_has_filters}, "
                    f"got {has_filters}"
                )
                result['passed'] = False
        
        # Check aggregation
        if test_case.expected_has_aggregation is not None:
            has_agg = len(analysis.aggregations) > 0
            if has_agg != test_case.expected_has_aggregation:
                result['failures'].append(
                    f"Aggregation detection mismatch: expected {test_case.expected_has_aggregation}, "
                    f"got {has_agg}"
                )
                result['passed'] = False
        
        # Check ordering
        if test_case.expected_has_ordering is not None:
            has_ordering = analysis.ordering is not None
            if has_ordering != test_case.expected_has_ordering:
                result['failures'].append(
                    f"Ordering detection mismatch: expected {test_case.expected_has_ordering}, "
                    f"got {has_ordering}"
                )
                result['passed'] = False
        
        # Check ambiguity
        if test_case.should_be_ambiguous is not None:
            if analysis.is_ambiguous != test_case.should_be_ambiguous:
                result['failures'].append(
                    f"Ambiguity detection mismatch: expected {test_case.should_be_ambiguous}, "
                    f"got {analysis.is_ambiguous}"
                )
                result['passed'] = False
        
        # Check confidence
        if test_case.min_confidence is not None:
            if analysis.confidence < test_case.min_confidence:
                result['failures'].append(
                    f"Confidence too low: expected >={test_case.min_confidence}, "
                    f"got {analysis.confidence:.2f}"
                )
                # Don't fail the test, just warn
        
    except Exception as e:
        result['passed'] = False
        result['error'] = str(e)
        result['failures'].append(f"Exception: {e}")
    
    return result


def print_result(result: Dict[str, Any], verbose: bool = False):
    """Print test result with color coding"""
    status = "✅ PASS" if result['passed'] else "❌ FAIL"
    print(f"\n{status} | {result['name']}")
    
    if result['error']:
        print(f"  💥 Error: {result['error']}")
    
    if result['failures']:
        for failure in result['failures']:
            print(f"  ⚠️  {failure}")
    
    if verbose and result['analysis']:
        analysis = result['analysis']
        print(f"  📊 Query Type: {analysis.query_type}")
        print(f"  🎯 Intent: {analysis.intent}")
        print(f"  📦 Entities: {analysis.entities}")
        if analysis.limit:
            print(f"  🔢 Limit: {analysis.limit}")
        if analysis.ordering:
            print(f"  📈 Ordering: {analysis.ordering}")
        if analysis.filters:
            print(f"  🔍 Filters: {len(analysis.filters)} found")
        if analysis.aggregations:
            print(f"  📊 Aggregations: {len(analysis.aggregations)} found")
        print(f"  🎲 Confidence: {analysis.confidence:.2f}")
        if analysis.is_ambiguous:
            print(f"  ⚠️  Ambiguous: {analysis.ambiguity_reasons}")


def run_all_tests(verbose: bool = False):
    """Run all test cases"""
    print("=" * 80)
    print("🧪 QUESTION DECOMPOSER TEST SUITE")
    print("=" * 80)
    
    decomposer = QuestionDecomposer()
    
    results = []
    for test_case in TEST_CASES:
        result = run_test(decomposer, test_case)
        results.append(result)
        print_result(result, verbose=verbose)
    
    # Summary
    passed = sum(1 for r in results if r['passed'])
    failed = len(results) - passed
    pass_rate = (passed / len(results)) * 100 if results else 0
    
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Pass Rate: {pass_rate:.1f}%")
    
    if failed > 0:
        print("\n🔍 Failed Tests:")
        for result in results:
            if not result['passed']:
                print(f"  • {result['name']}")
    
    print("=" * 80)
    
    return results, pass_rate


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Question Decomposer Agent')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Show detailed analysis for each test')
    parser.add_argument('-t', '--test', type=str,
                       help='Run specific test by name')
    
    args = parser.parse_args()
    
    if args.test:
        # Run specific test
        decomposer = QuestionDecomposer()
        matching_tests = [tc for tc in TEST_CASES if args.test.lower() in tc.name.lower()]
        
        if not matching_tests:
            print(f"❌ No test found matching '{args.test}'")
            print("\nAvailable tests:")
            for tc in TEST_CASES:
                print(f"  • {tc.name}")
        else:
            for test_case in matching_tests:
                result = run_test(decomposer, test_case)
                print_result(result, verbose=True)
    else:
        # Run all tests
        run_all_tests(verbose=args.verbose)
