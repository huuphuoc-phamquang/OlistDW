-- BUOC 1: tao database OlistDW va cac bang rong (khop metadata cot trong ssis/Project/Package.dtsx, khong co FK).
-- Chay truoc khi chay package SSIS. Script nay DROP va tao lai toan bo bang.
IF DB_ID(N'OlistDW') IS NULL CREATE DATABASE OlistDW;
GO
USE OlistDW;
GO
DROP TABLE IF EXISTS dbo.fact_seller_lead, dbo.fact_order_payment, dbo.fact_order_items,
                     dbo.dim_review, dbo.dim_customer, dbo.dim_seller, dbo.dim_product,
                     dbo.dim_product_category, dbo.dim_location;
GO
CREATE TABLE dbo.dim_location (
    location_id NVARCHAR(255), geolocation_zip_code_prefix NVARCHAR(255),
    geolocation_lat NVARCHAR(255), geolocation_lng NVARCHAR(255),
    geolocation_city NVARCHAR(255), geolocation_state NVARCHAR(255));
CREATE TABLE dbo.dim_product_category (
    product_category_name NVARCHAR(255) NOT NULL PRIMARY KEY, product_category_name_english NVARCHAR(255));
CREATE TABLE dbo.dim_product (
    product_id NVARCHAR(255) NOT NULL PRIMARY KEY, product_category_name NVARCHAR(255),
    product_name_lenght INT, product_description_lenght INT, product_photos_qty INT,
    product_weight_g FLOAT, product_length_cm FLOAT, product_height_cm FLOAT, product_width_cm FLOAT);
CREATE TABLE dbo.dim_customer (
    customer_id NVARCHAR(255) NOT NULL PRIMARY KEY, customer_unique_id NVARCHAR(255), location_id INT);
CREATE TABLE dbo.dim_seller (
    seller_id NVARCHAR(255) NOT NULL PRIMARY KEY, location_id INT);
CREATE TABLE dbo.dim_review (
    review_id NVARCHAR(255) NOT NULL PRIMARY KEY, order_id NVARCHAR(255), review_score INT,
    review_comment_title NVARCHAR(255), review_comment_message NVARCHAR(1000),
    review_creation_date DATETIME, review_answer_timestamp DATETIME);
CREATE TABLE dbo.fact_order_items (
    order_id NVARCHAR(255), order_item_id INT, customer_id NVARCHAR(255),
    seller_id NVARCHAR(255), product_id NVARCHAR(255), price MONEY, freight_value MONEY);
CREATE TABLE dbo.fact_order_payment (
    order_id NVARCHAR(255), payment_sequential INT, payment_type NVARCHAR(50),
    payment_installments INT, payment_value MONEY);
CREATE TABLE dbo.fact_seller_lead (
    mql_id NVARCHAR(255), first_contact_date DATETIME, landing_page_id NVARCHAR(255),
    origin NVARCHAR(255), seller_id NVARCHAR(255), sdr_id NVARCHAR(255), sr_id NVARCHAR(255),
    won_date DATETIME, business_segment NVARCHAR(250), lead_type NVARCHAR(250),
    lead_behaviour_profile NVARCHAR(250), has_company NVARCHAR(250), has_gtin NVARCHAR(250),
    average_stock NVARCHAR(20), business_type NVARCHAR(255),
    declared_product_catalog_size FLOAT, declared_monthly_revenue FLOAT, is_won BIT);
GO
