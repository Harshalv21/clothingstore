-- Drop the database if it exists
DROP DATABASE IF EXISTS smart_dresser;

-- Create the database
CREATE DATABASE smart_dresser;

USE smart_dresser;

-- Create tables with VARCHAR IDs
CREATE TABLE seller (
    seller_id VARCHAR(20) PRIMARY KEY,
    seller_name VARCHAR(255) NOT NULL,
    seller_location VARCHAR(255),
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staff (
    staff_id VARCHAR(20) PRIMARY KEY,
    staff_name VARCHAR(255) NOT NULL,
    join_date DATE NOT NULL,
    salary DECIMAL(10,2),
    speciality VARCHAR(100),
    gender VARCHAR(10),
    comfortable_working_with VARCHAR(255),
    seller_id VARCHAR(20) NOT NULL,
    shift_timing VARCHAR(100),
    FOREIGN KEY (seller_id) REFERENCES seller(seller_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

alter table staff add column password varchar(255);

CREATE TABLE users (
    user_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    user_name VARCHAR(255) UNIQUE NOT NULL,
    gender VARCHAR(10),
    age INT,
    email VARCHAR(255) UNIQUE NOT NULL,
    contact VARCHAR(15),
    password VARCHAR(255) NOT NULL,
    comfortable_with VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    product_id VARCHAR(20) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    product_type VARCHAR(100),
    product_size VARCHAR(50),
    product_price DECIMAL(10,2) NOT NULL,
    seller_id VARCHAR(20) NOT NULL,
    brand VARCHAR(100),
    product_occasion VARCHAR(100),
    product_fit VARCHAR(100),
    image_path VARCHAR(255),
    FOREIGN KEY (seller_id) REFERENCES seller(seller_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cart (
    cart_id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    product_id VARCHAR(20) NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

CREATE TABLE orders (
    order_id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    order_date DATE NOT NULL,
    order_time TIME NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_items (
    order_item_id VARCHAR(20) PRIMARY KEY,
    order_id VARCHAR(20) NOT NULL,
    product_id VARCHAR(20) NOT NULL,
    seller_id VARCHAR(20) NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    assigned_staff VARCHAR(20),
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (seller_id) REFERENCES seller(seller_id),
    FOREIGN KEY (assigned_staff) REFERENCES staff(staff_id)
);

CREATE TABLE assignments (
    assignment_id VARCHAR(20) PRIMARY KEY,
    order_id VARCHAR(20) NOT NULL,
    order_item_id VARCHAR(20) NOT NULL,
    staff_id VARCHAR(20) NOT NULL,
    user_id VARCHAR(20) NOT NULL,
    booking_date DATE NOT NULL,
    booking_time TIME NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (order_item_id) REFERENCES order_items(order_item_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_cart_user ON cart(user_id);
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_assignments_order ON assignments(order_id);
CREATE INDEX idx_products_seller ON products(seller_id);
CREATE INDEX idx_staff_seller ON staff(seller_id);

COMMIT;

ALTER TABLE staff ADD COLUMN password VARCHAR(255) NOT NULL;

ALTER TABLE billing DROP COLUMN billing_date;

alter table billing drop column file_path;

CREATE TABLE billing (
    bill_id VARCHAR(20) PRIMARY KEY,
    order_item_id VARCHAR(20) NOT NULL,
    staff_id VARCHAR(20) NOT NULL,
    user_id VARCHAR(20) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    billing_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_item_id) REFERENCES order_items(order_item_id),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

ALTER TABLE billing ADD COLUMN billing_date DATETIME DEFAULT CURRENT_TIMESTAMP;

commit;

use smart_dresser;
SELECT image_path FROM products;

alter table products add column notes VARCHAR(255);

CREATE TABLE feedback (
    feedback_id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    order_id VARCHAR(20) NOT NULL,
    rating INT NOT NULL,
    comments TEXT,
    feedback_date DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);