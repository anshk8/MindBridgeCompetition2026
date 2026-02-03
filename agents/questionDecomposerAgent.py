"""
Question Decomposer Agent - SIMPLIFIED VERSION

Uses LLM to extract structured information from natural language questions.
NO keyword searching, NO heuristics, NO pattern matching.
Just a well-designed prompt + JSON parsing.
"""

import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import ollama


@dataclass
class QuestionAnalysis:
    """Simplified, focused question analysis"""
    
    # Core identification
    original_question: str
    query_type: str  # "SELECT" | "COUNT" | "AGGREGATION" | "JOIN"
    
    # Database elements
    entities: List[str]  # Tables to query
    filters: List[Dict[str, Any]]  # WHERE conditions
    aggregations: List[Dict[str, str]]  # [{"function": "COUNT", "column": "*"}]
    ordering: Optional[Dict[str, str]]  # {"column": "price", "direction": "DESC"}
    limit: Optional[int]  # TOP N limit
    
    # Quality
    confidence: float
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class QuestionDecomposer:
    """
    Agent #1: SIMPLIFIED Question Decomposer
    
    Strategy: Let the LLM do ALL the work.
    No keyword searching, no heuristics, no regex.
    Just a good prompt + structured JSON output.
    """
    
    SYSTEM_PROMPT = """You are an expert at analyzing natural language questions about databases.

Extract the following information from the user's question:

1. **query_type**: The SQL operation type
   - "SELECT" - retrieve specific data
   - "COUNT" - count rows
   - "AGGREGATION" - sum, average, max, min, etc.
   - "JOIN" - combines multiple tables

2. **entities**: Database tables mentioned (e.g., "products", "customers", "orders")

3. **filters**: Conditions to filter data
   Format: [{"column": "price", "operator": ">", "value": 100}]
   
4. **aggregations**: Aggregate functions needed
   Format: [{"function": "COUNT|SUM|AVG|MAX|MIN", "column": "column_name or *"}]
   
5. **ordering**: Sorting requirements
   Format: {"column": "price", "direction": "ASC|DESC"}
   If user says "top", "highest", "most" → direction is "DESC"
   If user says "lowest", "cheapest", "least" → direction is "ASC"
   
6. **limit**: Number of results to return (e.g., "top 5" → 5)

7. **confidence**: Your confidence in this analysis (0.0 to 1.0)

IMPORTANT RULES:
- If no filters mentioned → filters = []
- If no aggregation → aggregations = []
- If no sorting → ordering = null
- If no limit → limit = null
- For COUNT questions → query_type = "COUNT", aggregations = [{"function": "COUNT", "column": "*"}]
- Entity names should be plural (e.g., "products" not "product")

Return ONLY valid JSON matching this exact structure:
{
  "query_type": "SELECT",
  "entities": ["products"],
  "filters": [],
  "aggregations": [],
  "ordering": null,
  "limit": null,
  "confidence": 0.9
}"""

    def __init__(self, model: str = None):
        """Initialize with LLM model"""
        # Use qwen2.5:14b for Agent #1 (excellent at structured output)
        self.model = model or os.getenv('AGENT1_MODEL', os.getenv('OLLAMA_MODEL', 'qwen2.5:14b'))
        self.client = ollama.Client(host=os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
        print(f"🤖 Agent #1 using model: {self.model}")
    
    def decompose(self, question: str) -> QuestionAnalysis:
        """
        Main method: Decompose question into structured analysis.
        
        Steps:
        1. Send question to LLM with structured prompt
        2. Parse JSON response
        3. Validate and return QuestionAnalysis
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        question = question.strip()
        
        print(f"\n{'='*80}")
        print(f"📝 AGENT #1: QUESTION DECOMPOSER")
        print(f"{'='*80}")
        print(f"INPUT: {question}")
        
        # Get LLM analysis
        analysis_dict = self._analyze_with_llm(question)
        
        # Convert to QuestionAnalysis object
        result = QuestionAnalysis(
            original_question=question,
            query_type=analysis_dict.get('query_type', 'SELECT'),
            entities=analysis_dict.get('entities', []),
            filters=analysis_dict.get('filters', []),
            aggregations=analysis_dict.get('aggregations', []),
            ordering=analysis_dict.get('ordering'),
            limit=analysis_dict.get('limit'),
            confidence=analysis_dict.get('confidence', 0.7)
        )
        
        # Print output
        print(f"\nOUTPUT:")
        print(f"  ├─ Query Type: {result.query_type}")
        print(f"  ├─ Entities: {result.entities}")
        print(f"  ├─ Filters: {result.filters if result.filters else 'None'}")
        print(f"  ├─ Aggregations: {result.aggregations if result.aggregations else 'None'}")
        print(f"  ├─ Ordering: {result.ordering if result.ordering else 'None'}")
        print(f"  ├─ Limit: {result.limit if result.limit else 'None'}")
        print(f"  └─ Confidence: {result.confidence:.2f}")
        print(f"{'='*80}")
        
        return result
    
    def _analyze_with_llm(self, question: str) -> Dict:
        """
        Send question to LLM and get structured JSON back.
        
        This is the ONLY analysis method - no heuristics, no keywords.
        """
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': self.SYSTEM_PROMPT},
                    {'role': 'user', 'content': f'Analyze this question: "{question}"'}
                ],
                format='json'
            )
            
            content = response['message']['content'].strip()
            
            # Parse JSON
            analysis = json.loads(content)
            
            # Validate required fields exist
            required_fields = ['query_type', 'entities', 'confidence']
            for field in required_fields:
                if field not in analysis:
                    raise ValueError(f"LLM response missing required field: {field}")
            
            # Ensure lists exist (even if empty)
            analysis.setdefault('filters', [])
            analysis.setdefault('aggregations', [])
            
            # Validate entities is a list of strings
            if not isinstance(analysis['entities'], list):
                raise ValueError(f"Entities must be a list, got {type(analysis['entities'])}")
            
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"❌ LLM returned invalid JSON: {e}")
            return self._fallback_analysis(question)
        except Exception as e:
            print(f"❌ LLM analysis failed: {e}")
            return self._fallback_analysis(question)
    
    def _fallback_analysis(self, question: str) -> Dict:
        """
        Minimal fallback when LLM fails.
        
        Just extract entity words and return basic SELECT.
        """
        # Very basic entity extraction - just look for common table names
        common_tables = ['products', 'customers', 'orders', 'stores', 'brands', 'categories', 'staff', 'stocks']
        question_lower = question.lower()
        
        entities = [table for table in common_tables if table in question_lower or table[:-1] in question_lower]
        
        # If "how many" or "count" → COUNT query
        query_type = "COUNT" if any(word in question_lower for word in ['how many', 'count', 'number of']) else "SELECT"
        
        return {
            'query_type': query_type,
            'entities': entities if entities else ['products'],  # Default to products
            'filters': [],
            'aggregations': [{"function": "COUNT", "column": "*"}] if query_type == "COUNT" else [],
            'ordering': None,
            'limit': None,
            'confidence': 0.3
        }
