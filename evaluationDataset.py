# evaluation_dataset.py
"""
Comprehensive evaluation dataset for Bike Store SQL Query Writer.

Based on:
- sqlservertutorial.net examples
- Common text-to-SQL patterns
- Real BI query scenarios
"""

EVALUATION_QUESTIONS = [
    # ========== CATEGORY 1: SIMPLE SELECT (Easy) ==========
    {
        "id": 1,
        "question": "Show me all brands",
        "expected_sql": "SELECT * FROM brands",
        "difficulty": "easy",
        "category": "simple_select",
        "expected_rows": 9  # Approximate
    },
    
    {
        "id": 2,
        "question": "List all product categories",
        "expected_sql": "SELECT category_name FROM categories",
        "difficulty": "easy",
        "category": "simple_select"
    },
    
    {
        "id": 3,
        "question": "What stores do we have?",
        "expected_sql": "SELECT store_name, city, state FROM stores",
        "difficulty": "easy",
        "category": "simple_select",
        "expected_rows": 3
    },
    
    # ========== CATEGORY 2: FILTERING (Easy-Medium) ==========
    {
        "id": 4,
        "question": "Show me products with price greater than 500",
        "expected_sql": "SELECT product_name, list_price FROM products WHERE list_price > 500",
        "difficulty": "easy",
        "category": "filtering"
    },
    
    {
        "id": 5,
        "question": "Find customers in New York",
        "expected_sql": "SELECT first_name, last_name, city, state FROM customers WHERE state = 'NY'",
        "difficulty": "easy",
        "category": "filtering"
    },
    
    {
        "id": 6,
        "question": "Show me all orders from 2018",
        "expected_sql": "SELECT order_id, order_date, order_status FROM orders WHERE YEAR(order_date) = 2018",
        "difficulty": "medium",
        "category": "filtering",
        "notes": "Date filtering - might use different syntax (EXTRACT, DATE_PART, etc.)"
    },
    
    {
        "id": 7,
        "question": "List products from Trek brand",
        "expected_sql": """SELECT p.product_name, p.list_price 
                          FROM products p 
                          JOIN brands b ON p.brand_id = b.brand_id 
                          WHERE b.brand_name = 'Trek'""",
        "difficulty": "medium",
        "category": "filtering_with_join"
    },
    
    # ========== CATEGORY 3: AGGREGATION (Medium) ==========
    {
        "id": 8,
        "question": "How many customers are there?",
        "expected_sql": "SELECT COUNT(*) FROM customers",
        "difficulty": "easy",
        "category": "aggregation",
        "expected_rows": 1
    },
    
    {
        "id": 9,
        "question": "What is the total number of products?",
        "expected_sql": "SELECT COUNT(*) FROM products",
        "difficulty": "easy",
        "category": "aggregation"
    },
    
    {
        "id": 10,
        "question": "What is the average product price?",
        "expected_sql": "SELECT AVG(list_price) FROM products",
        "difficulty": "easy",
        "category": "aggregation"
    },
    
    {
        "id": 11,
        "question": "How many orders were placed in 2018?",
        "expected_sql": "SELECT COUNT(*) FROM orders WHERE YEAR(order_date) = 2018",
        "difficulty": "medium",
        "category": "aggregation_with_filter"
    },
    
    # ========== CATEGORY 4: SORTING & LIMITING (Medium) ==========
    {
        "id": 12,
        "question": "What are the top 5 most expensive products?",
        "expected_sql": "SELECT product_name, list_price FROM products ORDER BY list_price DESC LIMIT 5",
        "difficulty": "medium",
        "category": "sorting_limiting"
    },
    
    {
        "id": 13,
        "question": "Show me the 10 cheapest products",
        "expected_sql": "SELECT product_name, list_price FROM products ORDER BY list_price ASC LIMIT 10",
        "difficulty": "medium",
        "category": "sorting_limiting"
    },
    
    {
        "id": 14,
        "question": "List the newest 5 orders",
        "expected_sql": "SELECT order_id, order_date, customer_id FROM orders ORDER BY order_date DESC LIMIT 5",
        "difficulty": "medium",
        "category": "sorting_limiting"
    },
    
    # ========== CATEGORY 5: GROUP BY (Medium-Hard) ==========
    {
        "id": 15,
        "question": "How many products are in each category?",
        "expected_sql": """SELECT c.category_name, COUNT(p.product_id) as product_count
                          FROM categories c
                          LEFT JOIN products p ON c.category_id = p.category_id
                          GROUP BY c.category_name""",
        "difficulty": "medium",
        "category": "groupby_aggregation"
    },
    
    {
        "id": 16,
        "question": "What is the total revenue by brand?",
        "expected_sql": """SELECT b.brand_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as total_revenue
                          FROM brands b
                          JOIN products p ON b.brand_id = p.brand_id
                          JOIN order_items oi ON p.product_id = oi.product_id
                          GROUP BY b.brand_name
                          ORDER BY total_revenue DESC""",
        "difficulty": "hard",
        "category": "groupby_aggregation_joins"
    },
    
    {
        "id": 17,
        "question": "How many orders did each customer place?",
        "expected_sql": """SELECT c.first_name, c.last_name, COUNT(o.order_id) as order_count
                          FROM customers c
                          LEFT JOIN orders o ON c.customer_id = o.customer_id
                          GROUP BY c.customer_id, c.first_name, c.last_name
                          ORDER BY order_count DESC""",
        "difficulty": "medium",
        "category": "groupby_aggregation"
    },
    
    # ========== CATEGORY 6: COMPLEX JOINS (Hard) ==========
    {
        "id": 18,
        "question": "Show me customer names with their order details",
        "expected_sql": """SELECT c.first_name, c.last_name, o.order_id, o.order_date, o.order_status
                          FROM customers c
                          JOIN orders o ON c.customer_id = o.customer_id
                          ORDER BY o.order_date DESC""",
        "difficulty": "medium",
        "category": "joins"
    },
    
    {
        "id": 19,
        "question": "Which store has the most inventory?",
        "expected_sql": """SELECT s.store_name, SUM(st.quantity) as total_inventory
                          FROM stores s
                          JOIN stocks st ON s.store_id = st.store_id
                          GROUP BY s.store_id, s.store_name
                          ORDER BY total_inventory DESC
                          LIMIT 1""",
        "difficulty": "hard",
        "category": "joins_aggregation"
    },
    
    {
        "id": 20,
        "question": "List all products and their available stock quantities by store",
        "expected_sql": """SELECT p.product_name, s.store_name, st.quantity
                          FROM products p
                          JOIN stocks st ON p.product_id = st.product_id
                          JOIN stores s ON st.store_id = s.store_id
                          ORDER BY p.product_name, s.store_name""",
        "difficulty": "medium",
        "category": "joins"
    },
    
    # ========== CATEGORY 7: SUBQUERIES (Hard) ==========
    {
        "id": 21,
        "question": "Find customers who have never placed an order",
        "expected_sql": """SELECT first_name, last_name, email
                          FROM customers
                          WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders)""",
        "difficulty": "hard",
        "category": "subquery_negation",
        "notes": "Can also use LEFT JOIN WHERE orders.customer_id IS NULL"
    },
    
    {
        "id": 22,
        "question": "Show products that are out of stock in all stores",
        "expected_sql": """SELECT p.product_name
                          FROM products p
                          WHERE p.product_id NOT IN (
                              SELECT product_id FROM stocks WHERE quantity > 0
                          )""",
        "difficulty": "hard",
        "category": "subquery"
    },
    
    {
        "id": 23,
        "question": "Find products with above average price",
        "expected_sql": """SELECT product_name, list_price
                          FROM products
                          WHERE list_price > (SELECT AVG(list_price) FROM products)
                          ORDER BY list_price DESC""",
        "difficulty": "hard",
        "category": "subquery_aggregation"
    },
    
    # ========== CATEGORY 8: DISTINCT (Easy-Medium) ==========
    {
        "id": 24,
        "question": "How many different brands do we have?",
        "expected_sql": "SELECT COUNT(DISTINCT brand_id) FROM products",
        "difficulty": "easy",
        "category": "distinct"
    },
    
    {
        "id": 25,
        "question": "Which cities do our customers live in?",
        "expected_sql": "SELECT DISTINCT city, state FROM customers ORDER BY state, city",
        "difficulty": "easy",
        "category": "distinct"
    },
    
    # ========== CATEGORY 9: BUSINESS INTELLIGENCE (Hard) ==========
    {
        "id": 26,
        "question": "What is the average order value?",
        "expected_sql": """SELECT AVG(order_total) as avg_order_value
                          FROM (
                              SELECT o.order_id, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as order_total
                              FROM orders o
                              JOIN order_items oi ON o.order_id = oi.order_id
                              GROUP BY o.order_id
                          ) as order_values""",
        "difficulty": "hard",
        "category": "business_intelligence"
    },
    
    {
        "id": 27,
        "question": "Show the top 10 customers by total purchase amount",
        "expected_sql": """SELECT c.first_name, c.last_name, 
                                 SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as total_spent
                          FROM customers c
                          JOIN orders o ON c.customer_id = o.customer_id
                          JOIN order_items oi ON o.order_id = oi.order_id
                          GROUP BY c.customer_id, c.first_name, c.last_name
                          ORDER BY total_spent DESC
                          LIMIT 10""",
        "difficulty": "hard",
        "category": "business_intelligence"
    },
    
    {
        "id": 28,
        "question": "What is the total sales by store?",
        "expected_sql": """SELECT s.store_name, 
                                 SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as total_sales
                          FROM stores s
                          JOIN orders o ON s.store_id = o.store_id
                          JOIN order_items oi ON o.order_id = oi.order_id
                          GROUP BY s.store_id, s.store_name
                          ORDER BY total_sales DESC""",
        "difficulty": "hard",
        "category": "business_intelligence"
    },
    
    # ========== CATEGORY 10: TEMPORAL (Medium-Hard) ==========
    {
        "id": 29,
        "question": "Show me orders from last month",
        "expected_sql": """SELECT order_id, order_date, customer_id
                          FROM orders
                          WHERE order_date >= DATE_SUB(CURRENT_DATE, INTERVAL 1 MONTH)""",
        "difficulty": "medium",
        "category": "temporal",
        "notes": "Syntax varies by SQL dialect (DATE_SUB, DATEADD, etc.)"
    },
    
    {
        "id": 30,
        "question": "How many orders were completed each month in 2017?",
        "expected_sql": """SELECT 
                              EXTRACT(MONTH FROM order_date) as month,
                              COUNT(*) as order_count
                          FROM orders
                          WHERE YEAR(order_date) = 2017 AND order_status = 4
                          GROUP BY EXTRACT(MONTH FROM order_date)
                          ORDER BY month""",
        "difficulty": "hard",
        "category": "temporal_aggregation"
    }
]
