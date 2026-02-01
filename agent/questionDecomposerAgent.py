"""
Question Decomposer Agent - Phase 1: Understanding

This agent is responsible for:
1. Breaking down complex questions into components
2. Identifying key entities (products, customers, orders, etc.)
3. Detecting relationships between entities
4. Classifying the query type (SELECT, COUNT, aggregation, join, etc.)
5. Detecting ambiguity or invalid questions
6. Extracting filters and conditions

The output provides a structured understanding that guides downstream agents.
"""

import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import ollama
from utils.prompts import QUESTION_DECOMPOSER_SYSTEM_PROMPT


#Dataclass is structured container for all extracted information about the question.
@dataclass
class QuestionAnalysis:
    """
    Structured output from question decomposition.
    
    This provides a comprehensive understanding of the user's question.
    """
    # Original question
    original_question: str
    
    # Query classification
    query_type: str  # e.g., "SELECT", "COUNT", "AGGREGATION", "JOIN", "COMPLEX"
    intent: str      # e.g., "find top products", "count customers", "calculate revenue"
    
    # Entities mentioned
    entities: List[str]  # e.g., ["products", "customers", "orders"]
    
    # Relationships needed
    relationships: List[Dict[str, str]]  # e.g., [{"from": "orders", "to": "customers", "type": "join"}]
    
    # Filters and conditions
    filters: List[Dict[str, Any]]  # e.g., [{"column": "price", "operator": ">", "value": 100}]
    
    # Aggregations needed
    aggregations: List[Dict[str, str]]  # e.g., [{"function": "COUNT", "column": "*"}]
    
    # Sorting/ordering
    ordering: Optional[Dict[str, str]]  # e.g., {"column": "price", "direction": "DESC"}
    
    # Limiting results
    limit: Optional[int]  # e.g., 5 for "top 5"
    
    # Ambiguity detection
    is_ambiguous: bool
    ambiguity_reasons: List[str]
    
    # Confidence score
    confidence: float  # 0.0 to 1.0
    
    # Additional notes
    notes: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


class QuestionDecomposer:
    """
    Agent 1: Question Decomposer
    
    Analyzes and breaks down natural language questions into structured components
    that can be used by downstream agents for SQL generation.
    
    This agent uses an LLM to understand the question deeply and extract all
    relevant information needed for accurate SQL generation.
    """
    
    def __init__(self, model: str = None, host: str = None):
        """
        Initialize the Question Decomposer.
        
        Args:
            model: LLM model name (defaults to env var OLLAMA_MODEL or 'llama3.2')
            host: Ollama host URL (defaults to env var OLLAMA_HOST or local)
        """
        self.model = model or os.getenv('OLLAMA_MODEL', 'llama3.2')
        host = host or os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.client = ollama.Client(host=host)
        
        # Common SQL query patterns for classification
        self.query_patterns = {
            'COUNT': ['how many', 'count', 'number of', 'total number'],
            'AGGREGATION': ['sum', 'average', 'avg', 'total', 'maximum', 'max', 'minimum', 'min'],
            'TOP_N': ['top', 'best', 'highest', 'lowest', 'first', 'last'],
            'JOIN': ['from', 'with', 'who', 'which', 'that have', 'belonging to'],
            'FILTER': ['where', 'with', 'having', 'greater than', 'less than', 'equal to', 'between'],
            'GROUPING': ['by', 'per', 'each', 'for each', 'group by'],
            'ORDERING': ['order', 'sort', 'sorted', 'arrange']
        }
    
    def decompose(self, question: str) -> QuestionAnalysis:
        """
        Decompose a natural language question into structured components.
        
        Args:
            question: The natural language question from the user
            
        Returns:
            QuestionAnalysis object with all extracted information
            
        Raises:
            ValueError: If the question is empty or invalid
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        question = question.strip()
        
        # Use LLM to analyze the question
        analysis_result = self._analyze_with_llm(question)
        
        # Perform additional heuristic analysis to complement LLM
        heuristic_analysis = self._heuristic_analysis(question)
        
        # Merge LLM and heuristic results
        final_analysis = self._merge_analyses(question, analysis_result, heuristic_analysis)
        
        return final_analysis
    
    def _analyze_with_llm(self, question: str) -> Dict:
        """
        Use LLM to deeply analyze the question.
        
        Args:
            question: The user's question
            
        Returns:
            Dictionary with LLM's analysis
        """
        user_prompt = f"""Analyze this question:

