"""
MCP Server for Database Operations

This server acts as a database expert, providing tools for:
- Schema information and exploration
- Sample data retrieval
- Query execution and validation
- Statistical analysis
"""

import duckdb
from typing import List, Any, Optional
from dataclasses import dataclass


@dataclass
class MCPToolResult:
    """Result from an MCP tool execution"""
    success: bool
    data: Any
    error: Optional[str] = None
    
    def to_dict(self):
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error
        }


class DatabaseMCPServer:
    """
    MCP Server that provides database expertise through various tools.
    
    This server maintains a connection to the DuckDB database and provides
    tools for agents to interact with the database safely and efficiently.
    """
    
    def __init__(self, db_path: str = 'bike_store.db'):
        """
        Initialize the MCP server with database connection.
        
        Args:
            db_path: Path to the DuckDB database file
        """
        self.db_path = db_path
        self.conn = None
        self._connect()
    
    def _connect(self):
        """Establish connection to the database"""
        try:
            self.conn = duckdb.connect(database=self.db_path, read_only=True)
        except Exception as e:
            print(f"Error connecting to database: {e}")
            raise
    
    def _execute_query(self, query: str) -> List[tuple]:
        """
        Execute a query and return results.
        
        Args:
            query: SQL query to execute
            
        Returns:
            List of tuples representing query results
        """
        try:
            if self.conn is None:
                self._connect()
            return self.conn.execute(query).fetchall()
        except Exception as e:
            raise Exception(f"Query execution failed: {str(e)}")
    
    def _validate_limit(self, limit: Optional[int], max_limit: int = 10000) -> tuple[bool, Optional[str]]:
        """
        Validate limit parameter.
        
        Args:
            limit: The limit value to validate
            max_limit: Maximum allowed limit (default: 10000)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if limit is None:
            return True, None
        
        if not isinstance(limit, int):
            return False, f"Limit must be an integer, got {type(limit).__name__}"
        
        if limit <= 0:
            return False, f"Limit must be positive, got {limit}"
        
        if limit > max_limit:
            return False, f"Limit exceeds maximum allowed value of {max_limit}, got {limit}"
        
        return True, None
    
    # ==================== SCHEMA TOOLS ====================
    
    def get_full_schema(self) -> MCPToolResult:
        """
        Get complete schema information for all tables.
        
        Returns:
            MCPToolResult with schema information for all tables
        """
        try:
            tables = self._execute_query("SHOW TABLES")
            schema_info = {}
            
            for (table_name,) in tables:
                columns = self._execute_query(f"DESCRIBE {table_name}")
                schema_info[table_name] = [
                    {
                        "name": col[0],
                        "type": col[1],
                        "null": col[2] if len(col) > 2 else None,
                        "key": col[3] if len(col) > 3 else None
                    }
                    for col in columns
                ]
            
            return MCPToolResult(success=True, data=schema_info)
        except Exception as e:
            return MCPToolResult(success=False, data=None, error=str(e))
    
    def list_tables(self) -> MCPToolResult:
        """
        Get a list of all tables in the database.
        
        Returns:
            MCPToolResult with list of table names
        """
        try:
            tables = self._execute_query("SHOW TABLES")
            table_names = [table[0] for table in tables]
            return MCPToolResult(success=True, data=table_names)
        except Exception as e:
            return MCPToolResult(success=False, data=None, error=str(e))
    
    def get_table_info(self, table_name: str) -> MCPToolResult:
        """
        Get detailed information about a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            MCPToolResult with table information including columns and types
        """
        try:
            columns = self._execute_query(f"DESCRIBE {table_name}")
            column_info = [
                {
                    "name": col[0],
                    "type": col[1],
                    "null": col[2] if len(col) > 2 else None
                }
                for col in columns
            ]
            return MCPToolResult(success=True, data={
                "table_name": table_name,
                "columns": column_info,
                "column_count": len(column_info)
            })
        except Exception as e:
            return MCPToolResult(success=False, data=None, error=str(e))
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> MCPToolResult:
        """
        Get sample rows from a table.
        
        Args:
            table_name: Name of the table
            limit: Number of rows to return (default: 5)
            
        Returns:
            MCPToolResult with sample data
        """
        # Validate limit
        is_valid, error_msg = self._validate_limit(limit, max_limit=1000)
        if not is_valid:
            return MCPToolResult(success=False, data=None, error=error_msg)
        
        # Ensure limit is integer (defensive programming)
        limit = int(limit)
        
        try:
            # Get column names
            columns = self._execute_query(f"DESCRIBE {table_name}")
            column_names = [col[0] for col in columns]
            
            # Get sample data
            rows = self._execute_query(f"SELECT * FROM {table_name} LIMIT {limit}")
            
            # Convert to list of dicts
            sample_data = [
                dict(zip(column_names, row))
                for row in rows
            ]
            
            return MCPToolResult(success=True, data={
                "table_name": table_name,
                "columns": column_names,
                "rows": sample_data,
                "row_count": len(sample_data)
            })
        except Exception as e:
            return MCPToolResult(success=False, data=None, error=str(e))
    
    # ==================== QUERY TOOLS ====================
    
    def execute_query(self, query: str, limit: Optional[int] = None) -> MCPToolResult:
        """
        Execute a SQL query and return results.
        
        Args:
            query: SQL query to execute
            limit: Optional limit on number of results
            
        Returns:
            MCPToolResult with query results
        """
        # Validate limit
        is_valid, error_msg = self._validate_limit(limit)
        if not is_valid:
            return MCPToolResult(success=False, data=None, error=error_msg)
        
        try:
            # Add limit if specified and not already in query
            if limit and 'LIMIT' not in query.upper():
                # Ensure limit is integer (defensive programming against SQL injection)
                limit = int(limit)
                query = f"{query.rstrip(';')} LIMIT {limit}"
            
            result = self._execute_query(query)
            
            # Get column names from the query
            try:
                cols = self.conn.execute(f"DESCRIBE ({query})").fetchall()
                column_names = [col[0] for col in cols]
            except Exception:
                column_names = [f"col_{i}" for i in range(len(result[0]) if result else 0)]
            
            # Convert to list of dicts
            results = [
                dict(zip(column_names, row))
                for row in result
            ]
            
            return MCPToolResult(success=True, data={
                "query": query,
                "columns": column_names,
                "rows": results,
                "row_count": len(results)
            })
        except Exception as e:
            return MCPToolResult(success=False, data=None, error=str(e))
    
    def validate_query_syntax(self, query: str) -> MCPToolResult:
        """
        Validate SQL query syntax without executing it.
        
        Args:
            query: SQL query to validate
            
        Returns:
            MCPToolResult indicating if query is valid
        """
        try:
            # Use EXPLAIN to validate syntax without executing
            self._execute_query(f"EXPLAIN {query}")
            return MCPToolResult(success=True, data={
                "valid": True,
                "query": query,
                "message": "Query syntax is valid"
            })
        except Exception as e:
            return MCPToolResult(success=False, data={
                "valid": False,
                "query": query,
                "error": str(e)
            }, error=str(e))
    
    def explain_query(self, query: str) -> MCPToolResult:
        """
        Get the execution plan for a query.
        
        Args:
            query: SQL query to explain
            
        Returns:
            MCPToolResult with query execution plan
        """
        try:
            plan = self._execute_query(f"EXPLAIN {query}")
            plan_text = "\n".join([row[0] for row in plan])
            return MCPToolResult(success=True, data={
                "query": query,
                "execution_plan": plan_text
            })
        except Exception as e:
            return MCPToolResult(success=False, data=None, error=str(e))
    
    # ==================== ANALYSIS TOOLS ====================
    
    def get_table_statistics(self, table_name: str) -> MCPToolResult:
        """
        Get statistics for a table (row count, column count, etc.).
        
        Args:
            table_name: Name of the table
            
        Returns:
            MCPToolResult with table statistics
        """
        try:
            # Get row count
            row_count = self._execute_query(f"SELECT COUNT(*) FROM {table_name}")[0][0]
            
            # Get column info
            columns = self._execute_query(f"DESCRIBE {table_name}")
            column_count = len(columns)
            
            # Get column names and types
            column_info = {col[0]: col[1] for col in columns}
            
            return MCPToolResult(success=True, data={
                "table_name": table_name,
                "row_count": row_count,
                "column_count": column_count,
                "columns": column_info
            })
        except Exception as e:
            return MCPToolResult(success=False, data=None, error=str(e))
    
    def get_column_values(self, table_name: str, column_name: str, distinct: bool = True, limit: int = 20) -> MCPToolResult:
        """
        Get unique values from a specific column.
        
        Args:
            table_name: Name of the table
            column_name: Name of the column
            distinct: Whether to return only distinct values
            limit: Maximum number of values to return
            
        Returns:
            MCPToolResult with column values
        """
        # Validate limit
        is_valid, error_msg = self._validate_limit(limit, max_limit=1000)
        if not is_valid:
            return MCPToolResult(success=False, data=None, error=error_msg)
        
        # Ensure limit is integer (defensive programming)
        limit = int(limit)
        
        try:
            distinct_clause = "DISTINCT" if distinct else ""
            query = f"SELECT {distinct_clause} {column_name} FROM {table_name} LIMIT {limit}"
            results = self._execute_query(query)
            values = [row[0] for row in results]
            
            return MCPToolResult(success=True, data={
                "table_name": table_name,
                "column_name": column_name,
                "values": values,
                "value_count": len(values),
                "distinct": distinct
            })
        except Exception as e:
            return MCPToolResult(success=False, data=None, error=str(e))
    
    def find_relationships(self) -> MCPToolResult:
        """
        Attempt to identify relationships between tables based on column names.
        
        Returns:
            MCPToolResult with potential relationships
        """
        try:
            schema = self.get_full_schema()
            if not schema.success:
                return schema
            
            relationships = []
            tables = schema.data
            
            # Look for common column names that might indicate relationships
            for table1, cols1 in tables.items():
                col_names1 = [col['name'].lower() for col in cols1]
                
                for table2, cols2 in tables.items():
                    if table1 >= table2:  # Avoid duplicates
                        continue
                    
                    col_names2 = [col['name'].lower() for col in cols2]
                    
                    # Find common columns (potential foreign keys)
                    common = set(col_names1) & set(col_names2)
                    
                    for col in common:
                        relationships.append({
                            "table1": table1,
                            "table2": table2,
                            "column": col,
                            "type": "potential_relationship"
                        })
            
            return MCPToolResult(success=True, data={
                "relationships": relationships,
                "relationship_count": len(relationships)
            })
        except Exception as e:
            return MCPToolResult(success=False, data=None, error=str(e))
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Convenience functions for easy access
def create_mcp_server(db_path: str = 'bike_store.db') -> DatabaseMCPServer:
    """
    Create and return an MCP server instance.
    
    Args:
        db_path: Path to the database
        
    Returns:
        DatabaseMCPServer instance
    """
    return DatabaseMCPServer(db_path=db_path)

