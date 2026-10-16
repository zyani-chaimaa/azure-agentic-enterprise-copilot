-- Customers: one record per customer identifier.
CREATE TABLE dbo.olist_customers (
    customer_id VARCHAR(32) NOT NULL PRIMARY KEY,
    customer_unique_id VARCHAR(32) NOT NULL,
    customer_zip_code_prefix VARCHAR(10) NULL,
    customer_city NVARCHAR(150) NULL,
    customer_state VARCHAR(5) NULL
);

-- Products: product attributes and original Portuguese categories.
CREATE TABLE dbo.olist_products (
    product_id VARCHAR(32) NOT NULL PRIMARY KEY,
    product_category_name NVARCHAR(150) NULL,
    product_name_lenght INT NULL,
    product_description_lenght INT NULL,
    product_photos_qty INT NULL,
    product_weight_g FLOAT NULL,
    product_length_cm FLOAT NULL,
    product_height_cm FLOAT NULL,
    product_width_cm FLOAT NULL
);

-- Sellers: one record per seller.
CREATE TABLE dbo.olist_sellers (
    seller_id VARCHAR(32) NOT NULL PRIMARY KEY,
    seller_zip_code_prefix VARCHAR(10) NULL,
    seller_city NVARCHAR(150) NULL,
    seller_state VARCHAR(5) NULL
);

-- Orders: linked to customers.
CREATE TABLE dbo.olist_orders (
    order_id VARCHAR(32) NOT NULL PRIMARY KEY,
    customer_id VARCHAR(32) NOT NULL,
    order_status VARCHAR(30) NULL,
    order_purchase_timestamp DATETIME2 NULL,
    order_approved_at DATETIME2 NULL,
    order_delivered_carrier_date DATETIME2 NULL,
    order_delivered_customer_date DATETIME2 NULL,
    order_estimated_delivery_date DATETIME2 NULL,
    CONSTRAINT FK_olist_orders_customers
        FOREIGN KEY (customer_id) REFERENCES dbo.olist_customers(customer_id)
);

-- Order items: multiple items can belong to one order.
CREATE TABLE dbo.olist_order_items (
    order_id VARCHAR(32) NOT NULL,
    order_item_id INT NOT NULL,
    product_id VARCHAR(32) NOT NULL,
    seller_id VARCHAR(32) NOT NULL,
    shipping_limit_date DATETIME2 NULL,
    price DECIMAL(18,2) NULL,
    freight_value DECIMAL(18,2) NULL,
    CONSTRAINT PK_olist_order_items PRIMARY KEY (order_id, order_item_id),
    CONSTRAINT FK_olist_items_orders
        FOREIGN KEY (order_id) REFERENCES dbo.olist_orders(order_id),
    CONSTRAINT FK_olist_items_products
        FOREIGN KEY (product_id) REFERENCES dbo.olist_products(product_id),
    CONSTRAINT FK_olist_items_sellers
        FOREIGN KEY (seller_id) REFERENCES dbo.olist_sellers(seller_id)
);

-- Payments: an order can have multiple payments.
CREATE TABLE dbo.olist_order_payments (
    order_id VARCHAR(32) NOT NULL,
    payment_sequential INT NOT NULL,
    payment_type VARCHAR(30) NULL,
    payment_installments INT NULL,
    payment_value DECIMAL(18,2) NULL,
    CONSTRAINT PK_olist_order_payments PRIMARY KEY (order_id, payment_sequential),
    CONSTRAINT FK_olist_payments_orders
        FOREIGN KEY (order_id) REFERENCES dbo.olist_orders(order_id)
);

-- Reviews: preserve original IDs and uniquely identify each row.
CREATE TABLE dbo.olist_order_reviews (
    review_record_id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    review_id VARCHAR(32) NOT NULL,
    order_id VARCHAR(32) NOT NULL,
    review_score INT NULL,
    review_comment_title NVARCHAR(500) NULL,
    review_comment_message NVARCHAR(MAX) NULL,
    review_creation_date DATETIME2 NULL,
    review_answer_timestamp DATETIME2 NULL,
    CONSTRAINT UQ_olist_review_order UNIQUE (review_id, order_id),
    CONSTRAINT FK_olist_reviews_orders
        FOREIGN KEY (order_id) REFERENCES dbo.olist_orders(order_id)
);

-- Category translations: Portuguese-to-English reference table.
CREATE TABLE dbo.olist_category_translations (
    product_category_name NVARCHAR(150) NOT NULL PRIMARY KEY,
    product_category_name_english NVARCHAR(150) NULL
);
