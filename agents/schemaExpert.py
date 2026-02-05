"""
Schema Scout Agent - Phase 2: SIMPLIFIED VERSION

A minimalist database intelligence agent that:
1. Maps entities to tables
2. Gets basic schema info
3. Finds sample data
4. Recommends columns

NO complex stats, NO filter validation, NO deep introspection.
Just the essentials to feed Agent #3.
"""

import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field

# Imports
try:
    from dataMCP.server import DatabaseMCPServer
    from agents.questionDecomposerAgent import QuestionAnalysis
except ImportError:
    try:
        # Try agent folder (singular)
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from agent.questionDecomposerAgent import QuestionAnalysis
        from dataMCP.server import DatabaseMCPServer
    except ImportError:
        # Fallback
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from questionDecomposerAgent import QuestionAnalysis
        from dataMCP.server import DatabaseMCPServer


# ==================== MINIMAL DATA STRUCTURES ====================

@dataclass
class ColumnInfo:
    """Basic column information"""
    name: str
    type: str
    is_primary_key: bool = False
    is_foreign_key: bool = False

@dataclass
class TableInfo:
    """Basic table information"""
    table_name: str
    columns: List[ColumnInfo]
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)
    
@dataclass
class JoinInfo:
    """Simple join information"""
    from_table: str
    to_table: str
    from_column: str
    to_column: str
    join_type: str = "INNER"

@dataclass
class FilterInfo:
    """Validated filter"""
    table: str
    column: str
    operator: str
    value: Any
    data_type: str
    is_valid: bool

@dataclass
class SchemaContext:
    """Output from Agent #2 - SIMPLIFIED"""
    selected_tables: List[str]
    table_details: Dict[str, TableInfo]
    required_joins: List[JoinInfo]
    recommended_columns: List[str]
    validated_filters: List[FilterInfo]
    confidence: float
    warnings: List[str] = field(default_factory=list)
    notes: str = ""


# ==================== SIMPLIFIED AGENT ====================

