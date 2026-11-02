-- BUOC 2: chay SAU KHI package SSIS nap xong du lieu vao OlistDW.
USE OlistDW;
GO

-- 2.1 Dat khoa chinh cho dim_location (SSIS doc location_id dang chuoi nen luc tao bang chua dat PK).
-- Hai lenh phai nam o hai batch (GO) - ADD PRIMARY KEY can cot da NOT NULL.
ALTER TABLE dbo.dim_location ALTER COLUMN location_id INT NOT NULL;
GO
ALTER TABLE dbo.dim_location ADD CONSTRAINT PK_dim_location PRIMARY KEY (location_id);
GO

-- 2.2 Khoa ngoai. Dat sau khi nap vi SQL Server kiem tra du lieu hien co khi tao FK.
-- Cot FK cho phep NULL nen cac dong chua tra cuu duoc van nap binh thuong.
ALTER TABLE dbo.dim_product ADD CONSTRAINT FK_dim_product_category
    FOREIGN KEY (product_category_name) REFERENCES dbo.dim_product_category(product_category_name);
ALTER TABLE dbo.dim_customer ADD CONSTRAINT FK_dim_customer_location
    FOREIGN KEY (location_id) REFERENCES dbo.dim_location(location_id);
ALTER TABLE dbo.dim_seller ADD CONSTRAINT FK_dim_seller_location
    FOREIGN KEY (location_id) REFERENCES dbo.dim_location(location_id);
ALTER TABLE dbo.fact_order_items ADD CONSTRAINT FK_fact_order_items_customer
    FOREIGN KEY (customer_id) REFERENCES dbo.dim_customer(customer_id);
ALTER TABLE dbo.fact_order_items ADD CONSTRAINT FK_fact_order_items_seller
    FOREIGN KEY (seller_id) REFERENCES dbo.dim_seller(seller_id);
ALTER TABLE dbo.fact_order_items ADD CONSTRAINT FK_fact_order_items_product
    FOREIGN KEY (product_id) REFERENCES dbo.dim_product(product_id);
GO

-- Ba quan he con lai CO CHU DICH khong dat FK:
--   fact_order_payment.order_id -> fact_order_items.order_id (830 dong mo coi)
--   dim_review.order_id         -> fact_order_items.order_id (725 dong mo coi)
--   fact_seller_lead.seller_id  -> dim_seller.seller_id      (462 dong mo coi)
-- Ly do 1: day la nghiep vu that (don bi huy van co thanh toan/danh gia; doi tac da
--   ky hop dong nhung chua ban duoc don nao), dat FK se chan mat du lieu dung.
-- Ly do 2: khoa chinh cua fact_order_items la (order_id, order_item_id) nen rieng
--   order_id khong duy nhat, SQL Server khong cho tham chieu toi. Muon dat FK phai
--   tach them bang dim_order.
-- Thay vi FK, cac quan he nay duoc kiem tra bang truy van o muc 2.4.

-- 2.3 So dong ky vong: customer 99441, seller 3095, product 32951, review 98410,
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

-- 2.4 Ven toan tham chieu cho ba quan he khong dat FK (xem ly do o muc 2.2).
--     Cac quan he con lai da duoc FK o muc 2.2 bao dam,
--     khong can kiem bang truy van.
-- Ky vong: 830, 725, 462 (deu la nghiep vu that, khong phai loi ETL).
SELECT COUNT(*) AS payment_khong_co_order FROM dbo.fact_order_payment p
    WHERE NOT EXISTS (SELECT 1 FROM dbo.fact_order_items f WHERE f.order_id = p.order_id);
SELECT COUNT(*) AS review_khong_co_order  FROM dbo.dim_review r
    WHERE NOT EXISTS (SELECT 1 FROM dbo.fact_order_items f WHERE f.order_id = r.order_id);
SELECT COUNT(*) AS lead_khong_co_seller   FROM dbo.fact_seller_lead l
    WHERE l.seller_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM dbo.dim_seller s WHERE s.seller_id = l.seller_id);
