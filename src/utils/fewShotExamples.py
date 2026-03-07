"""
fewShotExamples.py: Few-shot examples for the SQLAgent.
"""

import numpy as np
from typing import Optional
from dataclasses import dataclass


@dataclass
class FewShotExample:
    question: str
    sql: str
    explanation: str = ""
    embedding: Optional[np.ndarray] = None

FEW_SHOT_EXAMPLES = [
    # --- Basic ---
    FewShotExample(
        question="How many customers are there?",
        sql="SELECT COUNT(*) FROM customers",
        explanation="Simple COUNT aggregation on single table"
    ),
    FewShotExample(
        question="Show me all brands",
        sql="SELECT brand_id, brand_name FROM brands",
        explanation="Simple SELECT all columns from single table"
    ),
    FewShotExample(
        question="List all product categories",
        sql="SELECT category_id, category_name FROM categories",
        explanation="Simple SELECT from single table"
    ),
    FewShotExample(
        question="What are the top 5 most expensive products?",
        sql="SELECT product_name, list_price FROM products ORDER BY list_price DESC LIMIT 5",
        explanation="SELECT with ORDER BY and LIMIT"
    ),
    FewShotExample(
        question="What is the average product price?",
        sql="SELECT AVG(list_price) FROM products",
        explanation="Simple aggregation function (AVG)"
    ),

    # --- Filtering ---
    FewShotExample(
        question="Find customers in New York",
        sql="SELECT first_name, last_name, city, state FROM customers WHERE state = 'NY'",
        explanation="SELECT with WHERE clause for filtering"
    ),
    FewShotExample(
        question="Show orders from March 2017",
        sql="SELECT order_id, customer_id, order_date FROM orders WHERE order_date >= '2017-03-01' AND order_date < '2017-04-01'",
        explanation="Date filtering using comparison operators or BETWEEN"
    ),

    # --- JOINs ---
    FewShotExample(
        question="Show me customer names with their order details",
        sql="SELECT c.first_name, c.last_name, o.order_id, o.order_date FROM customers c INNER JOIN orders o ON c.customer_id = o.customer_id",
        explanation="Two-table JOIN with column selection"
    ),
    FewShotExample(
        question="How many products are in each category?",
        sql="SELECT c.category_name, COUNT(p.product_id) FROM categories c LEFT JOIN products p ON c.category_id = p.category_id GROUP BY c.category_name",
        explanation="JOIN with GROUP BY aggregation"
    ),
    FewShotExample(
        question="Which stores have the most inventory?",
        sql="SELECT s.store_name, SUM(st.quantity) as total_inventory FROM stores s JOIN stocks st ON s.store_id = st.store_id GROUP BY s.store_id, s.store_name ORDER BY total_inventory DESC",
        explanation="Multi-table JOIN with GROUP BY and ORDER BY"
    ),
    FewShotExample(
        question="List all products and their available stock quantities by store",
        sql="SELECT p.product_name, s.store_name, st.quantity FROM products p JOIN stocks st ON p.product_id = st.product_id JOIN stores s ON st.store_id = s.store_id",
        explanation="Three-table JOIN"
    ),

    # --- Subqueries / Exclusion ---
    FewShotExample(
        question="Find customers who have never placed an order",
        sql="SELECT first_name, last_name, email FROM customers WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders)",
        explanation="Subquery with NOT IN for exclusion"
    ),

    # --- Revenue / Aggregations ---
    FewShotExample(
        question="What is the total revenue by brand?",
        sql="SELECT b.brand_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as total_revenue FROM brands b JOIN products p ON b.brand_id = p.brand_id JOIN order_items oi ON p.product_id = oi.product_id GROUP BY b.brand_name ORDER BY total_revenue DESC",
        explanation="Complex multi-table JOIN with calculated aggregation"
    ),
    FewShotExample(
        question="What is the total value of order 1?",
        sql="SELECT o.order_id, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as order_total FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.order_id = 1 GROUP BY o.order_id",
        explanation="Order totals must be calculated from order_items: quantity * list_price * (1 - discount)"
    ),
    FewShotExample(
        question="Show customers with their total spending",
        sql="SELECT c.first_name, c.last_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as total_spent FROM customers c JOIN orders o ON c.customer_id = o.customer_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY c.customer_id, c.first_name, c.last_name",
        explanation="Customer spending requires joining through orders to order_items and calculating totals"
    ),
    FewShotExample(
        question="What is the average order value?",
        sql="SELECT AVG(order_total) FROM (SELECT o.order_id, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) as order_total FROM orders o JOIN order_items oi ON o.order_id = oi.order_id GROUP BY o.order_id) AS order_totals",
        explanation="Average order value requires subquery to first calculate each order's total. Always alias subqueries (AS order_totals) — required by most SQL engines."
    ),

    # --- Date Grouping ---
    FewShotExample(
        question="How many orders were placed in each year?",
        sql="SELECT YEAR(order_date) AS year, COUNT(order_id) AS order_count FROM orders GROUP BY YEAR(order_date) ORDER BY year",
        explanation="Use YEAR() or MONTH() directly in SELECT and GROUP BY on the orders table. Do not join order_items for a simple order count — that inflates results."
    ),
    FewShotExample(
        question="What is the monthly revenue for 2017?",
        sql="SELECT MONTH(o.order_date) AS month, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS monthly_revenue FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE YEAR(o.order_date) = 2017 GROUP BY MONTH(o.order_date) ORDER BY month",
        explanation="Monthly revenue requires joining order_items and grouping by MONTH(). Filter the year with WHERE YEAR(...) = N before grouping."
    ),

    # --- CTEs ---
    FewShotExample(
        question="What percentage of total revenue does each category contribute?",
        sql="WITH category_revenue AS (SELECT c.category_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS category_total FROM categories c JOIN products p ON c.category_id = p.category_id JOIN order_items oi ON p.product_id = oi.product_id GROUP BY c.category_name), total_revenue AS (SELECT SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS overall_total FROM order_items oi) SELECT cr.category_name, ROUND((cr.category_total / tr.overall_total) * 100, 2) AS revenue_pct FROM category_revenue cr, total_revenue tr ORDER BY revenue_pct DESC",
        explanation="Use a CTE (WITH ...) to compute a subtotal, then divide by a second CTE for the grand total. Cleaner than a correlated subquery for percentage-of-total patterns."
    ),

    # --- Window Functions ---
    FewShotExample(
        question="Show month-over-month revenue growth for 2017",
        sql="SELECT MONTH(o.order_date) AS month, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS revenue, LAG(SUM(oi.quantity * oi.list_price * (1 - oi.discount))) OVER (ORDER BY MONTH(o.order_date)) AS prev_revenue FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE YEAR(o.order_date) = 2017 GROUP BY MONTH(o.order_date) ORDER BY month",
        explanation="Use LAG() window function to access the previous row's value for growth calculations. Requires GROUP BY month first, then LAG() in the SELECT with OVER (ORDER BY month)."
    ),

    # --- Store Revenue (via orders, not stocks) ---
    FewShotExample(
        question="Which store has the highest total revenue?",
        sql="SELECT s.store_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS total_revenue FROM stores s JOIN orders o ON s.store_id = o.store_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY s.store_id, s.store_name ORDER BY total_revenue DESC LIMIT 1",
        explanation="Store revenue must go through orders not stocks. stocks is inventory only. Correct path: stores -> orders -> order_items"
    ),
    FewShotExample(
        question="Show total revenue per store",
        sql="SELECT s.store_name, SUM(oi.quantity * oi.list_price * (1 - oi.discount)) AS total_revenue FROM stores s JOIN orders o ON s.store_id = o.store_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY s.store_id, s.store_name ORDER BY total_revenue DESC",
        explanation="Store revenue must go through orders not stocks. stocks is inventory only. Correct path: stores -> orders -> order_items"
    ),

    # --- Top-per-group pattern ---
    FewShotExample(
        question="For each store, show the most expensive product in stock",
        sql="SELECT s.store_name, p.product_name, p.list_price FROM stores s JOIN stocks st ON s.store_id = st.store_id JOIN products p ON st.product_id = p.product_id WHERE (s.store_id, p.list_price) IN (SELECT st2.store_id, MAX(p2.list_price) FROM stocks st2 JOIN products p2 ON st2.product_id = p2.product_id GROUP BY st2.store_id)",
        explanation="Top-1 per group pattern: use a subquery to find the MAX per group, then filter the outer query using (group_key, max_value) IN (...). Never use GROUP BY on product_name for per-store max — that returns all products, not one per store."
    ),
    FewShotExample(
        question="What is the most expensive product in each brand?",
        sql="SELECT b.brand_name, p.product_name, p.list_price FROM products p JOIN brands b ON p.brand_id = b.brand_id WHERE (p.brand_id, p.list_price) IN (SELECT brand_id, MAX(list_price) FROM products GROUP BY brand_id) ORDER BY p.list_price DESC",
        explanation="Top-1 per group: subquery finds MAX price per brand_id, outer query filters to only those rows. NEVER use GROUP BY (brand_name, product_name) with MAX() — that groups every product separately and returns all 291 rows, not one per brand. The correct result has exactly one row per brand."
    ),
    FewShotExample(
        question="Show the cheapest product in each category",
        sql="SELECT c.category_name, p.product_name, p.list_price FROM products p JOIN categories c ON p.category_id = c.category_id WHERE (p.category_id, p.list_price) IN (SELECT category_id, MIN(list_price) FROM products GROUP BY category_id) ORDER BY p.list_price ASC",
        explanation="Top-1 per group (MIN variant): same (group_key, extreme_value) IN (subquery) pattern. Use MIN() for cheapest. Never GROUP BY both category and product_name — that returns all products."
    ),

    # --- Self-join / Hierarchy ---
    FewShotExample(
        question="Which staff members manage other staff, and how many people does each manager supervise?",
        sql="SELECT m.first_name, m.last_name, COUNT(s.staff_id) AS direct_reports FROM staffs m JOIN staffs s ON m.staff_id = CAST(s.manager_id AS BIGINT) GROUP BY m.staff_id, m.first_name, m.last_name ORDER BY direct_reports DESC",
        explanation="Self-join pattern for hierarchy: alias the same table twice (m=managers, s=subordinates) and join ON m.staff_id = s.manager_id. Never use WHERE manager_id IS NOT NULL with GROUP BY — that counts how many managers each staff member has, not how many reports each manager has."
    ),
]
