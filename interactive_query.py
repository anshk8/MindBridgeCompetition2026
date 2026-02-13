"""
Interactive SQL Query Tool

Simple tool to paste and execute SQL queries against the database.
"""

import duckdb


def print_results(results, headers):
    """Pretty print query results"""
    if not results:
        print("  (No results)")
        return
    
    # Print headers
    header_line = " | ".join(str(h) for h in headers)
    print(f"  {header_line}")
    print("  " + "-" * len(header_line))
    
    # Print rows (limit to 20 for readability)
    for i, row in enumerate(results[:20]):
        row_line = " | ".join(str(val) for val in row)
        print(f"  {row_line}")
    
    if len(results) > 20:
        print(f"  ... ({len(results) - 20} more rows)")
    
    print(f"\n  Total rows: {len(results)}")


def main():
    print("\n" + "="*80)
    print("🔍 SQL QUERY EXECUTOR")
    print("="*80)
    print("\nPaste your SQL queries and see results.")
    print("Type 'quit' or 'exit' to stop.")
    print("="*80 + "\n")
    
    # Connect to database
    conn = duckdb.connect('bike_store.db')
    
    try:
        while True:
            print("\n" + "-"*80)
            sql = input("\nSQL> ").strip()
            
            if sql.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break
            
            if not sql:
                continue
            
            try:
                result = conn.execute(sql)
                rows = result.fetchall()
                headers = [desc[0] for desc in result.description]
                
                print("\n📊 Results:")
                print_results(rows, headers)
            
            except Exception as e:
                print(f"❌ Error: {e}")
    
    finally:
        conn.close()


if __name__ == "__main__":
    main()
