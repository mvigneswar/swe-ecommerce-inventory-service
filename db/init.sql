-- ============================================================
--  E-Commerce Inventory Service — schema bootstrap
--  Auto-executed by the MySQL container on first start.
-- ============================================================

CREATE DATABASE IF NOT EXISTS ecommerce_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ecommerce_db;

-- ------------------------------------------------------------
-- products
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(255)   NOT NULL,
    description    TEXT           NULL,
    category       VARCHAR(100)   NOT NULL,
    price          DECIMAL(10,2)  NOT NULL,
    stock_quantity INT            NOT NULL DEFAULT 0,
    created_at     TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_products_price CHECK (price >= 0),
    CONSTRAINT chk_products_stock CHECK (stock_quantity >= 0),
    INDEX idx_products_category (category),
    INDEX idx_products_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- orders
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    customer_email VARCHAR(255)   NOT NULL,
    total_amount   DECIMAL(10,2)  NOT NULL,
    status         ENUM('Pending','Completed','Cancelled') NOT NULL DEFAULT 'Pending',
    created_at     TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_orders_total CHECK (total_amount >= 0),
    INDEX idx_orders_email (customer_email),
    INDEX idx_orders_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- order_items
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    order_id   INT           NOT NULL,
    product_id INT           NOT NULL,
    quantity   INT           NOT NULL,
    price      DECIMAL(10,2) NOT NULL,  -- price snapshot at purchase time
    CONSTRAINT chk_items_qty CHECK (quantity > 0),
    CONSTRAINT fk_items_order   FOREIGN KEY (order_id)   REFERENCES orders(id)   ON DELETE CASCADE,
    CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products(id),
    INDEX idx_items_order_product (order_id, product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
