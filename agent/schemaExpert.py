"""
Schema Scout Agent - Phase 2: Database Intelligence

This agent is responsible for:
1. Discovering relevant tables from user entities
2. Retrieving detailed schema information
3. Collecting sample data to prevent hallucination
4. Calculating column statistics for validation
5. Finding join paths between tables
6. Recommending columns for SELECT queries
7. Validating filters against actual data

The output provides rich database context that enables Agent #3
to generate accurate, grounded SQL queries.
"""

import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field

# NOTE: Run this script from project root directory:
#   cd /Users/anshnandwani/Downloads/carleton_competition_winter_2026-main
#   python3 agent/schemaExpert.py
from dataMCP.server import DatabaseMCPServer
from agent.questionDecomposerAgent import QuestionAnalysis


# ==================== OUTPUT DATA STRUCTURES ====================

@dataclass
class ColumnInfo:
    """Detailed information about a single column"""
    name: str
    type: str
    is_nullable: Optional[bool] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_ref: Optional[Dict[str, str]] = None  # {"table": "x", "column": "y"}


@dataclass
class ColumnStats:
    """Statistical information about a column"""
    column_name: str
    data_type: str
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    avg_value: Optional[float] = None
    distinct_count: Optional[int] = None
    null_count: Optional[int] = None
    null_percentage: Optional[float] = None
    sample_values: List[Any] = field(default_factory=list)


@dataclass
class TableInfo:
    """Detailed information about a single table"""
    table_name: str
    row_count: int
    columns: List[ColumnInfo]
    sample_rows: List[Dict[str, Any]]
    primary_keys: List[str]
    foreign_keys: List[Dict[str, Any]]  # {"column": "x", "ref_table": "y", "ref_column": "z"}
    column_stats: Dict[str, ColumnStats] = field(default_factory=dict)
    
    def get_column_names(self) -> List[str]:
        """Get list of all column names"""
        return [col.name for col in self.columns]
    
    def has_column(self, column_name: str) -> bool:
        """Check if table has a specific column"""
        return column_name.lower() in [col.name.lower() for col in self.columns]
    
    def get_column_type(self, column_name: str) -> Optional[str]:
        """Get data type of a column"""
        for col in self.columns:
            if col.name.lower() == column_name.lower():
                return col.type
        return None


@dataclass
class JoinInfo:
    """Information about a required join between tables"""
    from_table: str
    to_table: str
    from_column: str
    to_column: str
    join_type: str  # "INNER", "LEFT", "RIGHT"
    reasoning: str
    confidence: float = 0.9


@dataclass
class FilterInfo:
    """Validated filter information with actual column and data type"""
    table: str
    column: str
    operator: str
    value: Any
    data_type: str
    is_valid: bool
    validation_message: Optional[str] = None


@dataclass
class SchemaContext:
    """
    Output from Agent #2: Schema Scout
    
    This is the comprehensive database context that Agent #3 will use
    to generate accurate SQL queries.
    """
    # Tables selected
    selected_tables: List[str]
    
    # Detailed table information
    table_details: Dict[str, TableInfo]
    
    # Join information (if multiple tables)
    required_joins: List[JoinInfo]
    
    # Column recommendations
    recommended_columns: List[str]
    
    # Validated filters
    validated_filters: List[FilterInfo]
    
    # Metadata
    confidence: float
    warnings: List[str] = field(default_factory=list)
    notes: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    def get_all_columns(self) -> List[str]:
        """Get all available columns across all tables"""
        all_cols = []
        for table_name, table_info in self.table_details.items():
            for col in table_info.columns:
                all_cols.append(f"{table_name}.{col.name}")
        return all_cols


# ==================== MAIN AGENT CLASS ====================