"{question}"

Return ONLY the JSON analysis, nothing else."""

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': QUESTION_DECOMPOSER_SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_prompt}
                ],
                format='json'  # Request JSON format
            )
            
            content = response['message']['content'].strip()
            
                # Parse JSON response
            try:
                analysis = json.loads(content)
                return analysis
            
            except json.JSONDecodeError as e:
                print(f"Failed to parse LLM JSON response: {e}")
                raise ValueError("LLM returned invalid JSON format")
                    
        except Exception as e:
            print(f"LLM analysis failed: {e}")
            return self._create_fallback_analysis(question)
    
    def _heuristic_analysis(self, question: str) -> Dict:
        """
        Perform heuristic pattern-based analysis.
        
        This complements the LLM analysis with rule-based pattern matching.
        
        Args:
            question: The user's question
            
        Returns:
            Dictionary with heuristic analysis
        """
        question_lower = question.lower()
        
        analysis = {
            'patterns_found': [],
            'implied_limit': None,
            'needs_ordering': False,
            'needs_aggregation': False,
            'complexity': 'simple'
        }
        
        # Check for patterns
        for pattern_type, keywords in self.query_patterns.items():
            if any(keyword in question_lower for keyword in keywords):
                analysis['patterns_found'].append(pattern_type)
        
        # Extract numeric limits
        import re
        
        # Look for "top N", "first N", "last N"
        top_match = re.search(r'\b(top|first|last)\s+(\d+)\b', question_lower)
        if top_match:
            analysis['implied_limit'] = int(top_match.group(2))
            analysis['needs_ordering'] = True
        
        # Look for standalone numbers that might be limits
        number_match = re.search(r'\b(\d+)\s+(products|customers|orders|items)\b', question_lower)
        if number_match and not top_match:
            analysis['implied_limit'] = int(number_match.group(1))
        
        # Detect aggregation needs
        if any(pattern in analysis['patterns_found'] for pattern in ['AGGREGATION', 'COUNT', 'GROUPING']):
            analysis['needs_aggregation'] = True
        
        # Assess complexity
        if len(analysis['patterns_found']) > 3:
            analysis['complexity'] = 'complex'
        elif len(analysis['patterns_found']) > 1:
            analysis['complexity'] = 'moderate'
        
        return analysis
    

    def _merge_analyses(self, question: str, llm_analysis: Dict, heuristic_analysis: Dict) -> QuestionAnalysis:
        """
        Merge LLM and heuristic analyses into final QuestionAnalysis.
        
        Args:
            question: Original question
            llm_analysis: Analysis from LLM
            heuristic_analysis: Analysis from heuristics
            
        Returns:
            QuestionAnalysis object
        """
        
        # Strict entity validation - throw error if wrong format
        entities = llm_analysis.get('entities', [])
        if not isinstance(entities, list):
            raise ValueError(f"LLM returned invalid entities format. Expected list, got {type(entities).__name__}: {entities}")
        
        # Validate each entity is a string
        for i, entity in enumerate(entities):
            if not isinstance(entity, str):
                raise ValueError(f"Entity at index {i} is not a string: {type(entity).__name__} = {entity}")
        
        # Determine limit (prefer heuristic if found)
        limit = heuristic_analysis.get('implied_limit') or llm_analysis.get('limit')
        
        # Enhance ordering detection
        ordering = llm_analysis.get('ordering')
        if heuristic_analysis.get('needs_ordering') and not ordering:
            # Infer ordering from query type
            if 'top' in question.lower() or 'highest' in question.lower() or 'most' in question.lower():
                ordering = {"column": "inferred", "direction": "DESC"}
            elif 'lowest' in question.lower() or 'least' in question.lower() or 'cheapest' in question.lower():
                ordering = {"column": "inferred", "direction": "ASC"}
        
        # Build final analysis
        return QuestionAnalysis(
            original_question=question,
            query_type=llm_analysis.get('query_type', 'SELECT'),
            intent=llm_analysis.get('intent', 'Unknown intent'),
            entities=entities,
            relationships=llm_analysis.get('relationships', []),
            filters=llm_analysis.get('filters', []),
            aggregations=llm_analysis.get('aggregations', []),
            ordering=ordering,
            limit=limit,
            is_ambiguous=llm_analysis.get('is_ambiguous', False),
            ambiguity_reasons=llm_analysis.get('ambiguity_reasons', []),
            confidence=llm_analysis.get('confidence', 0.7),
            notes=f"Complexity: {heuristic_analysis.get('complexity', 'unknown')}. "
                  f"Patterns: {', '.join(heuristic_analysis.get('patterns_found', []))}. "
                  f"{llm_analysis.get('notes') or ''}"
        )
    
    def _create_fallback_analysis(self, question: str) -> Dict:
        """
        Create a basic fallback analysis when LLM fails.
        
        Args:
            question: The user's question
            
        Returns:
            Basic analysis dictionary
        """
        return {
            'query_type': 'SELECT',
            'intent': 'Unable to fully analyze question',
            'entities': [],
            'relationships': [],
            'filters': [],
            'aggregations': [],
            'ordering': None,
            'limit': None,
            'is_ambiguous': True,
            'ambiguity_reasons': ['Failed to analyze question with LLM'],
            'confidence': 0.3,
            'notes': 'Fallback analysis used due to LLM failure'
        }
    
    def validate_question(self, question: str) -> tuple[bool, List[str]]:
        """
        Validate if a question is answerable.
        
        Args:
            question: The user's question
            
        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []
        
        if not question or not question.strip():
            issues.append("Question is empty")
            return False, issues
        
        question_lower = question.lower()
        
        # Check for common issues
        if len(question.split()) < 3:
            issues.append("Question is too short to be meaningful")
        
        # Check if it's a question or command
        question_indicators = ['what', 'how', 'who', 'where', 'when', 'which', 'show', 'list', 'find', 'get', 'count', 'give', 'display', 'tell']
        if not any(indicator in question_lower for indicator in question_indicators):
            issues.append("Doesn't appear to be a question or request")
        
        # Check for SQL injection attempts (basic)
        dangerous_patterns = ['drop table', 'delete from', 'truncate', 'insert into', 'update set']
        if any(pattern in question_lower for pattern in dangerous_patterns):
            issues.append("Question contains potentially dangerous SQL commands")
            return False, issues
        
        return len(issues) == 0, issues


