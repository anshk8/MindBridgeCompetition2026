"""
SQL Architect Agent - Phase 3: Query Generation (PRODUCTION READY)


This agent is responsible for:
1. Routing query types to appropriate generation strategies
2. Building SQL clauses (SELECT, FROM, JOIN, WHERE, ORDER BY, LIMIT)
3. Using Chain-of-Thought reasoning for complex queries
4. Validating SQL syntax before returning
5. Generating accurate, executable SQL queries


The output provides a complete SQL query ready for execution.
"""


import os
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field


# LLM imports
try:
    import ollama
except ImportError:
    print("⚠️  Warning: ollama not installed. LLM generation will not work.")
    ollama = None


# Imports - handle both running as script and as module
try:
    from agents.questionDecomposerAgent import QuestionAnalysis
    from agents.schemaExpert import SchemaContext
except ImportError:
    # Running as script from agent directory
    from questionDecomposerAgent import QuestionAnalysis
    from schemaExpert import SchemaContext



# ==================== OUTPUT DATA STRUCTURES ====================


@dataclass
class SQLQuery:
    """Generated SQL query with metadata"""
    sql: str
    confidence: float
    reasoning: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    strategy: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "sql": self.sql,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "warnings": self.warnings,
            "strategy": self.strategy
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)



# ==================== MAIN AGENT CLASS ====================


