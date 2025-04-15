from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import Error
import random
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'smart_dresser'
}

def create_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        gender = request.form['gender']
        age = request.form['age']
        email = request.form['email']
        contact = request.form['contact']
        password = request.form['password']
        comfortable_with = request.form['comfortable_with']
        
        user_id = f"USER{random.randint(10**12, 10**13-1)}"
        
        connection = create_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                query = """
                INSERT INTO users (user_id, name, user_name, gender, age, email, contact, password, comfortable_with)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (user_id, name, username, gender, age, email, contact, password, comfortable_with))
                connection.commit()
                flash('Signup successful! Please login.', 'success')
                return redirect(url_for('login'))
            except Error as e:
                flash(f'Error during signup: {e}', 'danger')
            finally:
                cursor.close()
                connection.close()
        else:
            flash('Database connection error', 'danger')
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        connection = create_db_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                query = "SELECT * FROM users WHERE user_name = %s AND password = %s"
                cursor.execute(query, (username, password))
                user = cursor.fetchone()
                
                if user:
                    session['user_id'] = user['user_id']
                    session['username'] = user['user_name']
                    session['comfortable_with'] = user.get('comfortable_with', '')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid username or password', 'danger')
            except Error as e:
                flash(f'Error during login: {e}', 'danger')
            finally:
                cursor.close()
                connection.close()
        else:
            flash('Database connection error', 'danger')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', username=session['username'])

@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        search_term = request.form['search_term']
        
        connection = create_db_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                query = """
                SELECT * FROM products 
                WHERE product_name LIKE %s OR brand LIKE %s OR product_occasion LIKE %s
                """
                cursor.execute(query, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
                products = cursor.fetchall()
                
                for product in products:
                    # Extract only the filename from image_path
                    product['image_filename'] = product['image_path'].replace("\\", "/").split("/")[-1]

                return render_template('results.html', products=products, search_term=search_term)
            except Error as e:
                flash(f'Error during search: {e}', 'danger')
            finally:
                cursor.close()
                connection.close()
        else:
            flash('Database connection error', 'danger')
    
    return render_template('dashboard.html')



def create_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def get_full_image_path(image_path):
    """
    Helper function to generate full image path
    If image_path is not None and not empty, join with static/uploads
    Otherwise return None
    """
    return os.path.join('static', 'uploads', image_path) if image_path else None

def assign_staff_for_order_item(cursor, seller_id, comfortable_with, booking_date, booking_time):
    """
    Assign staff based on seller, comfortable working with, and availability
    """
    # First, try to find staff matching exact comfort level and shift
    cursor.execute("""
        SELECT staff_id FROM staff 
        WHERE seller_id = %s 
        AND comfortable_working_with LIKE %s
        AND shift_timing LIKE %s
        LIMIT 1
    """, (seller_id, f"%{comfortable_with}%", f"%{booking_time}%"))
    staff = cursor.fetchone()

    # If no exact match, find staff with matching comfort level
    if not staff:
        cursor.execute("""
            SELECT staff_id FROM staff 
            WHERE seller_id = %s 
            AND comfortable_working_with LIKE %s
            LIMIT 1
        """, (seller_id, f"%{comfortable_with}%"))
        staff = cursor.fetchone()

    # If still no match, find any available staff from the seller
    if not staff:
        cursor.execute("""
            SELECT staff_id FROM staff 
            WHERE seller_id = %s 
            LIMIT 1
        """, (seller_id,))
        staff = cursor.fetchone()

    return staff['staff_id'] if staff else None

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    product_id = request.form['product_id']
    quantity = int(request.form['quantity'])
    
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get product details
            cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
            product = cursor.fetchone()
            
            if not product:
                flash('Product not found', 'danger')
                return redirect(url_for('search'))
            
            # Check if product already in cart
            cursor.execute("""
                SELECT * FROM cart 
                WHERE user_id = %s AND product_id = %s
            """, (session['user_id'], product_id))
            existing_item = cursor.fetchone()
            
            if existing_item:
                # Update quantity
                new_quantity = existing_item['quantity'] + quantity
                cursor.execute("""
                    UPDATE cart SET quantity = %s 
                    WHERE user_id = %s AND product_id = %s
                """, (new_quantity, session['user_id'], product_id))
            else:
                # Add new item to cart
                cart_id = f"CRT{random.randint(10**8, 10**9-1)}"
                cursor.execute("""
                    INSERT INTO cart (cart_id, user_id, product_id, quantity)
                    VALUES (%s, %s, %s, %s)
                """, (cart_id, session['user_id'], product_id, quantity))
            
            connection.commit()
            flash('Product added to cart successfully!', 'success')
        except Error as e:
            connection.rollback()
            flash(f'Error adding to cart: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return redirect(url_for('view_cart'))

@app.route('/cart')
def view_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get cart items with calculated totals
            cursor.execute("""
                SELECT 
                    c.cart_id,
                    c.product_id,
                    c.quantity,
                    p.product_name,
                    p.product_price,
                    p.image_path,
                    (c.quantity * p.product_price) AS item_total
                FROM cart c
                JOIN products p ON c.product_id = p.product_id
                WHERE c.user_id = %s
            """, (session['user_id'],))
            cart_items = cursor.fetchall()
            
            # Calculate total amount
            total_amount = sum(item['item_total'] for item in cart_items) if cart_items else 0
            
            # Add full image path to each item
            for item in cart_items:
                item['full_image_path'] = get_full_image_path(item['image_path'])
            
            return render_template('cart.html', cart_items=cart_items, total_amount=total_amount)
        except Error as e:
            flash(f'Error retrieving cart: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('cart.html', cart_items=[], total_amount=0)

@app.route('/remove_from_cart/<string:product_id>')
def remove_from_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("""
                DELETE FROM cart 
                WHERE user_id = %s AND product_id = %s
            """, (session['user_id'], product_id))
            connection.commit()
            flash('Item removed from cart', 'success')
        except Error as e:
            connection.rollback()
            flash(f'Error removing item: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return redirect(url_for('view_cart'))

def assign_staff_for_order_item(cursor, seller_id, comfortable_with, booking_date, booking_time):
    """
    Assign staff based on seller, comfortable working with, and availability
    with more flexible matching
    """
    print(f"Attempting to assign staff with parameters:")
    print(f"Seller ID: {seller_id}")
    print(f"Comfortable With: {comfortable_with}")
    print(f"Booking Date: {booking_date}")
    print(f"Booking Time: {booking_time}")

    # Prepare base query
    query = """
    SELECT staff_id, staff_name, seller_id, 
           comfortable_working_with, 
           shift_timing, 
           gender 
    FROM staff 
    WHERE seller_id = %s 
    """
    params = [seller_id]

    # Handle different comfortable_with scenarios
    if comfortable_with.lower() == 'any':
        # When comfortable with is 'any', don't filter by working with
        # Also, don't filter by gender
        pass
    elif comfortable_with:
        # If a specific preference is given
        query += " AND (comfortable_working_with LIKE %s OR comfortable_working_with = 'any')"
        params.append(f"%{comfortable_with}%")

    query += " LIMIT 5"  # Fetch multiple potential matches for debugging

    cursor.execute(query, params)
    potential_staff = cursor.fetchall()

    print("Potential Staff Matches:")
    for staff in potential_staff:
        print(staff)

    # Return the first staff member if any exist
    if potential_staff:
        return potential_staff[0]['staff_id']
    
    # Fallback: Find any staff for the seller if no matches
    cursor.execute("""
    SELECT staff_id 
    FROM staff 
    WHERE seller_id = %s 
    LIMIT 1
    """, (seller_id,))
    
    fallback_staff = cursor.fetchone()
    if fallback_staff:
        print(f"Using fallback staff: {fallback_staff['staff_id']}")
        return fallback_staff['staff_id']
    
    print("No staff found for assignment!")
    return None

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        booking_date = request.form['booking_date']
        booking_time = request.form['booking_time']
        
        print(f"Booking Process Started - Date: {booking_date}, Time: {booking_time}")
        print(f"User Comfortable With: {session.get('comfortable_with', 'Not specified')}")
        
        connection = create_db_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                
                # Start transaction
                connection.start_transaction()

                # 1. Get all cart items with necessary details
                cursor.execute("""
                    SELECT c.*, p.seller_id, p.product_name, p.product_price
                    FROM cart c
                    JOIN products p ON c.product_id = p.product_id
                    WHERE c.user_id = %s
                """, (session['user_id'],))
                cart_items = cursor.fetchall()

                if not cart_items:
                    flash('Your cart is empty', 'warning')
                    return redirect(url_for('view_cart'))

                # 2. Create a single order for all items
                order_id = f"ORD{random.randint(10**8, 10**9-1)}"
                total_amount = sum(item['quantity'] * item['product_price'] for item in cart_items)
                
                # Insert into orders table with correct column names
                cursor.execute("""
                    INSERT INTO orders (order_id, user_id, order_date, order_time, total_amount, status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                """, (order_id, session['user_id'], booking_date, booking_time, total_amount))

                # 3. Process each cart item
                for item in cart_items:
                    print(f"Processing Cart Item - Product: {item['product_name']}, Seller ID: {item['seller_id']}")
                    
                    # Create order item
                    order_item_id = f"ITEM{random.randint(10**8, 10**9-1)}"
                    
                    # Assign staff for this specific order item
                    assigned_staff = assign_staff_for_order_item(
                        cursor, 
                        item['seller_id'], 
                        session.get('comfortable_with', ''), 
                        booking_date, 
                        booking_time
                    )

                    print(f"Assigned Staff: {assigned_staff}")

                    cursor.execute("""
                        INSERT INTO order_items (order_item_id, order_id, product_id, seller_id, quantity, price, assigned_staff)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (order_item_id, order_id, item['product_id'], item['seller_id'], 
                          item['quantity'], item['product_price'], assigned_staff))

                    if assigned_staff:
                        # Create assignment
                        assignment_id = f"ASN{random.randint(10**8, 10**9-1)}"
                        cursor.execute("""
                            INSERT INTO assignments (
                                assignment_id, order_id, order_item_id, 
                                staff_id, user_id, booking_date, booking_time, status
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                        """, (assignment_id, order_id, order_item_id, assigned_staff,
                              session['user_id'], booking_date, booking_time))
                        print(f"Assignment Created - ID: {assignment_id}")
                    else:
                        print("No assignment created due to no staff found")

                # 4. Clear the cart
                cursor.execute("DELETE FROM cart WHERE user_id = %s", (session['user_id'],))

                # Commit transaction
                connection.commit()
                flash('Booking confirmed! Your items will be prepared for you.', 'success')
                return redirect(url_for('confirmation'))

            except Exception as e:
                connection.rollback()
                print(f"Booking Error: {str(e)}")
                flash(f'Error processing booking: {str(e)}', 'danger')
                return redirect(url_for('view_cart'))
            finally:
                if connection.is_connected():
                    cursor.close()
                    connection.close()
    
    return render_template('booking.html')
    
