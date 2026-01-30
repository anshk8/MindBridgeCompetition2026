# Test Suite for SQL Query Writer Agent

## Running Tests

### Question Decomposer Tests

**Run all tests:**
```bash
python tests/test_question_decomposer.py
```

**Run with verbose output (shows full analysis):**
```bash
python tests/test_question_decomposer.py -v
```

**Run specific test:**
```bash
python tests/test_question_decomposer.py -t "Simple COUNT"
```

## Adding New Test Cases

Edit `test_question_decomposer.py` and add to the `TEST_CASES` list:

```python
TestCase(
    name="Your Test Name",
    question="Your question here?",
    expected_query_type="SELECT",
    expected_entities=["products"],
    expected_limit=5,
    expected_has_filters=True,
    min_confidence=0.7,
    notes="Description of what this tests"
)
```

## Test Case Fields

- `name`: Descriptive test name
- `question`: The natural language question to test
- `expected_query_type`: Expected query classification ("SELECT", "COUNT", "AGGREGATION", etc.)
- `expected_entities`: List of database entities that should be detected
- `expected_limit`: Expected LIMIT value (e.g., 5 for "top 5")
- `expected_has_filters`: Should filters be detected? (True/False)
- `expected_has_aggregation`: Should aggregations be detected? (True/False)
- `expected_has_ordering`: Should ordering be detected? (True/False)
- `should_be_ambiguous`: Should question be marked as ambiguous? (True/False)
- `min_confidence`: Minimum acceptable confidence score (0.0-1.0)
- `notes`: Description/explanation of the test

All fields except `name` and `question` are optional. Only specified fields will be validated.

## Test Categories

Current test coverage includes:

- ✅ **Basic Queries**: Simple SELECT, COUNT, filters
- ✅ **Aggregations**: SUM, AVG, GROUP BY patterns
- ✅ **Joins**: Multi-table queries
- ✅ **Edge Cases - Typos**: Misspelled entities
- ✅ **Edge Cases - Ambiguity**: Vague or unclear questions
- ✅ **Edge Cases - Complex**: Subqueries, multiple filters
- ✅ **Edge Cases - Number Variations**: "ten" vs "10", different limit patterns
- ✅ **Edge Cases - Ordering**: ASC vs DESC, implicit ordering
- ✅ **Edge Cases - Invalid**: Empty, too short
- ✅ **Edge Cases - Distinct**: COUNT DISTINCT patterns
- ✅ **Edge Cases - Date Ranges**: Relative dates
- ✅ **Edge Cases - Multiple Entities**: Multi-table relationships