class SchemaScout:
    """
    Agent #2: SIMPLIFIED Schema Scout
    
    Does ONLY the essentials:
    - Dynamic table lookup (queries actual DB)
    - Schema retrieval (columns only)
    - Sample data (3 rows)
    - Column recommendation (basic heuristics)
    - JOIN detection (FK only)
    """
    
    def __init__(self, db_path: str = 'bike_store.db'):
        self.db_path = db_path
        self.mcp = DatabaseMCPServer(db_path=db_path)
        self._all_tables_cache = None
        # Use glm4:9b for Agent #2 (good at context understanding)
        self.model = os.getenv('AGENT2_MODEL', os.getenv('OLLAMA_MODEL', 'glm4:9b'))
        print(f"🤖 Agent #2 using model: {self.model}")
    
    def scout(self, question_analysis: QuestionAnalysis) -> SchemaContext:
        """
        Main entry point - SIMPLIFIED WORKFLOW
        
        Steps:
        1. Map entities → tables
        2. Get schema for each table
        3. Get sample data
        4. Recommend columns
        5. Find JOINs (if multi-table)
        6. Validate filters (if any)
        """
        print("\n" + "=" * 80)
        print("🔭 AGENT #2: SCHEMA SCOUT (SIMPLIFIED)")
        print("=" * 80)
        
        warnings = []
        
        # STEP 1: Map entities to tables
        print("\n[1/4] 🔍 Mapping entities to tables...")
        selected_tables = self._map_entities_to_tables(question_analysis.entities)
        print(f"   → Tables: {selected_tables}")
        
        if not selected_tables:
            warnings.append("No tables found for entities")
            return self._empty_context(warnings)
        
        # STEP 2: Get schema + samples
        print("\n[2/4] 📊 Getting schema and samples...")
        table_details = {}
        for table in selected_tables:
            info = self._get_table_info(table)
            if info:
                table_details[table] = info
                print(f"   → {table}: {len(info.columns)} columns, {len(info.sample_rows)} samples")
        
        # STEP 3: Recommend columns
        print("\n[3/4] 💡 Recommending columns...")
        recommended_columns = self._recommend_columns(question_analysis, table_details)
        print(f"   → {len(recommended_columns)} columns")
        
        # STEP 4: Find JOINs (if multiple tables)
        print("\n[4/4] 🔗 Finding JOINs...")
        required_joins = self._find_joins(selected_tables, table_details) if len(selected_tables) > 1 else []
        print(f"   → {len(required_joins)} joins")
        
        # STEP 5: Validate filters (simple)
        validated_filters = self._validate_filters(question_analysis.filters, table_details)
        
        # Build output
        confidence = 1.0 if not warnings else 0.8
        
        schema_context = SchemaContext(
            selected_tables=selected_tables,
            table_details=table_details,
            required_joins=required_joins,
            recommended_columns=recommended_columns,
            validated_filters=validated_filters,
            confidence=confidence,
            warnings=warnings,
            notes=f"Found {len(selected_tables)} tables"
        )
        
        print(f"\n✅ Complete! Confidence: {confidence:.2f}")
        print("=" * 80)
        
        return schema_context
    
    # ==================== STEP 1: DYNAMIC TABLE MAPPING ====================
    
    def _get_all_tables(self) -> List[str]:
        """Get all table names from database (cached)"""
        if self._all_tables_cache is None:
            try:
                result = self.mcp.list_tables()
                print(f"   DEBUG: MCP list_tables result - success: {result.success}, data: {result.data}")
                if result.success:
                    self._all_tables_cache = result.data
                else:
                    print(f"   ERROR: MCP list_tables failed: {result.error}")
                    self._all_tables_cache = []
            except Exception as e:
                print(f"   ERROR: Exception in _get_all_tables: {e}")
                import traceback
                traceback.print_exc()
                self._all_tables_cache = []
        return self._all_tables_cache
    
    def _map_entities_to_tables(self, entities: List[str]) -> List[str]:
        """
        Map entities to actual table names by querying the database.
        
        Algorithm:
        1. Get all tables from DB
        2. For each entity, find matching table(s):
           - Exact match (e.g., "customers" → "customers")
           - Plural/singular (e.g., "customer" → "customers")
           - Substring match (e.g., "product" in "products")
        3. Return unique matches
        """
        if not entities:
            print(f"   ⚠️  No entities provided!")
            return []
        
        all_tables = self._get_all_tables()
        if not all_tables:
            print(f"   ⚠️  No tables found in database!")
            return []
        
        print(f"   → Entities to map: {entities}")
        print(f"   → Available tables: {all_tables}")
        
        matched_tables = []
        
        for entity in entities:
            entity_lower = entity.lower().strip()
            print(f"   → Trying to match entity: '{entity_lower}'")
            
            # Strategy 1: Exact match
            if entity_lower in all_tables:
                if entity_lower not in matched_tables:
                    matched_tables.append(entity_lower)
                    print(f"      ✓ Exact match: {entity_lower}")
                continue
            
            # Strategy 2: Add 's' for plural (customer → customers)
            plural = entity_lower + 's' if not entity_lower.endswith('s') else entity_lower
            if plural in all_tables:
                if plural not in matched_tables:
                    matched_tables.append(plural)
                    print(f"      ✓ Plural match: {plural}")
                continue
            
            # Strategy 3: Remove 's' for singular (customers → customer)
            singular = entity_lower[:-1] if entity_lower.endswith('s') else entity_lower
            if singular in all_tables:
                if singular not in matched_tables:
                    matched_tables.append(singular)
                    print(f"      ✓ Singular match: {singular}")
                continue
            
            # Strategy 4: Substring match (entity in table_name OR table_name in entity)
            for table in all_tables:
                if entity_lower in table or table in entity_lower:
                    if table not in matched_tables:
                        matched_tables.append(table)
                        print(f"      ✓ Substring match: {table}")
                    break
            else:
                print(f"      ✗ No match found for '{entity_lower}'")
        
        return matched_tables
    
    # ==================== STEP 2: SCHEMA + SAMPLES ====================
    
    def _get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """
        Get basic table info: columns + sample rows.
        
        """
        try:
            # Get columns
            result = self.mcp.get_table_info(table_name)
            if not result.success:
                return None
            
            columns = []
            for col in result.data['columns']:
                col_info = ColumnInfo(
                    name=col['name'],
                    type=col['type'],
                    is_primary_key=col['name'].endswith('_id') and col['name'].startswith(table_name[:-1]),
                    is_foreign_key=col['name'].endswith('_id') and not col['name'].startswith(table_name[:-1])
                )
                columns.append(col_info)
            
            # Get samples
            sample_result = self.mcp.get_sample_data(table_name, limit=3)
            samples = sample_result.data['rows'] if sample_result.success else []
            
            return TableInfo(
                table_name=table_name,
                columns=columns,
                sample_rows=samples
            )
            
        except Exception as e:
            print(f"   ⚠️  Error getting info for {table_name}: {e}")
            return None
    
    # ==================== STEP 3: LLM-POWERED COLUMN RECOMMENDATION ====================
    
    def _recommend_columns(
        self,
        question_analysis: QuestionAnalysis,
        table_details: Dict[str, TableInfo]
    ) -> List[str]:
        """
        LLM-POWERED column recommendation.
        
        Asks the LLM to intelligently select columns based on:
        - Question intent
        - Available columns
        - Sample data (to understand what columns contain)
        - Query type (SELECT, COUNT, AGGREGATION)
        """
        
        # Build context about available columns with sample data
        columns_context = self._build_columns_context(table_details)
        
        # Build prompt for LLM
        prompt = f"""Given this natural language question about a database, recommend which columns to SELECT.

QUESTION: "{question_analysis.original_question}"

QUERY TYPE: {question_analysis.query_type}

AGGREGATIONS: {question_analysis.aggregations if question_analysis.aggregations else "None"}

AVAILABLE COLUMNS:
{columns_context}

RULES:
1. For COUNT(*) queries with no GROUP BY: Return empty array []
2. For COUNT queries with GROUP BY: Return the grouping columns
3. For AGGREGATION queries: Include both aggregation columns and GROUP BY columns
4. For SELECT queries: Return columns that answer the question (not all columns)
5. Only recommend columns that actually exist in the schema
6. Use format: "table_name.column_name"
7. Return ONLY columns, not aggregation functions (Agent #3 handles that)

EXAMPLES:
Question: "How many customers are there?"
Recommended: []

Question: "Count customers by state"
Recommended: ["customers.state"]

Question: "What's the average product price by brand?"
Recommended: ["brands.brand_name", "products.list_price"]

Question: "Show me customer names"
Recommended: ["customers.first_name", "customers.last_name"]

Question: "What stores do we have?"
Recommended: ["stores.store_name", "stores.city", "stores.state"]

Question: "List all orders"
Recommended: ["orders.order_id", "orders.order_date", "orders.order_status"]

Return ONLY a JSON array of column names:
["column1", "column2", ...]
"""
        
        try:
            # Get LLM recommendation
            import ollama
            client = ollama.Client(host=os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
            
            response = client.chat(
                model=self.model,  # Use Agent #2's configured model
                messages=[
                    {'role': 'system', 'content': 'You are a database expert. Return only valid JSON arrays.'},
                    {'role': 'user', 'content': prompt}
                ],
                format='json'
            )
            
            content = response['message']['content'].strip()
            
            # Parse JSON response
            recommended = json.loads(content)
            
            # Validate it's a list
            if not isinstance(recommended, list):
                print(f"   ⚠️  LLM returned non-list, using fallback")
                return self._fallback_column_recommendation(question_analysis, table_details)
            
            # Clean up recommendations
            cleaned = []
            for col in recommended:
                if isinstance(col, str) and col.strip():
                    cleaned.append(col.strip())
            
            return cleaned if cleaned else self._fallback_column_recommendation(question_analysis, table_details)
            
        except Exception as e:
            print(f"   ⚠️  LLM column recommendation failed: {e}")
            return self._fallback_column_recommendation(question_analysis, table_details)
    
    def _build_columns_context(self, table_details: Dict[str, TableInfo]) -> str:
        """
        Build a context string showing available columns with sample data.
        
        This helps the LLM understand WHAT each column contains.
        """
        context_parts = []
        
        for table_name, table_info in table_details.items():
            context_parts.append(f"\n{table_name.upper()}:")
            
            for col in table_info.columns:
                # Get sample values for this column
                sample_values = []
                for row in table_info.sample_rows[:3]:
                    val = row.get(col.name)
                    if val is not None:
                        sample_values.append(str(val)[:50])  # Truncate long values
                
                samples_str = ", ".join(sample_values[:3]) if sample_values else "no data"
                
                # Format: column_name (TYPE) - samples: value1, value2, value3
                context_parts.append(
                    f"  - {col.name} ({col.type}) - samples: {samples_str}"
                )
        
        return "\n".join(context_parts)
    
    def _fallback_column_recommendation(
        self,
        question_analysis: QuestionAnalysis,
        table_details: Dict[str, TableInfo]
    ) -> List[str]:
        """
        Fallback when LLM fails - use SIMPLE heuristics.
        """
        recommended = []
        
        # For COUNT(*): return empty if single table, no complex queries
        if question_analysis.aggregations:
            for agg in question_analysis.aggregations:
                if agg.get('function') == 'COUNT' and agg.get('column') == '*':
                    # Simple COUNT(*) - return empty
                    if len(question_analysis.entities) == 1:
                        return []
        
        # For AGGREGATION: try to extract from question_analysis
        if question_analysis.aggregations:
            for agg in question_analysis.aggregations:
                col = agg.get('column', '*')
                if col and col != '*':
                    # Find this column in schema
                    for table_name, table_info in table_details.items():
                        for c in table_info.columns:
                            if c.name.lower() == col.lower():
                                recommended.append(f"{table_name}.{c.name}")
        
        # For SELECT: return "name" columns as safe default
        if not recommended:
            for table_name, table_info in table_details.items():
                for col in table_info.columns:
                    if 'name' in col.name.lower() or col.is_primary_key:
                        recommended.append(f"{table_name}.{col.name}")
                        if len(recommended) >= 3:
                            break
        
        # Ultimate fallback: first 3 columns
        if not recommended:
            for table_name, table_info in table_details.items():
                for col in table_info.columns[:3]:
                    recommended.append(f"{table_name}.{col.name}")
        
        return recommended
    
    # ==================== STEP 4: JOIN DETECTION ====================
    
    def _find_joins(
        self,
        tables: List[str],
        table_details: Dict[str, TableInfo]
    ) -> List[JoinInfo]:
        """
        Find JOINs using SIMPLE rule:
        
        If table A has column "x_id" and table "xs" exists → JOIN
        """
        joins = []
        
        for table1 in tables:
            info1 = table_details.get(table1)
            if not info1:
                continue
            
            for col in info1.columns:
                if col.is_foreign_key:
                    # Extract referenced table name
                    ref_table = col.name.replace('_id', '') + 's'
                    
                    # Check if ref_table is in our selected tables
                    if ref_table in tables:
                        joins.append(JoinInfo(
                            from_table=table1,
                            to_table=ref_table,
                            from_column=col.name,
                            to_column=col.name
                        ))
        
        return joins
    
    # ==================== STEP 5: FILTER VALIDATION ====================

    def _validate_filters(
        self,
        filters: List[Dict[str, Any]],
        table_details: Dict[str, TableInfo]
    ) -> List[FilterInfo]:
        """
        Validate filters - SIMPLE check: does column exist?
        """
        validated = []
        
        # Handle None or empty filters
        if not filters:
            return validated
        
        for f in filters:
            column_name = f.get('column', '').lower()
            found = False
            
            for table_name, table_info in table_details.items():
                for col in table_info.columns:
                    if col.name.lower() == column_name:
                        validated.append(FilterInfo(
                            table=table_name,
                            column=col.name,
                            operator=f.get('operator', '='),
                            value=f.get('value'),
                            data_type=col.type,
                            is_valid=True
                        ))
                        found = True
                        break
                if found:
                    break
            
            if not found:
                validated.append(FilterInfo(
                    table="unknown",
                    column=column_name,
                    operator=f.get('operator', '='),
                    value=f.get('value'),
                    data_type="unknown",
                    is_valid=False
                ))
        
        return validated

    # ==================== HELPERS ====================
    
    def _empty_context(self, warnings: List[str]) -> SchemaContext:
        """Return empty context when nothing found"""
        return SchemaContext(
            selected_tables=[],
            table_details={},
            required_joins=[],
            recommended_columns=[],
            validated_filters=[],
            confidence=0.0,
            warnings=warnings
        )
    
    def close(self):
        """Cleanup"""
        if self.mcp:
            self.mcp.close()


# ==================== TEST ====================

def test_schema_scout():
    """Test with simple questions"""
    try:
        from agents.questionDecomposerAgent import QuestionDecomposer
    except ImportError:
        from agent.questionDecomposerAgent import QuestionDecomposer
    
    print("=" * 80)
    print("Testing SIMPLIFIED Schema Scout")
    print("=" * 80)
    
    decomposer = QuestionDecomposer()
    scout = SchemaScout()
    
    questions = [
        "What stores do we have?",
        "How many customers are there?",
        "Show me products from Trek brand",
    ]
    
    for i, q in enumerate(questions, 1):
        print(f"\n{'=' * 80}")
        print(f"Test {i}: {q}")
        print('=' * 80)
        
        try:
            # Agent #1 will print its own output now
            analysis = decomposer.decompose(q)
            
            # Agent #2 will print its own output
            context = scout.scout(analysis)
            
            print("\n✅ PIPELINE COMPLETE")
            print(f"Final confidence: {context.confidence:.2f}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    scout.close()
    print("\n" + "=" * 80)
    print("Tests complete!")
    print("=" * 80)

if __name__ == "__main__":
    test_schema_scout()