class SchemaScout:
    """
    Agent #2: Schema Scout (Database Expert)
    
    This agent bridges the gap between question understanding (Agent #1)
    and SQL generation (Agent #3) by providing rich, accurate database context.
    
    Key responsibilities:
    - Table discovery and selection
    - Schema retrieval
    - Sample data collection (prevents hallucination!)
    - Statistical analysis
    - Join path detection
    - Column recommendation
    """
    
    def __init__(self, db_path: str = 'bike_store.db'):
        """
        Initialize the Schema Scout.
        
        Args:
            db_path: Path to the DuckDB database
        """
        self.db_path = db_path
        self.mcp = DatabaseMCPServer(db_path=db_path)
        self.schema_cache = None  # Cache full schema to avoid repeated queries
        self._all_tables = None  # Cache table list
        
    def scout(self, question_analysis: QuestionAnalysis) -> SchemaContext:
        """
        Main method: Build comprehensive schema context from question analysis.
        
        This is the primary entry point for Agent #2.
        
        Args:
            question_analysis: Output from Agent #1 (QuestionDecomposer)
            
        Returns:
            SchemaContext with all database information needed for SQL generation
        """
        print("\n" + "=" * 80)
        print("🔭 AGENT #2: SCHEMA SCOUT - Starting database intelligence gathering")
        print("=" * 80)
        
        warnings = []
        
        # Step 1: Discover relevant tables
        print("\n[1/6] 🔍 Discovering relevant tables...")
        selected_tables = self._discover_tables(question_analysis.entities)
        print(f"   → Found {len(selected_tables)} tables: {', '.join(selected_tables)}")

        
        # Step 2: Retrieve detailed schema for each table and store info
        print("\n[2/6] 📊 Retrieving schema information...")
        table_details = {}
        for table in selected_tables:
            table_info = self._retrieve_schema(table)
            if table_info:
                table_details[table] = table_info
            else:
                warnings.append(f"Could not retrieve schema for table: {table}")
        
        # Step 3: Get sample data for each table
        print("\n[3/6] 🎲 Collecting sample data...")
        for table_name, table_info in table_details.items():
            samples = self._get_samples(table_name, limit=3)
            table_info.sample_rows = samples
            print(f"   → {table_name}: {len(samples)} sample rows")
        
        # Step 4: Calculate column statistics
        print("\n[4/6] 📈 Calculating column statistics...")
        for table_name, table_info in table_details.items():
            stats = self._calculate_stats(table_name, table_info)
            table_info.column_stats = stats
            print(f"   → {table_name}: Statistics for {len(stats)} columns")
        
        # Step 5: Find join paths (if multiple tables)
        print("\n[5/6] 🔗 Finding join paths...")
        required_joins = []
        if len(selected_tables) > 1:
            required_joins = self._find_join_paths(selected_tables, table_details)
            print(f"   → Found {len(required_joins)} potential joins")
            for join in required_joins:
                print(f"      {join.from_table}.{join.from_column} → {join.to_table}.{join.to_column}")
        else:
            print("   → Single table query, no joins needed")
        
        # Step 6: Recommend columns
        print("\n[6/6] 💡 Recommending columns...")
        recommended_columns = self._recommend_columns(question_analysis, table_details)
        print(f"   → Recommended {len(recommended_columns)} columns: {', '.join(recommended_columns)}")
        
        # Step 7: Validate filters
        print("\n[7/7] ✅ Validating filters...")
        validated_filters = self._validate_filters(question_analysis.filters, table_details)
        print(f"   → Validated {len(validated_filters)} filters")
        
        # Calculate confidence score
        confidence = self._calculate_confidence(
            question_analysis, 
            selected_tables, 
            table_details, 
            warnings
        )
        
        # Build final context
        schema_context = SchemaContext(
            selected_tables=selected_tables,
            table_details=table_details,
            required_joins=required_joins,
            recommended_columns=recommended_columns,
            validated_filters=validated_filters,
            confidence=confidence,
            warnings=warnings,
            notes=f"Schema scouting complete for {len(selected_tables)} tables"
        )
        
        print(f"\n✅ Schema Scout complete! Confidence: {confidence:.2f}")
        print("=" * 80 + "\n")
        
        return schema_context
    
    # ==================== STEP 1: TABLE DISCOVERY ====================
    
    def _discover_tables(self, entities: List[str]) -> List[str]:
        """
        Discover which database tables are needed based on entities.
        
        Args:
            entities: List of entity names from Agent #1
            
        Returns:
            List of actual table names from the database
        """
        if not entities:
            return []
        
        all_tables = self._get_all_tables()
        selected_tables = []
        
        # Known table mappings for bike store
        table_mappings = {
            'product': 'products',
            'bike': 'products',
            'customer': 'customers',
            'order': 'orders',
            'store': 'stores',
            'staff': 'staffs',
            'brand': 'brands',
            'category': 'categories',
            'stock': 'stocks',
            'inventory': 'stocks',
            'order_item': 'order_items',
            'item': 'order_items'
        }
        
        for entity in entities:
            entity_lower = entity.lower().strip()
            
            # Check if entity is already a valid table name
            if entity_lower in all_tables:
                if entity_lower not in selected_tables:
                    selected_tables.append(entity_lower)
            # Check if entity maps to a known table
            elif entity_lower in table_mappings:
                table = table_mappings[entity_lower]
                if table not in selected_tables:
                    selected_tables.append(table)
            # Try fuzzy matching
            else:
                for table in all_tables:
                    if entity_lower in table or table in entity_lower:
                        if table not in selected_tables:
                            selected_tables.append(table)
                            break
        
        return selected_tables
    
    def _get_all_tables(self) -> List[str]:
        """Get list of all tables in the database (cached)"""
        if self._all_tables is None:
            result = self.mcp.list_tables()
            if result.success:
                self._all_tables = result.data
            else:
                self._all_tables = []
        return self._all_tables
    
    # ==================== STEP 2: SCHEMA RETRIEVAL ====================
    
    def _retrieve_schema(self, table_name: str) -> Optional[TableInfo]:
        """
        Retrieve detailed schema information for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            TableInfo object or None if retrieval fails
        """
        try:
            # Get table info from MCP
            table_info_result = self.mcp.get_table_info(table_name)
            if not table_info_result.success:
                return None
            
            table_data = table_info_result.data
            
            # Get row count
            stats_result = self.mcp.get_table_statistics(table_name)
            row_count = stats_result.data.get('row_count', 0) if stats_result.success else 0
            
            # Parse columns
            columns = []
            primary_keys = []
            foreign_keys = []
            
            for col in table_data['columns']:
                col_info = ColumnInfo(
                    name=col['name'],
                    type=col['type'],
                    is_nullable=col.get('null', 'YES') == 'YES'
                )
                
                # Detect primary keys (heuristic: columns named 'id' or ending in '_id' at start)
                if col['name'].lower() == f"{table_name[:-1]}_id" or col['name'].lower() == 'id':
                    col_info.is_primary_key = True
                    primary_keys.append(col['name'])
                
                # Detect foreign keys (heuristic: columns ending in '_id' that aren't the primary key)
                if col['name'].lower().endswith('_id') and not col_info.is_primary_key:
                    col_info.is_foreign_key = True
                    # Try to infer referenced table
                    ref_table = col['name'].lower().replace('_id', '') + 's'
                    if ref_table in self._get_all_tables():
                        col_info.foreign_key_ref = {
                            "table": ref_table,
                            "column": col['name']
                        }
                        foreign_keys.append({
                            "column": col['name'],
                            "ref_table": ref_table,
                            "ref_column": col['name']
                        })
                
                columns.append(col_info)
            
            return TableInfo(
                table_name=table_name,
                row_count=row_count,
                columns=columns,
                sample_rows=[],  # Filled in next step
                primary_keys=primary_keys,
                foreign_keys=foreign_keys
            )
            
        except Exception as e:
            print(f"   ⚠️  Error retrieving schema for {table_name}: {e}")
            return None
    
    # ==================== STEP 3: SAMPLE DATA RETRIEVAL ====================
    
    def _get_samples(self, table_name: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Get sample rows from a table.
        
        This is CRITICAL for preventing hallucination!
        
        Args:
            table_name: Name of the table
            limit: Number of sample rows to retrieve
            
        Returns:
            List of sample rows as dictionaries
        """
        try:
            result = self.mcp.get_sample_data(table_name, limit=limit)
            if result.success:
                return result.data['rows']
            return []
        except Exception as e:
            print(f"   ⚠️  Error getting samples from {table_name}: {e}")
            return []
    
    # ==================== STEP 4: COLUMN STATISTICS ====================
    
    def _calculate_stats(self, table_name: str, table_info: TableInfo) -> Dict[str, ColumnStats]:
        """
        Calculate statistics for each column.
        
        Args:
            table_name: Name of the table
            table_info: TableInfo object
            
        Returns:
            Dictionary mapping column names to ColumnStats
        """
        stats = {}
        
        for col in table_info.columns:
            col_stats = ColumnStats(
                column_name=col.name,
                data_type=col.type
            )
            
            try:
                # For numeric columns: get min, max, avg
                if self._is_numeric_type(col.type):
                    query = f"""
                        SELECT 
                            MIN({col.name}) as min_val,
                            MAX({col.name}) as max_val,
                            AVG({col.name}) as avg_val,
                            COUNT(DISTINCT {col.name}) as distinct_count,
                            COUNT(*) - COUNT({col.name}) as null_count
                        FROM {table_name}
                    """
                    result = self.mcp.execute_query(query, limit=1)
                    if result.success and result.data['rows']:
                        row = result.data['rows'][0]
                        col_stats.min_value = row.get('min_val')
                        col_stats.max_value = row.get('max_val')
                        col_stats.avg_value = row.get('avg_val')
                        col_stats.distinct_count = row.get('distinct_count')
                        col_stats.null_count = row.get('null_count')
                        if table_info.row_count > 0:
                            col_stats.null_percentage = (col_stats.null_count / table_info.row_count) * 100
                
                # For text columns: get distinct count and sample values
                elif self._is_text_type(col.type):
                    # Get distinct count
                    query = f"SELECT COUNT(DISTINCT {col.name}) as distinct_count FROM {table_name}"
                    result = self.mcp.execute_query(query, limit=1)
                    if result.success and result.data['rows']:
                        col_stats.distinct_count = result.data['rows'][0].get('distinct_count')
                    
                    # Get sample values (if distinct count is small, these are likely categories)
                    if col_stats.distinct_count and col_stats.distinct_count < 50:
                        values_result = self.mcp.get_column_values(table_name, col.name, distinct=True, limit=20)
                        if values_result.success:
                            col_stats.sample_values = values_result.data['values']
                
                stats[col.name] = col_stats
                
            except Exception as e:
                # If stats fail for a column, still include basic info
                stats[col.name] = col_stats
        
        return stats
    
    def _is_numeric_type(self, data_type: str) -> bool:
        """Check if a data type is numeric"""
        numeric_types = ['INTEGER', 'BIGINT', 'SMALLINT', 'DECIMAL', 'NUMERIC', 'REAL', 'DOUBLE', 'FLOAT']
        return any(t in data_type.upper() for t in numeric_types)
    
    def _is_text_type(self, data_type: str) -> bool:
        """Check if a data type is text"""
        text_types = ['VARCHAR', 'CHAR', 'TEXT', 'STRING']
        return any(t in data_type.upper() for t in text_types)
    
    # ==================== STEP 5: JOIN PATH DISCOVERY ====================
    
    def _find_join_paths(self, tables: List[str], table_details: Dict[str, TableInfo]) -> List[JoinInfo]:
        """
        Find how to join multiple tables together.
        
        Args:
            tables: List of table names
            table_details: Dictionary of TableInfo objects
            
        Returns:
            List of JoinInfo objects
        """
        joins = []
        
        # For each pair of tables, look for foreign key relationships
        for i, table1 in enumerate(tables):
            for table2 in tables[i+1:]:
                join_info = self._find_join_between_tables(
                    table1, table2, 
                    table_details.get(table1), 
                    table_details.get(table2)
                )
                if join_info:
                    joins.append(join_info)
        
        return joins
    
    def _find_join_between_tables(
        self, 
        table1: str, 
        table2: str, 
        info1: Optional[TableInfo], 
        info2: Optional[TableInfo]
    ) -> Optional[JoinInfo]:
        """
        Find join relationship between two specific tables.
        
        Args:
            table1: First table name
            table2: Second table name
            info1: TableInfo for first table
            info2: TableInfo for second table
            
        Returns:
            JoinInfo if relationship found, None otherwise
        """
        if not info1 or not info2:
            return None
        
        # Strategy 1: Look for foreign keys in table1 pointing to table2
        for fk in info1.foreign_keys:
            if fk['ref_table'] == table2:
                return JoinInfo(
                    from_table=table1,
                    to_table=table2,
                    from_column=fk['column'],
                    to_column=fk['ref_column'],
                    join_type="INNER",
                    reasoning=f"{table1} has FK to {table2}",
                    confidence=0.95
                )
        
        # Strategy 2: Look for foreign keys in table2 pointing to table1
        for fk in info2.foreign_keys:
            if fk['ref_table'] == table1:
                return JoinInfo(
                    from_table=table2,
                    to_table=table1,
                    from_column=fk['column'],
                    to_column=fk['ref_column'],
                    join_type="INNER",
                    reasoning=f"{table2} has FK to {table1}",
                    confidence=0.95
                )
        
        # Strategy 3: Look for common column names (lower confidence)
        cols1 = set(col.name.lower() for col in info1.columns)
        cols2 = set(col.name.lower() for col in info2.columns)
        common_cols = cols1 & cols2
        
        if common_cols:
            # Prefer columns ending in '_id'
            id_cols = [col for col in common_cols if col.endswith('_id')]
            if id_cols:
                col_name = id_cols[0]
                return JoinInfo(
                    from_table=table1,
                    to_table=table2,
                    from_column=col_name,
                    to_column=col_name,
                    join_type="INNER",
                    reasoning=f"Common column: {col_name}",
                    confidence=0.7
                )
        
        return None
    
    # ==================== STEP 6: COLUMN RECOMMENDATION ====================
    
    def _recommend_columns(
        self, 
        question_analysis: QuestionAnalysis, 
        table_details: Dict[str, TableInfo]
    ) -> List[str]:
        """
        Recommend which columns should be included in the SELECT clause.
        
        Args:
            question_analysis: Analysis from Agent #1
            table_details: Schema information
            
        Returns:
            List of recommended column names (format: "table.column")
        """
        recommended = []
        
        # Extract keywords from question
        question_lower = question_analysis.original_question.lower()
        keywords = question_lower.split()
        
        # Common column patterns to look for
        name_patterns = ['name', 'title', 'description']
        id_patterns = ['id']
        value_patterns = ['price', 'cost', 'amount', 'revenue', 'total', 'value', 'quantity']
        date_patterns = ['date', 'time', 'year', 'month']
        
        for table_name, table_info in table_details.items():
            for col in table_info.columns:
                col_lower = col.name.lower()
                
                # Always include primary keys (for identification)
                if col.is_primary_key:
                    recommended.append(f"{table_name}.{col.name}")
                
                # Include columns mentioned in question
                elif any(keyword in col_lower for keyword in keywords):
                    recommended.append(f"{table_name}.{col.name}")
                
                # Include name columns (usually what users want to see)
                elif any(pattern in col_lower for pattern in name_patterns):
                    recommended.append(f"{table_name}.{col.name}")
                
                # Include value columns for aggregation queries
                elif question_analysis.query_type in ['AGGREGATION', 'COUNT'] and \
                     any(pattern in col_lower for pattern in value_patterns):
                    recommended.append(f"{table_name}.{col.name}")
        
        # If no recommendations, default to first few columns of each table
        if not recommended:
            for table_name, table_info in table_details.items():
                for col in table_info.columns[:3]:  # First 3 columns
                    recommended.append(f"{table_name}.{col.name}")
        
        return recommended
    
    # ==================== STEP 7: FILTER VALIDATION ====================
    
    def _validate_filters(
        self, 
        filters: List[Dict[str, Any]], 
        table_details: Dict[str, TableInfo]
    ) -> List[FilterInfo]:
        """
        Validate filters against actual schema and data.
        
        Args:
            filters: Filters from Agent #1
            table_details: Schema information
            
        Returns:
            List of validated FilterInfo objects
        """
        validated = []
        
        for filter_dict in filters:
            column_name = filter_dict.get('column', '').lower()
            operator = filter_dict.get('operator', '=')
            value = filter_dict.get('value')
            
            # Find which table has this column
            found_table = None
            found_column = None
            data_type = None
            
            for table_name, table_info in table_details.items():
                for col in table_info.columns:
                    if col.name.lower() == column_name:
                        found_table = table_name
                        found_column = col.name
                        data_type = col.type
                        break
                if found_table:
                    break
            
            if found_table:
                validated.append(FilterInfo(
                    table=found_table,
                    column=found_column,
                    operator=operator,
                    value=value,
                    data_type=data_type,
                    is_valid=True,
                    validation_message=f"Column found in {found_table}"
                ))
            else:
                validated.append(FilterInfo(
                    table="unknown",
                    column=column_name,
                    operator=operator,
                    value=value,
                    data_type="unknown",
                    is_valid=False,
                    validation_message=f"Column '{column_name}' not found in any selected table"
                ))
        
        return validated
    
    # ==================== CONFIDENCE CALCULATION ====================
    
    def _calculate_confidence(
        self,
        question_analysis: QuestionAnalysis,
        selected_tables: List[str],
        table_details: Dict[str, TableInfo],
        warnings: List[str]
    ) -> float:
        """
        Calculate confidence score for the schema context.
        
        Args:
            question_analysis: Analysis from Agent #1
            selected_tables: Tables selected
            table_details: Schema information
            warnings: List of warnings
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 1.0
        
        # Penalize if no tables found
        if not selected_tables:
            confidence -= 0.5
        
        # Penalize if tables have no data
        for table_name, table_info in table_details.items():
            if table_info.row_count == 0:
                confidence -= 0.1
        
        # Penalize for each warning
        confidence -= len(warnings) * 0.05
        
        # Boost confidence if we have samples
        if table_details and all(t.sample_rows for t in table_details.values()):
            confidence += 0.1
        
        # Ensure confidence is in valid range
        return max(0.0, min(1.0, confidence))
    
    def close(self):
        """Clean up resources"""
        if self.mcp:
            self.mcp.close()


# ==================== TEST FUNCTION ====================

def test_schema_scout():
    """Test the Schema Scout with sample question analysis"""
    from agent.questionDecomposerAgent import QuestionDecomposer
    
    print("=" * 80)
    print("Testing Schema Scout Agent")
    print("=" * 80)
    
    # Initialize agents
    decomposer = QuestionDecomposer()
    scout = SchemaScout()
    
    test_questions = [
        "What are the top 5 most expensive products?",
        "How many customers are there?",
        "Show me all orders from customers in California",
        "Which brand has the most products?",
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'=' * 80}")
        print(f"Test {i}: {question}")
        print('=' * 80)
        
        try:
            # Step 1: Decompose question (Agent #1)
            print("\n🤔 Agent #1: Analyzing question...")
            analysis = decomposer.decompose(question)
            print(f"   Entities: {analysis.entities}")
            print(f"   Query Type: {analysis.query_type}")
            
            # Step 2: Scout schema (Agent #2)
            schema_context = scout.scout(analysis)
            
            # Display results
            print("\n📋 Schema Context Summary:")
            print(f"   Tables: {', '.join(schema_context.selected_tables)}")
            print(f"   Columns: {len(schema_context.recommended_columns)}")
            print(f"   Joins: {len(schema_context.required_joins)}")
            print(f"   Confidence: {schema_context.confidence:.2f}")
            
            if schema_context.warnings:
                print(f"\n⚠️  Warnings:")
                for warning in schema_context.warnings:
                    print(f"   - {warning}")
            
            # Show sample data
            print("\n🎲 Sample Data:")
            for table_name, table_info in schema_context.table_details.items():
                if table_info.sample_rows:
                    print(f"\n   {table_name} (showing 1 row):")
                    print(f"   {json.dumps(table_info.sample_rows[0], indent=6)}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    scout.close()
    print("\n" + "=" * 80)
    print("Schema Scout test complete!")
    print("=" * 80)


if __name__ == "__main__":
    test_schema_scout()