def test_question_decomposer():
    """Test the Question Decomposer with various questions"""
    
    print("=" * 80)
    print("Testing Question Decomposer Agent")
    print("=" * 80)
    
    decomposer = QuestionDecomposer()
    
    test_questions = [
        "What are the top 5 most expensive products?",
        "How many customers are there?",
        "Show me all orders from 2018",
        "Which store has the most inventory?",
        "What is the total revenue by brand?",
        "List all products with price greater than 500",
        "Find customers who have never placed an order",
        "What is the average order value?",
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'=' * 80}")
        print(f"Test {i}: {question}")
        print('=' * 80)
        
        try:
            # Validate question
            is_valid, issues = decomposer.validate_question(question)
            if not is_valid:
                print(f"❌ Invalid question: {', '.join(issues)}")
                continue
            
            # Decompose question
            analysis = decomposer.decompose(question)
            
            # Display results
            print(f"\n✅ Analysis Complete (Confidence: {analysis.confidence:.2f})")
            print(f"\nQuery Type: {analysis.query_type}")
            print(f"Intent: {analysis.intent}")
            print(f"Entities: {', '.join(analysis.entities) if analysis.entities else 'None'}")
            
            if analysis.filters:
                print(f"Filters: {json.dumps(analysis.filters, indent=2)}")
            
            if analysis.aggregations:
                print(f"Aggregations: {json.dumps(analysis.aggregations, indent=2)}")
            
            if analysis.ordering:
                print(f"Ordering: {analysis.ordering}")
            
            if analysis.limit:
                print(f"Limit: {analysis.limit}")
            
            if analysis.is_ambiguous:
                print(f"\n⚠️  Ambiguous: {', '.join(analysis.ambiguity_reasons)}")
            
            print(f"\nNotes: {analysis.notes}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("Question Decomposer test complete!")
    print("=" * 80)


if __name__ == "__main__":
    test_question_decomposer()
