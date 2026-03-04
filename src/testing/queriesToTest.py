"""
queriesToTest.py — All test query banks.

BASIC_QUERIES   — easy / medium / hard / hard_advanced (core coverage)
EXTENDED_QUERIES — medium / hard / ambiguous / nonsense (stress tests)
ALL_QUERIES     — merged view of both banks, used by testAgentPipeline.py

Import in your test file:
    from src.testing.queriesToTest import ALL_QUERIES
"""


BASIC_QUERIES = {

    "easy": [
        {
            "id": "E1",
            "question": "List all stores in California",
            "expected_sql": "SELECT store_name, city, state FROM stores WHERE state = 'CA'",
            "notes": "Simple WHERE filter on state column"
        },
        {
            "id": "E2",
            "question": "What is the cheapest product in the database?",
            "expected_sql": "SELECT product_name, list_price FROM products ORDER BY list_price ASC LIMIT 1",
            "notes": "MIN via ORDER BY ASC + LIMIT"
        },
        {
            "id": "E3",
            "question": "How many products were made in 2018?",
            "expected_sql": "SELECT COUNT(*) FROM products WHERE model_year = 2018",
            "notes": "COUNT with WHERE on year column"
        },
        {
            "id": "E4",
            "question": "Show all staff emails",
            "expected_sql": "SELECT first_name, last_name, email FROM staffs",
            "notes": "Simple SELECT specific columns"
        },
        {
            "id": "E5",
            "question": "What is the total quantity of all products in stock?",
            "expected_sql": "SELECT SUM(quantity) FROM stocks",
            "notes": "Simple SUM aggregation"
        },
    ],

    "medium": [
        {
            "id": "M1",
            "question": "Show all orders placed in January 2017",
            "expected_sql": "SELECT order_id, order_date FROM orders WHERE order_date BETWEEN '2017-01-01' AND '2017-01-31'",
            "notes": "Date range filtering with BETWEEN"
        },
        {
            "id": "M2",
            "question": "Which brands have more than 10 products?",
            "expected_sql": "SELECT b.brand_name, COUNT(p.product_id) as product_count FROM brands b JOIN products p ON b.brand_id = p.brand_id GROUP BY b.brand_name HAVING COUNT(p.product_id) > 10",
            "notes": "JOIN with GROUP BY and HAVING clause"
        },
        {
            "id": "M3",
            "question": "List all staff members and their store names",
            "expected_sql": "SELECT s.first_name, s.last_name, st.store_name FROM staffs s JOIN stores st ON s.store_id = st.store_id",
            "notes": "Two-table JOIN"
        },
        {
            "id": "M4",
            "question": "Find products priced between 1000 and 2000 dollars",
            "expected_sql": "SELECT product_name, brand_id, list_price FROM products WHERE list_price BETWEEN 1000 AND 2000",
            "notes": "BETWEEN operator for range"
        },
        {
            "id": "M5",
            "question": "How many orders has each customer placed?",
            "expected_sql": "SELECT c.first_name, c.last_name, COUNT(o.order_id) as order_count FROM customers c LEFT JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.customer_id, c.first_name, c.last_name",
            "notes": "LEFT JOIN with GROUP BY"
        },
    ],

    "hard": [
        {
            "id": "H1",
            "question": "What is the average order value for each customer?",
            "expected_sql": "SELECT c.first_name, c.last_name, AVG(oi.quantity * oi.list_price * (1 - oi.discount)) as avg_order_value FROM customers c JOIN orders o ON c.customer_id = o.customer_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY c.customer_id, c.first_name, c.last_name",
            "notes": "3-table JOIN with calculated AVG"
        },
        {
            "id": "H2",
            "question": "Which products have never been ordered?",
            "expected_sql": "SELECT product_name, product_id FROM products WHERE product_id NOT IN (SELECT DISTINCT product_id FROM order_items)",
            "notes": "NOT IN subquery for exclusion"
        },
        {
            "id": "H3",
            "question": "Show the top 3 customers by total purchase amount",
            "expected_sql": "SELECT c.first_name, c.last_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as total_spent FROM customers c JOIN orders o ON c.customer_id = o.customer_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY c.customer_id, c.first_name, c.last_name ORDER BY total_spent DESC LIMIT 3",
            "notes": "Multi-table JOIN with complex calculation, ORDER BY, LIMIT"
        },
        {
            "id": "H4",
            "question": "For each store, show the most expensive product in stock",
            "expected_sql": "SELECT s.store_name, p.product_name, p.list_price FROM stores s JOIN stocks st ON s.store_id = st.store_id JOIN products p ON st.product_id = p.product_id WHERE (s.store_id, p.list_price) IN (SELECT st2.store_id, MAX(p2.list_price) FROM stocks st2 JOIN products p2 ON st2.product_id = p2.product_id GROUP BY st2.store_id)",
            "notes": "Correlated subquery with MAX per group"
        },
        {
            "id": "H5",
            "question": "What percentage of total revenue does each category contribute?",
            "expected_sql": "SELECT c.category_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as category_revenue, (SUM(oi.quantity * oi.list_price * (1 - oi.discount)) * 100.0 / (SELECT SUM(quantity * list_price * (1 - discount)) FROM order_items)) as revenue_percentage FROM categories c JOIN products p ON c.category_id = p.category_id JOIN order_items oi ON p.product_id = oi.product_id GROUP BY c.category_name ORDER BY revenue_percentage DESC",
            "notes": "Multi-table JOIN with subquery for percentage calculation"
        },
    ],

    "hard_advanced": [
        {
            "id": "H6",
            "question": "Which staff members manage other staff, and how many people does each manager supervise?",
            "expected_sql": "SELECT m.first_name, m.last_name, m.staff_id, COUNT(s.staff_id) as direct_reports FROM staffs m JOIN staffs s ON m.staff_id = CAST(s.manager_id AS BIGINT) GROUP BY m.staff_id, m.first_name, m.last_name ORDER BY direct_reports DESC",
            "notes": "Self-join on staffs table"
        },
        {
            "id": "H7",
            "question": "For each brand, show the number of products and the average price, but only for brands that have products in at least 3 different categories",
            "expected_sql": "SELECT b.brand_name, COUNT(DISTINCT p.product_id) as product_count, AVG(p.list_price) as avg_price FROM brands b JOIN products p ON b.brand_id = p.brand_id GROUP BY b.brand_id, b.brand_name HAVING COUNT(DISTINCT p.category_id) >= 3 ORDER BY product_count DESC",
            "notes": "Multiple aggregations with HAVING on COUNT DISTINCT"
        },
        {
            "id": "H8",
            "question": "List customers who placed orders in 2016 but not in 2017",
            "expected_sql": "SELECT c.first_name, c.last_name, c.email FROM customers c WHERE c.customer_id IN (SELECT DISTINCT customer_id FROM orders WHERE YEAR(order_date) = 2016) AND c.customer_id NOT IN (SELECT DISTINCT customer_id FROM orders WHERE YEAR(order_date) = 2017)",
            "notes": "Multiple subqueries with set operations"
        },
        {
            "id": "H9",
            "question": "What is the month-over-month revenue growth for 2017?",
            "expected_sql": "SELECT MONTH(o.order_date) as month, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as monthly_revenue FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE YEAR(o.order_date) = 2017 GROUP BY MONTH(o.order_date) ORDER BY month",
            "notes": "Date aggregation by month with calculated revenue"
        },
        {
            "id": "H10",
            "question": "Find products that are stocked in all stores",
            "expected_sql": "SELECT p.product_name, p.product_id FROM products p WHERE (SELECT COUNT(DISTINCT st.store_id) FROM stocks st WHERE st.product_id = p.product_id) = (SELECT COUNT(*) FROM stores)",
            "notes": "Correlated subquery — universal quantification"
        },
    ],
}

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


# Merged view — combine BASIC_QUERIES and EXTENDED_QUERIES under shared keys.
ALL_QUERIES: dict = {}
for _bank in (BASIC_QUERIES, EXTENDED_QUERIES):
    for _key, _queries in _bank.items():
        ALL_QUERIES.setdefault(_key, []).extend(_queries)