class SQLArchitect:
    """
    Agent #3: SQL Architect (PRODUCTION READY)
    
    Generates SQL queries from natural language understanding
    and database schema context.
    
    Responsibilities:
    1. Route query type to appropriate generation strategy
    2. Build SELECT, FROM, JOIN, WHERE, GROUP BY, ORDER BY, LIMIT clauses
    3. Use Chain-of-Thought reasoning for complex queries
    4. Validate SQL syntax before returning
    5. Generate executable SQL queries
    
    FIXES APPLIED:
    - ✅ JOIN generation for multi-table queries
    - ✅ Table prefixes for columns (prevents ambiguity)
    - ✅ SQL injection protection (string escaping)
    - ✅ Multi-table JOIN template
    - ✅ Simple aggregation template
    - ✅ Improved Chain-of-Thought prompting
    """
    
    def __init__(self, model: str = None):
        """
        Initialize SQL Architect.
        
        Args:
            model: Ollama model name (default: from env or 'qwen2.5-coder:14b')
        """
        # Use qwen2.5-coder:14b for Agent #3 (excellent at SQL generation)
        self.model = model or os.getenv('AGENT3_MODEL', os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:14b'))
        self.client = ollama if ollama else None
        print(f"🤖 Agent #3 using model: {self.model}")
        
        # SQL templates for common patterns
        self.templates = {
            "simple_select": "SELECT {columns} FROM {table}",
            "simple_count": "SELECT COUNT(*) FROM {table}",
            "top_n": "SELECT {columns} FROM {table} ORDER BY {order_column} {direction} LIMIT {limit}",
            "with_filter": "SELECT {columns} FROM {table} WHERE {conditions}",
            "with_join": "SELECT {columns} FROM {table1} JOIN {table2} ON {join_condition}",
            "aggregation": "SELECT {group_columns}, {agg_function}({agg_column}) FROM {table} GROUP BY {group_columns}"
        }
    
    def generate(
        self, 
        question_analysis: QuestionAnalysis,
        schema_context: SchemaContext
    ) -> SQLQuery:
        """
        MAIN METHOD: Generate SQL query.
        
        Args:
            question_analysis: Output from Agent #1
            schema_context: Output from Agent #2
            
        Returns:
            SQLQuery object with generated SQL
        """
        
        print("\n" + "=" * 80)
        print("🏗️  AGENT #3: SQL ARCHITECT - Starting SQL generation")
        print("=" * 80)
        
        reasoning = []
        warnings = []
        
        # Step 1: Determine query strategy via Agent 1 Output
        print("\n[1/5] 🚦 Routing query type...")
        strategy = self._route_query_type(question_analysis)
        print(f"   → Strategy: {strategy}")
        reasoning.append(f"Using strategy: {strategy}")
        
        # Step 2: Try template-based generation first (fast & reliable)
        print("\n[2/5] 📋 Attempting template-based generation...")
        template_sql = self._try_template_generation(
            strategy, question_analysis, schema_context
        )
        
        if template_sql:
            print(f"   → Template match successful!")
            print(f"   → SQL: {template_sql[:80]}...")
            
            # Validate template SQL
            is_valid, validation_errors = self._validate_sql_syntax(template_sql)
            if not is_valid:
                warnings.extend(validation_errors)
            
            return SQLQuery(
                sql=template_sql,
                confidence=0.90 if is_valid else 0.70,
                reasoning=reasoning + ["Generated from template"],
                warnings=warnings,
                strategy=strategy
            )
        
        print("   → No template match, using LLM...")
        
        # Step 3: Use Chain-of-Thought LLM generation (for complex queries)
        if self.client is None:
            error_msg = "LLM not available and no template matched"
            print(f"   ❌ {error_msg}")
            warnings.append(error_msg)
            return SQLQuery(
                sql="-- Unable to generate SQL",
                confidence=0.0,
                reasoning=reasoning,
                warnings=warnings,
                strategy=strategy
            )
        
        print("\n[3/5] 🧠 Using Chain-of-Thought LLM generation...")
        cot_sql = self._generate_with_chain_of_thought(
            question_analysis, schema_context
        )
        print(f"   → LLM generated SQL")
        reasoning.append("Generated with Chain-of-Thought LLM")
        
        # Step 4: Validate SQL syntax
        print("\n[4/5] ✅ Validating SQL syntax...")
        is_valid, validation_errors = self._validate_sql_syntax(cot_sql)
        
        if not is_valid:
            print(f"   ⚠️  Validation warnings: {validation_errors}")
            warnings.extend(validation_errors)
        else:
            print(f"   → SQL is valid")
        
        # Step 5: Calculate confidence
        print("\n[5/5] 🎲 Calculating confidence...")
        confidence = self._calculate_confidence(
            question_analysis, schema_context, is_valid, warnings
        )
        print(f"   → Confidence: {confidence:.2f}")
        
        result = SQLQuery(
            sql=cot_sql,
            confidence=confidence,
            reasoning=reasoning,
            warnings=warnings,
            strategy=strategy
        )
        
        # Print final output
        print(f"\nOUTPUT:")
        print(f"  ├─ Strategy: {result.strategy}")
        print(f"  ├─ Confidence: {result.confidence:.2f}")
        print(f"  ├─ Warnings: {len(result.warnings)}")
        print(f"  └─ Generated SQL:")
        print(f"\n{'─' * 80}")
        for line in result.sql.split('\n'):
            print(f"      {line}")
        print(f"{'─' * 80}\n")
        
        print(f"✅ SQL Architect complete!")
        print("=" * 80 + "\n")
        
        return result
    
    # ==================== QUERY TYPE ROUTING ====================
    
    def _route_query_type(self, question_analysis: QuestionAnalysis) -> str:
        """
        Determine which SQL generation strategy to use.
        
        Returns:
            Strategy name
        """
        query_type = question_analysis.query_type
        
        # Simple COUNT query - check for actual COUNT aggregation
        if question_analysis.aggregations:
            has_count = any(agg.get('function') == 'COUNT' for agg in question_analysis.aggregations)
            # Simple COUNT with single table, no filters
            if has_count and not question_analysis.filters and len(question_analysis.entities) == 1:
                return "simple_count"
        
        # Aggregation queries (SUM, AVG, MAX, MIN, COUNT with filters/joins)
        if question_analysis.aggregations:
            if len(question_analysis.entities) > 1:
                return "aggregation_with_join"
            else:
                return "simple_aggregation"
        
        # Multi-table JOIN
        if len(question_analysis.entities) > 1:
            return "multi_table_join"
        
        # TOP N query (ORDER BY + LIMIT)
        if question_analysis.ordering and question_analysis.limit:
            return "top_n_query"
        
        # Simple SELECT with filter
        if question_analysis.filters:
            return "select_with_filter"
        
        # Default: simple SELECT
        return "simple_select"
    
    # ==================== TEMPLATE-BASED GENERATION ====================
    
    def _try_template_generation(
        self,
        strategy: str,
        question_analysis: QuestionAnalysis,
        schema_context: SchemaContext
    ) -> Optional[str]:
        """
        Try to generate SQL using templates (fast path).
        
        Returns SQL if template matches, None otherwise.
        """
        
        if strategy == "simple_count":
            return self._generate_simple_count(schema_context)
        
        elif strategy == "top_n_query":
            return self._generate_top_n(question_analysis, schema_context)
        
        elif strategy == "simple_select":
            return self._generate_simple_select(schema_context)
        
        elif strategy == "select_with_filter":
            return self._generate_select_with_filter(question_analysis, schema_context)
        
        elif strategy == "simple_aggregation":
            return self._generate_simple_aggregation(question_analysis, schema_context)
        
        elif strategy == "multi_table_join":
            return self._generate_multi_table_join(question_analysis, schema_context)
        
        # For complex queries, return None to use LLM
        return None
    
    def _generate_simple_count(self, schema_context: SchemaContext) -> str:
        """Generate COUNT(*) query"""
        table = schema_context.selected_tables[0]
        return f"SELECT COUNT(*) FROM {table}"
    
    def _generate_top_n(
        self,
        question_analysis: QuestionAnalysis,
        schema_context: SchemaContext
    ) -> str:
        """Generate TOP N query (e.g., top 5 most expensive products)"""
        
        # Get table
        table = schema_context.selected_tables[0]
        
        # Get columns
        columns = self._select_columns(question_analysis, schema_context)
        columns_str = self._format_columns_for_select(columns, schema_context)
        
        # Get ordering
        ordering = question_analysis.ordering
        order_column = self._infer_order_column(ordering, schema_context)
        direction = ordering.get('direction', 'DESC')
        
        # Get limit
        limit = question_analysis.limit
        
        # Build JOINs (if any)
        joins = self._build_joins(schema_context)
        
        sql = f"""SELECT {columns_str}
FROM {table}"""
        
        if joins:
            sql += f"\n{joins}"
        
        sql += f"""
ORDER BY {order_column} {direction}
LIMIT {limit}"""
        
        return sql
    
    def _generate_simple_select(self, schema_context: SchemaContext) -> str:
        """Generate simple SELECT query"""
        table = schema_context.selected_tables[0]
        columns = schema_context.recommended_columns
        columns_str = self._format_columns_for_select(columns, schema_context)
        
        return f"SELECT {columns_str} FROM {table}"
    
    def _generate_select_with_filter(
        self,
        question_analysis: QuestionAnalysis,
        schema_context: SchemaContext
    ) -> Optional[str]:
        """Generate SELECT with WHERE clause"""
        
        table = schema_context.selected_tables[0]
        columns = self._select_columns(question_analysis, schema_context)
        columns_str = self._format_columns_for_select(columns, schema_context)
        
        # Build JOINs (if any)
        joins = self._build_joins(schema_context)
        
        where_clause = self._build_where_clause(question_analysis, schema_context)
        
        if not where_clause:
            return None  # Fall back to LLM
        
        sql = f"""SELECT {columns_str}
FROM {table}"""
        
        if joins:
            sql += f"\n{joins}"
        
        sql += f"\n{where_clause}"
        
        return sql
    
    def _generate_simple_aggregation(
        self,
        question_analysis: QuestionAnalysis,
        schema_context: SchemaContext
    ) -> Optional[str]:
        """
        Generate simple aggregation query.
        
        Examples:
        - "What is the average product price?"
        - "What is the total revenue?"
        """
        
        if not question_analysis.aggregations:
            return None
        
        table = schema_context.selected_tables[0]
        
        # Build aggregation expression
        agg = question_analysis.aggregations[0]  # Take first
        func = agg.get('function', 'COUNT')
        col = agg.get('column', '*')
        
        # If column is specified, find full name
        if col != '*':
            for table_name, table_info in schema_context.table_details.items():
                for column in table_info.columns:
                    if col.lower() in column.name.lower():
                        col = column.name
                        break
        
        sql = f"SELECT {func}({col}) FROM {table}"
        
        return sql
    
    def _generate_multi_table_join(
        self,
        question_analysis: QuestionAnalysis,
        schema_context: SchemaContext
    ) -> Optional[str]:
        """Generate multi-table JOIN query"""
        
        # Only handle simple 2-3 table joins in template
        if len(schema_context.selected_tables) > 3:
            return None  # Too complex, use LLM
        
        if not schema_context.required_joins:
            return None  # No join info
        
        # Get tables
        primary_table = schema_context.selected_tables[0]
        
        # Get columns
        columns = self._select_columns(question_analysis, schema_context)
        columns_str = self._format_columns_for_select(columns, schema_context)
        
        # Get joins
        joins = self._build_joins(schema_context)
        
        # Get WHERE (if any)
        where_clause = self._build_where_clause(question_analysis, schema_context)
        
        # Get ORDER BY (if any)
        order_clause = self._build_order_limit(question_analysis, schema_context)
        
        sql = f"""SELECT {columns_str}
FROM {primary_table}
{joins}"""
        
        if where_clause:
            sql += f"\n{where_clause}"
        
        if order_clause:
            sql += f"\n{order_clause}"
        
        return sql.strip()
    
    # ==================== SQL CLAUSE BUILDERS ====================
    
    def _select_columns(
        self, 
        question_analysis: QuestionAnalysis,
        schema_context: SchemaContext
    ) -> List[str]:
        """
        Decide which columns to include in SELECT clause.
        """
        
        # Special case: COUNT queries
        if "COUNT" in question_analysis.query_type:
            return ["COUNT(*)"]
        
        # Special case: Aggregation
        if question_analysis.aggregations:
            agg_columns = []
            for agg in question_analysis.aggregations:
                func = agg.get('function', 'COUNT')
                col = agg.get('column', '*')
                agg_columns.append(f"{func}({col})")
            return agg_columns
        
        # Use Agent #2's recommendations
        return schema_context.recommended_columns if schema_context.recommended_columns else ["*"]
    
    def _format_columns_for_select(
        self,
        columns: List[str],
        schema_context: SchemaContext
    ) -> str:
        """
        Format columns for SELECT clause.
        
        Rules:
        - Single table: remove table prefix (cleaner)
        - Multiple tables: keep table prefix (avoid ambiguity)
        """
        
        # Check if we have multiple tables
        num_tables = len(schema_context.selected_tables)
        
        if num_tables == 1:
            # Single table - remove prefix for cleaner SQL
            formatted = [c.split('.')[-1] if '.' in c else c for c in columns]
        else:
            # Multiple tables - keep prefix to avoid ambiguity
            formatted = columns
        
        return ", ".join(formatted)
    
    def _build_joins(self, schema_context: SchemaContext) -> str:
        """
        Build JOIN clauses from schema context.
        
        This method validates table and column identifiers to avoid
        accidentally constructing unsafe SQL if the schema context is
        compromised or malformed.
        
        Example:
            INNER JOIN brands ON products.brand_id = brands.brand_id
        """
        
        if not schema_context.required_joins:
            return ""
        
        # Allowed join types (normalized to upper case)
        allowed_join_types = {
            "INNER",
            "LEFT",
            "LEFT OUTER",
            "RIGHT",
            "RIGHT OUTER",
            "FULL",
            "FULL OUTER",
            "CROSS",
        }
        
        def _is_valid_identifier(name: str) -> bool:
            """
            Validate that a table/column name is a simple SQL identifier:
            starts with a letter or underscore, followed by letters,
            digits, or underscores.
            """
            return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name or ""))
        
        joins = []
        
        for join_info in schema_context.required_joins:
            join_type_normalized = (join_info.join_type or "").upper().strip()
            
            if join_type_normalized not in allowed_join_types:
                raise ValueError(f"Invalid join type in schema context: {join_info.join_type!r}")
            
            from_table = join_info.from_table
            to_table = join_info.to_table
            from_column = join_info.from_column
            to_column = join_info.to_column
            
            if not _is_valid_identifier(from_table):
                raise ValueError(f"Invalid table name in schema context: {from_table!r}")
            if not _is_valid_identifier(to_table):
                raise ValueError(f"Invalid table name in schema context: {to_table!r}")
            if not _is_valid_identifier(from_column):
                raise ValueError(f"Invalid column name in schema context: {from_column!r}")
            if not _is_valid_identifier(to_column):
                raise ValueError(f"Invalid column name in schema context: {to_column!r}")
            
            join_clause = (
                f"{join_type_normalized} JOIN {to_table} "
                f"ON {from_table}.{from_column} = {to_table}.{to_column}"
            )
            joins.append(join_clause)
        
        return "\n".join(joins)
    
    def _build_where_clause(
        self,
        question_analysis: QuestionAnalysis,
        schema_context: SchemaContext
    ) -> str:
        """
        Build WHERE clause from filters.
        
        Handles:
        - Simple comparisons (>, <, =)
        - String matching (LIKE, IN)
        - Date filtering
        - NULL handling
        - SQL injection prevention
        """
        
        validated_filters = schema_context.validated_filters
        
        if not validated_filters:
            return ""
        
        conditions = []
        
        for filter_info in validated_filters:
            if not filter_info.is_valid:
                continue
            
            table = filter_info.table
            column = filter_info.column
            operator = filter_info.operator
            value = filter_info.value
            data_type = filter_info.data_type
            
            # ✅ ALWAYS include table prefix for clarity
            full_column = f"{table}.{column}"
            
            # Format value based on data type
            if "VARCHAR" in data_type or "TEXT" in data_type:
                escaped_value = self._escape_sql_string(value)
                if operator == "contains":
                    condition = f"{full_column} LIKE '%{escaped_value}%'"
                else:
                    condition = f"{full_column} {operator} '{escaped_value}'"
            elif "INTEGER" in data_type or "DECIMAL" in data_type:
                condition = f"{full_column} {operator} {value}"
            elif "DATE" in data_type:
                condition = f"{full_column} {operator} '{value}'"
            else:
                condition = f"{full_column} {operator} {value}"
            
            conditions.append(condition)
        
        if conditions:
            return "WHERE " + " AND ".join(conditions)
        
        return ""
    
    def _build_order_limit(
        self,
        question_analysis: QuestionAnalysis,
        schema_context: SchemaContext
    ) -> str:
        """Build ORDER BY and LIMIT clauses"""
        
        clauses = []
        
        # ORDER BY
        if question_analysis.ordering:
            ordering = question_analysis.ordering
            order_column = self._infer_order_column(ordering, schema_context)
            direction = ordering.get('direction', 'ASC')
            
            if order_column != "inferred":
                clauses.append(f"ORDER BY {order_column} {direction}")
        
        # LIMIT
        if question_analysis.limit:
            clauses.append(f"LIMIT {question_analysis.limit}")
        
        return "\n".join(clauses)
    
    def _infer_order_column(
        self,
        ordering: Dict,
        schema_context: SchemaContext
    ) -> str:
        """Infer which column to use for ORDER BY"""
        
        column = ordering.get('column', 'inferred')
        
        if column != 'inferred':
            return column
        
        # Try to infer from column names
        for table_name, table_info in schema_context.table_details.items():
            for col in table_info.columns:
                col_lower = col.name.lower()
                if 'price' in col_lower or 'amount' in col_lower or 'cost' in col_lower:
                    return col.name
                if 'date' in col_lower or 'time' in col_lower:
                    return col.name
        
        # Default: use first non-ID column
        for table_name, table_info in schema_context.table_details.items():
            for col in table_info.columns:
                if not col.is_primary_key:
                    return col.name
        
        return "*"
    
    def _escape_sql_string(self, value: str) -> str:
        """
        Escape single quotes in SQL strings to prevent SQL injection.
        
        SQL standard: ' becomes ''
        """
        if isinstance(value, str):
            return value.replace("'", "''")
        return str(value)
    
    # ==================== CHAIN-OF-THOUGHT GENERATION ====================
    
    def _generate_with_chain_of_thought(
        self,
        question_analysis: QuestionAnalysis,
        schema_context: SchemaContext
    ) -> str:
        """Use LLM with Chain-of-Thought prompting"""
        
        prompt = self._build_cot_prompt(question_analysis, schema_context)
        
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert SQL query generator. Generate only the SQL query, no explanations."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            sql = self._extract_sql_from_response(response['message']['content'])
            return sql
            
        except Exception as e:
            print(f"   ❌ LLM error: {e}")
            # Fallback to basic template
            return self._generate_simple_select(schema_context)
    
    def _build_cot_prompt(
        self, 
        question_analysis: QuestionAnalysis,
        schema_context: SchemaContext
    ) -> str:
        """
        Build improved Chain-of-Thought prompt for LLM.
        
        This version forces explicit step-by-step reasoning.
        """
        
        # Get sample data
        sample_data = ""
        for table_name, table_info in schema_context.table_details.items():
            if table_info.sample_rows and len(table_info.sample_rows) > 0:
                sample_data += f"\n{table_name} sample:\n"
                sample_data += json.dumps(table_info.sample_rows[0], indent=2, default=str)
        
        # Get column info
        column_info = ""
        for table_name, table_info in schema_context.table_details.items():
            column_info += f"\n{table_name} columns:\n"
            for col in table_info.columns:
                column_info += f"  - {col.name} ({col.type})"
                if col.is_primary_key:
                    column_info += " [PRIMARY KEY]"
                if col.is_foreign_key:
                    column_info += " [FOREIGN KEY]"
                column_info += "\n"
        
        # Get join info
        join_info = ""
        if schema_context.required_joins:
            join_info = "\nREQUIRED JOINS:\n"
            for join in schema_context.required_joins:
                join_info += f"- {join.from_table}.{join.from_column} = {join.to_table}.{join.to_column} ({join.join_type})\n"
        
        prompt = f"""You are an expert SQL generator. Answer this question by thinking step-by-step.

QUESTION: "{question_analysis.original_question}"

DATABASE SCHEMA:
{column_info}

SAMPLE DATA (showing actual values):
{sample_data}

{join_info}

RECOMMENDED COLUMNS: {', '.join(schema_context.recommended_columns[:5])}

INSTRUCTIONS:
1. First, write your reasoning for EACH step below
2. Then, write the final SQL query

STEP 1 - Which tables?
Available: {', '.join(schema_context.selected_tables)}
YOUR REASONING: [explain which tables and why]

STEP 2 - Which columns to SELECT?
YOUR REASONING: [explain which columns and why]

STEP 3 - Any JOINs needed?
{f"Yes, found {len(schema_context.required_joins)} joins" if schema_context.required_joins else "No joins needed"}
YOUR REASONING: [explain joins if any]

STEP 4 - Any filters (WHERE)?
Detected filters: {question_analysis.filters if question_analysis.filters else "None"}
YOUR REASONING: [explain WHERE clause]

STEP 5 - Any sorting (ORDER BY)?
Detected ordering: {question_analysis.ordering if question_analysis.ordering else "None"}
YOUR REASONING: [explain ORDER BY]

STEP 6 - Any limit (LIMIT)?
Detected limit: {question_analysis.limit if question_analysis.limit else "None"}
YOUR REASONING: [explain LIMIT]

Now write the FINAL SQL QUERY below:

```sql
[YOUR SQL HERE]
```"""

        return prompt
    
    def _extract_sql_from_response(self, response: str) -> str:
        """Extract SQL query from LLM response"""
        
        # Remove markdown code blocks
        response = re.sub(r'```sql\n?', '', response)
        response = re.sub(r'```\n?', '', response)
        
        # Remove extra whitespace
        response = response.strip()
        
        # Ensure it ends with semicolon
        if not response.endswith(';'):
            response += ';'
        
        return response
    
    # ==================== VALIDATION ====================
    
    def _validate_sql_syntax(self, sql: str) -> Tuple[bool, List[str]]:
        """
        Validate SQL syntax.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        if not sql or sql == "-- Unable to generate SQL":
            return False, ["No SQL generated"]
        
        sql_upper = sql.upper()
        
        # Basic syntax checks
        if not sql_upper.startswith('SELECT'):
            errors.append("SQL must start with SELECT")
        
        if 'FROM' not in sql_upper:
            errors.append("SQL must have FROM clause")
        
        # Check for balanced parentheses
        if sql.count('(') != sql.count(')'):
            errors.append("Unbalanced parentheses")
        
        # Check for common mistakes
        select_part = sql.split('FROM')[0] if 'FROM' in sql_upper else sql
        if '*' in select_part and ',' in select_part and 'COUNT' not in sql_upper:
            errors.append("Cannot mix * with specific columns")
        
        return len(errors) == 0, errors
    
    def _calculate_confidence(
        self,
        question_analysis: QuestionAnalysis,
        schema_context: SchemaContext,
        is_valid: bool,
        warnings: List[str]
    ) -> float:
        """Calculate confidence score"""
        
        confidence = 0.75  # Base confidence
        
        # Boost if schema context has high confidence
        confidence += schema_context.confidence * 0.10
        
        # Boost if question analysis has high confidence
        confidence += question_analysis.confidence * 0.05
        
        # Penalize if SQL validation failed
        if not is_valid:
            confidence -= 0.25
        
        # Penalize for warnings
        confidence -= len(warnings) * 0.05
        
        # Boost if simple query type
        if question_analysis.query_type in ['SELECT', 'COUNT']:
            confidence += 0.05
        
        # Ensure range [0, 1]
        return max(0.0, min(1.0, confidence))
    
    def close(self):
        """Clean up resources"""
        pass