@app.route('/confirmation')
def confirmation():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get the most recent order for this user
    connection = create_db_connection()
    recent_order_id = None
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT order_id FROM orders 
                WHERE user_id = %s 
                ORDER BY order_date DESC, order_time DESC 
                LIMIT 1
            """, (session['user_id'],))
            recent_order = cursor.fetchone()
            if recent_order:
                recent_order_id = recent_order['order_id']
        except Error as e:
            print(f"Error fetching recent order: {e}")
        finally:
            cursor.close()
            connection.close()
    
    return render_template('confirmation.html', order_id=recent_order_id)


@app.route('/view_bills')
def view_bills():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    connection = create_db_connection()
    bills = []
    
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            query = "SELECT bill_id, amount FROM billing WHERE user_id = %s"
            cursor.execute(query, (session['user_id'],))
            bills = cursor.fetchall()
        except Error as e:
            flash(f'Error retrieving bills: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()

    return render_template('bills.html', bills=bills)


@app.route('/bill/<string:bill_id>')  # Accepting bill_id as a string
def bill_details(bill_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)

            query = """
                SELECT 
                    b.bill_id, 
                    b.amount, 
                    b.payment_method, 
                    b.billing_date, 
                    u.name AS user_name, 
                    u.contact AS user_contact, 
                    p.product_id, 
                    p.product_name, 
                    p.product_price, 
                    p.brand, 
                    s.staff_name, 
                    se.seller_name, 
                    se.seller_location
                FROM billing b
                JOIN users u ON b.user_id = u.user_id
                JOIN order_items oi ON b.order_item_id = oi.order_item_id
                JOIN products p ON oi.product_id = p.product_id
                JOIN staff s ON b.staff_id = s.staff_id
                JOIN seller se ON s.seller_id = se.seller_id
                WHERE b.bill_id = %s
            """

            cursor.execute(query, (bill_id,))
            bill = cursor.fetchone()

            if bill:
                return render_template('bill_details.html', bill=bill)
            else:
                flash('Bill not found!', 'danger')
                return redirect(url_for('view_bills'))
        except mysql.connector.Error as e:
            flash(f'Error retrieving bill: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()

    return redirect(url_for('view_bills'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    
@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'user_id' not in session:
        print("User not logged in. Redirecting to login.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        rating = request.form.get('rating')
        comments = request.form.get('comments')
        order_id = request.form.get('order_id')

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                flash('Please provide a valid rating between 1 and 5', 'danger')
                return redirect(url_for('confirmation'))
        except ValueError:
            flash('Invalid rating. Please enter a number between 1 and 5.', 'danger')
            return redirect(url_for('confirmation'))

        connection = create_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                feedback_id = f"FB{random.randint(10**8, 10**9-1)}"

                cursor.execute("""
                    INSERT INTO feedback (feedback_id, user_id, order_id, rating, comments, feedback_date)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (feedback_id, session['user_id'], order_id, rating, comments))

                connection.commit()
                flash('Thank you for your valuable feedback!', 'success')

            except Error as e:
                connection.rollback()
                flash(f'Error submitting feedback: {str(e)}', 'danger')

            finally:
                cursor.close()
                connection.close()

    print("Redirecting to dashboard...")
    return redirect(url_for('dashboard'))  # Ensure this matches your actual function name
