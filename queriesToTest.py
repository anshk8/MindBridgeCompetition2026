"""
queriesToTest.py - Extended Test Query Bank

Contains medium, hard, and ambiguous/nonsense queries for stress-testing
the SQL agent. None of these are in the few-shot example bank.

Import in your test file:
    from queriesToTest import EXTENDED_QUERIES
"""

EXTENDED_QUERIES = {

    # ─────────────────────────────────────────────────────────────────
    # MEDIUM QUERIES
    # New patterns: subquery comparison, NULL handling, brand filter,
    # year grouping, status filter, recent record, staff activity
    # ─────────────────────────────────────────────────────────────────
    "medium": [
        {
            "id": "M6",
            "question": "Show all products that cost more than the average product price",
            "expected_sql": "SELECT product_name, list_price FROM products WHERE list_price > (SELECT AVG(list_price) FROM products) ORDER BY list_price DESC",
            "notes": "Scalar subquery comparison — WHERE with subquery returning single value"
        },
        {
            "id": "M7",
            "question": "How many orders were placed in each year?",
            "expected_sql": "SELECT YEAR(order_date) AS year, COUNT(order_id) AS order_count FROM orders GROUP BY YEAR(order_date) ORDER BY year",
            "notes": "Date extraction with GROUP BY — YEAR() function aggregation"
        },
        {
            "id": "M8",
            "question": "List all products from the Trek brand",
            "expected_sql": "SELECT p.product_name, p.list_price, p.model_year FROM products p JOIN brands b ON p.brand_id = b.brand_id WHERE b.brand_name = 'Trek' ORDER BY p.list_price DESC",
            "notes": "JOIN with string filter on related table — tests brand name lookup"
        },
        {
            "id": "M9",
            "question": "Which customers are from Texas?",
            "expected_sql": "SELECT first_name, last_name, city FROM customers WHERE state = 'TX'",
            "notes": "Simple state filter — tests state abbreviation handling (TX not Texas)"
        },
        {
            "id": "M10",
            "question": "How many orders does each store have?",
            "expected_sql": "SELECT s.store_name, COUNT(o.order_id) AS order_count FROM stores s LEFT JOIN orders o ON s.store_id = o.store_id GROUP BY s.store_id, s.store_name ORDER BY order_count DESC",
            "notes": "LEFT JOIN + GROUP BY — preserves stores with zero orders"
        },
        {
            "id": "M11",
            "question": "What is the most recent order date in the database?",
            "expected_sql": "SELECT MAX(order_date) AS most_recent_order FROM orders",
            "notes": "Simple MAX on date column — single value aggregation"
        },
        {
            "id": "M12",
            "question": "Find customers who have placed more than 3 orders",
            "expected_sql": "SELECT c.first_name, c.last_name, COUNT(o.order_id) AS order_count FROM customers c JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.customer_id, c.first_name, c.last_name HAVING COUNT(o.order_id) > 3 ORDER BY order_count DESC",
            "notes": "JOIN + GROUP BY + HAVING — post-aggregation filter on count"
        },
    ],

    # ─────────────────────────────────────────────────────────────────
    # HARD QUERIES
    # New patterns: store revenue ranking, most ordered product,
    # multi-category customers, staff revenue, low stock alert,
    # order with most items, discount analysis
    # ─────────────────────────────────────────────────────────────────
    "hard": [
        {
            "id": "H11",
            "question": "Which store generated the highest total revenue?",
            "expected_sql": "SELECT s.store_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS total_revenue FROM stores s JOIN orders o ON s.store_id = o.store_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY s.store_id, s.store_name ORDER BY total_revenue DESC LIMIT 1",
            "notes": "3-table JOIN + revenue formula + LIMIT 1 — store revenue ranking"
        },
        {
            "id": "H12",
            "question": "What is the most ordered product by total quantity sold?",
            "expected_sql": "SELECT p.product_name, SUM(oi.quantity) AS total_quantity_sold FROM products p JOIN order_items oi ON p.product_id = oi.product_id GROUP BY p.product_id, p.product_name ORDER BY total_quantity_sold DESC LIMIT 1",
            "notes": "JOIN + SUM quantity + ORDER BY + LIMIT — product popularity ranking"
        },
        {
            "id": "H13",
            "question": "Find customers who have ordered products from at least 3 different categories",
            "expected_sql": "SELECT c.first_name, c.last_name, COUNT(DISTINCT p.category_id) AS category_count FROM customers c JOIN orders o ON c.customer_id = o.customer_id JOIN order_items oi ON o.order_id = oi.order_id JOIN products p ON oi.product_id = p.product_id GROUP BY c.customer_id, c.first_name, c.last_name HAVING COUNT(DISTINCT p.category_id) >= 3 ORDER BY category_count DESC",
            "notes": "4-table JOIN + COUNT DISTINCT + HAVING — cross-category purchase analysis"
        },
        {
            "id": "H14",
            "question": "Which staff member has handled the most orders and how many?",
            "expected_sql": "SELECT s.first_name, s.last_name, COUNT(o.order_id) AS orders_handled FROM staffs s JOIN orders o ON s.staff_id = o.staff_id GROUP BY s.staff_id, s.first_name, s.last_name ORDER BY orders_handled DESC LIMIT 1",
            "notes": "staffs-orders JOIN + GROUP BY + ORDER BY + LIMIT 1 — staff performance"
        },
        {
            "id": "H15",
            "question": "Show all products that have stock below 5 units in any store",
            "expected_sql": "SELECT p.product_name, s.store_name, st.quantity FROM products p JOIN stocks st ON p.product_id = st.product_id JOIN stores s ON st.store_id = s.store_id WHERE st.quantity < 5 ORDER BY st.quantity ASC",
            "notes": "3-table JOIN + low threshold filter — inventory alert query"
        },
        {
            "id": "H16",
            "question": "What is the total revenue generated by each staff member?",
            "expected_sql": "SELECT s.first_name, s.last_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS total_revenue FROM staffs s JOIN orders o ON s.staff_id = o.staff_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY s.staff_id, s.first_name, s.last_name ORDER BY total_revenue DESC",
            "notes": "3-table JOIN through staffs→orders→order_items + revenue formula"
        },
        {
            "id": "H17",
            "question": "Which order contained the most individual items (by total quantity)?",
            "expected_sql": "SELECT oi.order_id, SUM(oi.quantity) AS total_items FROM order_items oi GROUP BY oi.order_id ORDER BY total_items DESC LIMIT 1",
            "notes": "Single table aggregation — SUM quantity per order, find max"
        },
        {
            "id": "H18",
            "question": "Show the average discount percentage applied per product category",
            "expected_sql": "SELECT c.category_name, ROUND(AVG(oi.discount) * 100, 2) AS avg_discount_pct FROM categories c JOIN products p ON c.category_id = p.category_id JOIN order_items oi ON p.product_id = oi.product_id GROUP BY c.category_id, c.category_name ORDER BY avg_discount_pct DESC",
            "notes": "3-table JOIN + AVG + ROUND + scale to percentage — discount analysis"
        },
    ],

    # ─────────────────────────────────────────────────────────────────
    # AMBIGUOUS QUERIES
    # These have partial answers — agent should produce something
    # reasonable or a safe fallback, not crash or hallucinate tables
    # ─────────────────────────────────────────────────────────────────
    "ambiguous": [
        {
            "id": "A1",
            "question": "Show me the best products",
            "expected_sql": "SELECT product_name, list_price FROM products ORDER BY list_price DESC LIMIT 10",
            "notes": "Ambiguous — 'best' is undefined. Agent should interpret as most expensive or most ordered. Any reasonable interpretation is acceptable."
        },
        {
            "id": "A2",
            "question": "Which customers are VIP?",
            "expected_sql": "SELECT c.first_name, c.last_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS total_spent FROM customers c JOIN orders o ON c.customer_id = o.customer_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY c.customer_id, c.first_name, c.last_name ORDER BY total_spent DESC LIMIT 20",
            "notes": "Ambiguous — no VIP column exists. Agent should interpret as top spenders. Any definition of 'VIP' using existing data is acceptable."
        },
        {
            "id": "A3",
            "question": "What are the popular items?",
            "expected_sql": "SELECT p.product_name, COUNT(oi.order_id) AS times_ordered FROM products p JOIN order_items oi ON p.product_id = oi.product_id GROUP BY p.product_id, p.product_name ORDER BY times_ordered DESC LIMIT 10",
            "notes": "Ambiguous — 'popular' is undefined. Agent should use order frequency or quantity sold as proxy."
        },
        {
            "id": "A4",
            "question": "Are sales going up or down?",
            "expected_sql": "SELECT YEAR(o.order_date) AS year, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS annual_revenue FROM orders o JOIN order_items oi ON o.order_id = oi.order_id GROUP BY YEAR(o.order_date) ORDER BY year",
            "notes": "Trend question — no single scalar answer. Agent should return year-over-year revenue to allow comparison. Interesting to see how it handles open-ended trend analysis."
        },
    ],

    # ─────────────────────────────────────────────────────────────────
    # NONSENSE QUERIES
    # These reference data that does not exist in this database.
    # Agent should either return a safe fallback or handle gracefully
    # without crashing or hallucinating non-existent tables/columns.
    # ─────────────────────────────────────────────────────────────────
    "nonsense": [
        {
            "id": "N1",
            "question": "What is the PS5 column in the Sun?",
            "expected_sql": "SELECT 1",
            "notes": "Pure nonsense — no PS5, no Sun table. Agent should return fallback without hallucinating."
        },
        {
            "id": "N2",
            "question": "Show me the weather forecast for the Santa Cruz store",
            "expected_sql": "SELECT 1",
            "notes": "Weather data does not exist in this database. Agent should not hallucinate a weather table."
        },
        {
            "id": "N3",
            "question": "Which customers have a loyalty score above 100?",
            "expected_sql": "SELECT 1",
            "notes": "No loyalty_score column exists anywhere. Agent should not invent it."
        },
        {
            "id": "N4",
            "question": "What is the profit margin for each product?",
            "expected_sql": "SELECT product_name, list_price FROM products ORDER BY list_price DESC",
            "notes": "Partially valid — cost data does not exist, only list_price. Agent may return list_price as a proxy or explain it cannot compute profit without cost. Either is acceptable."
        },
        {
            "id": "N5",
            "question": "How many returned orders are there?",
            "expected_sql": "SELECT 1",
            "notes": "No returns/refunds table exists. order_status codes exist but no return status is documented. Agent should not hallucinate a returns table."
        },
    ],
}
