-- BUOC 4: doi chieu voi cac truy van MDX trong ssas/mdx/ (chay sau khi cube da deploy va process).
-- Tong (MDX: ssas/mdx/02_compare_with_sql.mdx)
USE OlistDW;
SELECT SUM(price) AS revenue, SUM(freight_value) AS freight, COUNT(*) AS items
FROM dbo.fact_order_items;

-- Top 5 category theo doanh thu
SELECT TOP 5 p.product_category_name, SUM(f.price) AS revenue, COUNT(*) AS items
FROM dbo.fact_order_items f
LEFT JOIN dbo.dim_product p ON p.product_id = f.product_id
GROUP BY p.product_category_name
ORDER BY revenue DESC;

-- Doanh thu theo bang (Q1/Q9 trong ssas/mdx/01_olist_mdx_queries.mdx; dia ly theo khach hang)
SELECT l.geolocation_state, SUM(f.price) AS revenue, COUNT(*) AS items
FROM dbo.fact_order_items f
JOIN dbo.dim_customer c ON c.customer_id = f.customer_id
JOIN dbo.dim_location l ON l.location_id = c.location_id
GROUP BY l.geolocation_state
ORDER BY revenue DESC;

-- Q9: bang SP va nhom beleza_saude -> 462305.22 / 4204
SELECT SUM(f.price) AS revenue, COUNT(*) AS items
FROM dbo.fact_order_items f
JOIN dbo.dim_customer c ON c.customer_id = f.customer_id
JOIN dbo.dim_location l ON l.location_id = c.location_id
JOIN dbo.dim_product  p ON p.product_id  = f.product_id
WHERE l.geolocation_state = 'SP' AND p.product_category_name = 'beleza_saude';
