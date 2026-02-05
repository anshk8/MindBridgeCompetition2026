"""
Schema Scout Agent - CLEAN REWRITE

WHAT IT DOES:
1. Maps entities → tables
2. Gets schema + samples from database
3. Recommends columns (LLM-based)
4. Finds JOINs (database FK-based)

THAT'S IT. No fallbacks, no heuristics, no complexity.
"""

import os
import json
import sqlite3
from typing import Dict, List, Any
from dataclasses import dataclass, field
import ollama

try:
    from dataMCP.server import DatabaseMCPServer
    from agents.questionDecomposerAgent import QuestionAnalysis
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from questionDecomposerAgent import QuestionAnalysis
    from dataMCP.server import DatabaseMCPServer


# ==================== DATA STRUCTURES ====================

@dataclass
class ColumnInfo:
    name: str
    type: str
    is_primary_key: bool = False
    is_foreign_key: bool = False

@dataclass
class TableInfo:
    table_name: str
    columns: List[ColumnInfo]
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class JoinInfo:
    from_table: str
    to_table: str
    from_column: str
    to_column: str

@dataclass
class SchemaContext:
    """What Agent #3 needs to generate SQL"""
    selected_tables: List[str]
    table_details: Dict[str, TableInfo]
    required_joins: List[JoinInfo]
    recommended_columns: List[str]  # Can include AVG(), COUNT(), etc.
    confidence: float


# ==================== AGENT ====================

class SchemaScout:
    """Agent #2: Database Schema Expert"""
    
    def __init__(self, db_path: str = 'bike_store.db'):
        self.db_path = db_path
        self.mcp = DatabaseMCPServer(db_path=db_path)
        self.model = os.getenv('AGENT2_MODEL', 'llama3.2')
        self.client = ollama.Client(host=os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
    
    def scout(self, question_analysis: QuestionAnalysis) -> SchemaContext:
        """Main workflow - 4 simple steps"""
        print("\n🔭 AGENT #2: SCHEMA SCOUT")
        print("="*80)
        
        # STEP 1: Find tables
        tables = self._find_tables(question_analysis.entities)
        print(f"[1/4] Tables: {tables}")
        
        # STEP 2: Get schema + samples
        table_details = self._get_schemas(tables)
        print(f"[2/4] Got schema for {len(table_details)} tables")
        
        # STEP 3: Recommend columns (LLM does the work)
        columns = self._recommend_columns(question_analysis, table_details)
        print(f"[3/4] Recommended {len(columns)} columns")
        
        # STEP 4: Find JOINs (database does the work)
        joins = self._find_joins(tables) if len(tables) > 1 else []
        print(f"[4/4] Found {len(joins)} joins")
        
        print("="*80)
        
        return SchemaContext(
            selected_tables=tables,
            table_details=table_details,
            required_joins=joins,
            recommended_columns=columns,
            confidence=1.0 if tables else 0.0
        )
    
    # ==================== STEP 1: FIND TABLES ====================
    
    def _find_tables(self, entities: List[str]) -> List[str]:
        """Map entities to actual table names"""
        all_tables_result = self.mcp.list_tables()
        all_tables = all_tables_result.data if all_tables_result.success else []
        
        # Create lowercase mapping
        table_map = {t.lower(): t for t in all_tables}
        
        matched = []
        for entity in entities:
            entity = entity.lower().strip()
            
            # Try exact, plural, singular
            candidates = [entity, entity + 's', entity[:-1] if entity.endswith('s') else entity]
            
            for candidate in candidates:
                if candidate in table_map:
                    actual_table = table_map[candidate]
                    if actual_table not in matched:
                        matched.append(actual_table)
                    break
        
        return matched
    
    # ==================== STEP 2: GET SCHEMAS ====================
    
    def _get_schemas(self, tables: List[str]) -> Dict[str, TableInfo]:
        """Get schema + samples using PRAGMA for PK/FK"""
        table_details = {}
        
        for table in tables:
            result = self.mcp.get_table_info(table)
            if not result.success:
                continue
            
            # Get PK/FK from database
            pks = self._get_primary_keys(table)
            fks = {fk['from'] for fk in self._get_foreign_keys(table)}
            
            columns = []
            for col in result.data['columns']:
                columns.append(ColumnInfo(
                    name=col['name'],
                    type=col['type'],
                    is_primary_key=col['name'] in pks,
                    is_foreign_key=col['name'] in fks
                ))
            
            sample_result = self.mcp.get_sample_data(table, limit=3)
            samples = sample_result.data['rows'] if sample_result.success else []
            
            table_details[table] = TableInfo(
                table_name=table,
                columns=columns,
                sample_rows=samples
            )
        
        return table_details
    
    def _get_primary_keys(self, table: str) -> set:
        """Get PK columns from PRAGMA table_info"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        rows = cursor.fetchall()
        conn.close()
        return {row[1] for row in rows if row[5] > 0}
    
    def _get_foreign_keys(self, table: str) -> List[Dict[str, str]]:
        """Get FK info from PRAGMA foreign_key_list"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA foreign_key_list({table})")
        rows = cursor.fetchall()
        conn.close()
        return [{'table': row[2], 'from': row[3], 'to': row[4]} for row in rows]
    
    # ==================== STEP 3: RECOMMEND COLUMNS ====================
    
    def _recommend_columns(self, qa: QuestionAnalysis, tables: Dict[str, TableInfo]) -> List[str]:
        """Ask LLM which columns/expressions to SELECT"""
        context = self._build_column_context(tables)
        
        prompt = f"""Given this question, recommend which columns/expressions to SELECT.

QUESTION: "{qa.original_question}"
QUERY TYPE: {qa.query_type}

AVAILABLE COLUMNS:
{context}

RULES:
1. For "How many X?" → return []
2. For "Average/Sum/Max/Min" → return aggregation like AVG(table.column)
3. For "Show me" → return relevant columns like table.column_name
4. ONLY return columns that exist in the schema above
5. Format: "table_name.column_name" or "FUNC(table.column)"

EXAMPLES:
"How many customers?" → []
"Average product price?" → ["AVG(products.list_price)"]
"Show customer names" → ["customers.first_name", "customers.last_name"]

Return JSON array: ["col1", "col2", ...]
"""
        
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': 'You are a SQL expert. Return only JSON.'},
                    {'role': 'user', 'content': prompt}
                ],
                format='json'
            )
            
            result = json.loads(response['message']['content'])
            return result if isinstance(result, list) else []
            
        except Exception as e:
            print(f"   ⚠️ LLM failed: {e}")
            return []  # Clean failure - let Agent #3 handle empty columns
    
    def _build_column_context(self, tables: Dict[str, TableInfo]) -> str:
        """Show LLM what columns exist with sample data"""
        parts = []
        for table, info in tables.items():
            parts.append(f"\n{table.upper()}:")
            for col in info.columns:
                samples = [str(row.get(col.name, '')) for row in info.sample_rows[:3]] 
                parts.append(f"  - {col.name} ({col.type}): {', '.join(samples)}")
        return ''.join(parts)
    
    # ==================== STEP 4: FIND JOINS ====================
    
    def _find_joins(self, tables: List[str]) -> List[JoinInfo]:
        """Use PRAGMA foreign_key_list to find JOINs"""
        joins = []
        
        for table in tables:
            fks = self._get_foreign_keys(table)
            
            for fk in fks:
                if fk['table'] in tables:
                    joins.append(JoinInfo(
                        from_table=table,
                        to_table=fk['table'],
                        from_column=fk['from'],
                        to_column=fk['to']
                    ))
        
        return joins
    
    def close(self):
        self.mcp.close()
