"""
Interactive SQL Query Tool

Lets you test the SQL Agent interactively and see actual results from the database.
"""

import duckdb
from agents.SQLAgent import SQLAgent


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
    print("🔍 INTERACTIVE SQL QUERY TOOL")
    print("="*80)
    print("\nOptions:")
    print("  1. Enter natural language question (uses AI agent)")
    print("  2. Enter SQL directly")
    print("  3. Show database schema")
    print("  4. Exit")
    print("="*80 + "\n")
    
    # Initialize
    print("🚀 Initializing SQL Agent...")
    agent = SQLAgent(dbPath='bike_store.db')
    conn = agent.duckdbConn
    
    try:
        while True:
            print("\n" + "-"*80)
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == "1":
                # Natural language query
                question = input("\n💬 Enter your question: ").strip()
                if not question:
                    continue
                
                print("\n🤖 Generating SQL...")
                try:
                    sql = agent.generate(question)
                    print(f"\n📝 Generated SQL:\n  {sql}\n")
                    
                    # Execute and show results
                    execute = input("Execute this query? (y/n): ").strip().lower()
                    if execute == 'y':
                        result = conn.execute(sql)
                        rows = result.fetchall()
                        headers = [desc[0] for desc in result.description]
                        
                        print("\n📊 Results:")
                        print_results(rows, headers)
                
                except Exception as e:
                    print(f"❌ Error: {e}")
            
            elif choice == "2":
                # Direct SQL
                print("\n💻 Enter SQL (or 'cancel' to go back):")
                sql = input("SQL> ").strip()
                
                if sql.lower() == 'cancel':
                    continue
                
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
            
            elif choice == "3":
                # Show schema
                print("\n📚 Database Schema:\n")
                tables = conn.execute("SHOW TABLES").fetchall()
                
                for table in tables:
                    table_name = table[0]
                    print(f"\n  Table: {table_name}")
                    print("  " + "-" * 40)
                    
                    columns = conn.execute(f"DESCRIBE {table_name}").fetchall()
                    for col in columns:
                        print(f"    {col[0]:<20} {col[1]}")
                    
                    # Show row count
                    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                    print(f"    Total rows: {count}")
            
            elif choice == "4":
                print("\n👋 Goodbye!")
                break
            
            else:
                print("Invalid option. Please choose 1-4.")
    
    finally:
        agent.close()
        conn.close()


if __name__ == "__main__":
    main()
