-- BUOC 2: chay SAU KHI package SSIS nap xong du lieu vao OlistDW.
USE OlistDW;
GO

-- 2.1 Dat khoa chinh cho dim_location (SSIS doc location_id dang chuoi nen luc tao bang chua dat PK).
-- Hai lenh phai nam o hai batch (GO) - ADD PRIMARY KEY can cot da NOT NULL.
ALTER TABLE dbo.dim_location ALTER COLUMN location_id INT NOT NULL;
GO
ALTER TABLE dbo.dim_location ADD PRIMARY KEY (location_id);
GO

-- 2.2 So dong ky vong: customer 99441, seller 3095, product 32951, review 98410,
--     order_items 112650, order_payment 103886, seller_lead 8000, location 1000325, category 74
SELECT 'dim_customer' AS tbl, COUNT(*) AS n FROM dbo.dim_customer UNION ALL
SELECT 'dim_seller', COUNT(*) FROM dbo.dim_seller UNION ALL
SELECT 'dim_product', COUNT(*) FROM dbo.dim_product UNION ALL
SELECT 'dim_product_category', COUNT(*) FROM dbo.dim_product_category UNION ALL
SELECT 'dim_review', COUNT(*) FROM dbo.dim_review UNION ALL
SELECT 'dim_location', COUNT(*) FROM dbo.dim_location UNION ALL
SELECT 'fact_order_items', COUNT(*) FROM dbo.fact_order_items UNION ALL
SELECT 'fact_order_payment', COUNT(*) FROM dbo.fact_order_payment UNION ALL
SELECT 'fact_seller_lead', COUNT(*) FROM dbo.fact_seller_lead;

-- 2.3 Ven toan khoa ngoai (moi truy van phai tra ve 0)
SELECT COUNT(*) AS customer_khong_co_location FROM dbo.dim_customer c LEFT JOIN dbo.dim_location l ON l.location_id = c.location_id WHERE l.location_id IS NULL;
SELECT COUNT(*) AS seller_khong_co_location   FROM dbo.dim_seller   s LEFT JOIN dbo.dim_location l ON l.location_id = s.location_id WHERE l.location_id IS NULL;
SELECT COUNT(*) AS fact_khong_co_customer     FROM dbo.fact_order_items f LEFT JOIN dbo.dim_customer c ON c.customer_id = f.customer_id WHERE c.customer_id IS NULL;
SELECT COUNT(*) AS fact_khong_co_product      FROM dbo.fact_order_items f LEFT JOIN dbo.dim_product p ON p.product_id = f.product_id WHERE p.product_id IS NULL;

-- Neu "customer_khong_co_location" lon (location_id bi nhan 10 do sai locale khi nap CSV), sua:
-- UPDATE dbo.dim_customer SET location_id = location_id/10 WHERE location_id % 10 = 0;
-- UPDATE dbo.dim_seller   SET location_id = location_id/10 WHERE location_id % 10 = 0;
