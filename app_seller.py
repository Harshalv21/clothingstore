from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import Error
import random
from datetime import datetime, date, time, timedelta
import os
from werkzeug.utils import secure_filename
import uuid

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

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def generate_unique_filename(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    return f"{uuid.uuid4().hex}.{ext}"

@app.route('/')
def seller_index():
    return render_template('seller_index.html')

@app.route('/seller_signup', methods=['GET', 'POST'])
def seller_signup():
    if request.method == 'POST':
        seller_name = request.form['seller_name']
        seller_location = request.form['seller_location']
        email = request.form['email']
        password = request.form['password']
        
        seller_id = "SELR" + str(random.randint(10**10, 10**11-1))
        
        connection = create_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute("""
                    INSERT INTO seller (seller_id, seller_name, seller_location, email, password)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (seller_id, seller_name, seller_location, email, password))
                connection.commit()
                flash('Seller registration successful! Please login.', 'success')
                return redirect(url_for('seller_login'))
            except Error as e:
                flash(f'Error during registration: {e}', 'danger')
            finally:
                cursor.close()
                connection.close()
        else:
            flash('Database connection error', 'danger')
    
    return render_template('seller_signup.html')

@app.route('/seller_login', methods=['GET', 'POST'])
def seller_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        connection = create_db_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT * FROM seller WHERE email = %s AND password = %s", (email, password))
                seller = cursor.fetchone()
                
                if seller:
                    session['seller_id'] = seller['seller_id']
                    session['seller_name'] = seller['seller_name']
                    return redirect(url_for('seller_dashboard'))
                else:
                    flash('Invalid email or password', 'danger')
            except Error as e:
                flash(f'Error during login: {e}', 'danger')
            finally:
                cursor.close()
                connection.close()
        else:
            flash('Database connection error', 'danger')
    
    return render_template('seller_login.html')

from datetime import datetime

@app.route('/seller_dashboard')
def seller_dashboard():
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get today's date
            today = datetime.today().date()
            
            # Get today's appointments
            cursor.execute("""
                SELECT a.assignment_id, a.booking_date, 
                       TIME_FORMAT(a.booking_time, '%%h:%%i %%p') as formatted_time,
                       u.name as user_name, p.product_name, s.staff_name, a.status
                FROM assignments a
                JOIN order_items oi ON a.order_item_id = oi.order_item_id
                JOIN products p ON oi.product_id = p.product_id
                JOIN users u ON a.user_id = u.user_id
                JOIN staff s ON a.staff_id = s.staff_id
                WHERE p.seller_id = %s AND a.booking_date = CURDATE()
                ORDER BY a.booking_date, a.booking_time
                """, (session['seller_id'],))
            appointments = cursor.fetchall()
            
            # Get upcoming appointments (next 7 days)
            cursor.execute("""
                SELECT a.assignment_id, a.booking_date, 
                       TIME_FORMAT(a.booking_time, '%%h:%%i %%p') as formatted_time,
                       u.name as user_name, p.product_name, s.staff_name, a.status
                FROM assignments a
                JOIN order_items oi ON a.order_item_id = oi.order_item_id
                JOIN products p ON oi.product_id = p.product_id
                JOIN users u ON a.user_id = u.user_id
                JOIN staff s ON a.staff_id = s.staff_id
                WHERE p.seller_id = %s AND a.booking_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
                ORDER BY a.booking_date, a.booking_time
                """, (session['seller_id'],))
            upcoming_appointments = cursor.fetchall()
            
            # Get product count
            cursor.execute("SELECT COUNT(*) as product_count FROM products WHERE seller_id = %s", (session['seller_id'],))
            product_count = cursor.fetchone()['product_count']
            
            # Get staff count
            cursor.execute("SELECT COUNT(*) as staff_count FROM staff WHERE seller_id = %s", (session['seller_id'],))
            staff_count = cursor.fetchone()['staff_count']
            
            # Get revenue data
            cursor.execute("""
                SELECT SUM(oi.price * oi.quantity) as total_revenue
                FROM order_items oi
                JOIN products p ON oi.product_id = p.product_id
                WHERE p.seller_id = %s
                """, (session['seller_id'],))
            revenue_data = cursor.fetchone()
            total_revenue = revenue_data['total_revenue'] if revenue_data['total_revenue'] else 0
            
            # Get recent orders
            cursor.execute("""
                SELECT o.order_id, o.order_date, u.name as user_name, 
                       COUNT(oi.order_item_id) as item_count, o.total_amount
                FROM orders o
                JOIN users u ON o.user_id = u.user_id
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN products p ON oi.product_id = p.product_id
                WHERE p.seller_id = %s
                GROUP BY o.order_id
                ORDER BY o.order_date DESC
                LIMIT 5
                """, (session['seller_id'],))
            recent_orders = cursor.fetchall()
            
            return render_template('seller_dashboard.html',
                                seller_name=session['seller_name'],
                                today=today,  # Pass the today variable to the template
                                appointments=appointments,
                                upcoming_appointments=upcoming_appointments,
                                product_count=product_count,
                                staff_count=staff_count,
                                total_revenue=total_revenue,
                                recent_orders=recent_orders)
        except Error as e:
            flash(f'Error retrieving dashboard data: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('seller_dashboard.html', seller_name=session['seller_name'])

@app.route('/seller_add_product', methods=['GET', 'POST'])
def seller_add_product():
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    if request.method == 'POST':
        product_data = {
            'product_name': request.form['product_name'],
            'product_type': request.form['product_type'],
            'product_size': request.form['product_size'],
            'product_price': float(request.form['product_price']),
            'brand': request.form['brand'],
            'product_occasion': request.form['product_occasion'],
            'product_fit': request.form['product_fit'],
            'seller_id': session['seller_id']
        }
        
        file = request.files['product_image']
        if not file or file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = generate_unique_filename(secure_filename(file.filename))
            
            # Ensure the upload directory exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            # Save the file to static/uploads
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Generate product ID
            product_id = "PROD" + str(random.randint(10**4, 10**5-1))
            product_data['product_id'] = product_id
            
            # Store relative path for database (static/uploads/filename)
            product_data['image_path'] = os.path.join('uploads', filename)
            
            connection = create_db_connection()
            if connection:
                try:
                    cursor = connection.cursor()
                    cursor.execute("""
                        INSERT INTO products 
                        (product_id, product_name, product_type, product_size, 
                         product_price, seller_id, brand, product_occasion, 
                         product_fit, image_path)
                        VALUES (%(product_id)s, %(product_name)s, %(product_type)s, 
                                %(product_size)s, %(product_price)s, %(seller_id)s, 
                                %(brand)s, %(product_occasion)s, %(product_fit)s, 
                                %(image_path)s)
                        """, product_data)
                    connection.commit()
                    flash('Product added successfully!', 'success')
                    return redirect(url_for('seller_view_products'))
                except Error as e:
                    connection.rollback()
                    # Clean up the uploaded file if DB operation failed
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    flash(f'Error adding product: {e}', 'danger')
                finally:
                    cursor.close()
                    connection.close()
        else:
            flash('Allowed file types: png, jpg, jpeg, gif', 'danger')
    
    return render_template('seller_add_product.html')

@app.route('/seller_edit_product/<product_id>', methods=['GET', 'POST'])
def seller_edit_product(product_id):
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    connection = create_db_connection()
    if not connection:
        flash('Database connection error', 'danger')
        return redirect(url_for('seller_view_products'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get the current product data
        cursor.execute("""
            SELECT * FROM products 
            WHERE product_id = %s AND seller_id = %s
            """, (product_id, session['seller_id']))
        product = cursor.fetchone()
        
        if not product:
            flash('Product not found or not authorized', 'danger')
            return redirect(url_for('seller_view_products'))
        
        if request.method == 'POST':
            # Update product data
            update_data = {
                'product_id': product_id,
                'product_name': request.form['product_name'],
                'product_type': request.form['product_type'],
                'product_size': request.form['product_size'],
                'product_price': float(request.form['product_price']),
                'brand': request.form['brand'],
                'product_occasion': request.form['product_occasion'],
                'product_fit': request.form['product_fit'],
                'seller_id': session['seller_id'],
                'notes': request.form['notes']
            }
            
            file = request.files['product_image']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    # Generate new filename
                    filename = generate_unique_filename(secure_filename(file.filename))
                    
                    # Ensure the upload directory exists
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    
                    # Save the new file
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    
                    # Delete the old image file if it exists
                    if product['image_path']:
                        old_filepath = os.path.join('static', product['image_path'])
                        if os.path.exists(old_filepath):
                            os.remove(old_filepath)
                    
                    # Update the image path
                    update_data['image_path'] = os.path.join('uploads', filename)
                else:
                    flash('Allowed file types: png, jpg, jpeg, gif', 'danger')
                    return redirect(request.url)
            else:
                # Keep the existing image path if no new file was uploaded
                update_data['image_path'] = product['image_path']
            
            try:
                cursor.execute("""
                    UPDATE products 
                    SET product_name = %(product_name)s,
                        product_type = %(product_type)s,
                        product_size = %(product_size)s,
                        product_price = %(product_price)s,
                        brand = %(brand)s,
                        product_occasion = %(product_occasion)s,
                        product_fit = %(product_fit)s,
                        image_path = %(image_path)s
                    WHERE product_id = %(product_id)s AND seller_id = %(seller_id)s
                    """, update_data)
                connection.commit()
                flash('Product updated successfully!', 'success')
                return redirect(url_for('seller_view_products'))
            except Error as e:
                connection.rollback()
                flash(f'Error updating product: {e}', 'danger')
        
        # Add full image path for display in template
        if product['image_path']:
            product['full_image_path'] = os.path.join('static', product['image_path'])
        else:
            product['full_image_path'] = None
            
        return render_template('seller_edit_product.html', product=product)
        
    except Error as e:
        flash(f'Error retrieving product: {e}', 'danger')
    finally:
        cursor.close()
        connection.close()
    
    return redirect(url_for('seller_view_products'))

@app.route('/seller_delete_product/<product_id>', methods=['POST'])
def seller_delete_product(product_id):
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    connection = create_db_connection()
    if not connection:
        flash('Database connection error', 'danger')
        return redirect(url_for('seller_view_products'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # First get the product to delete its image file
        cursor.execute("""
            SELECT image_path FROM products 
            WHERE product_id = %s AND seller_id = %s
            """, (product_id, session['seller_id']))
        product = cursor.fetchone()
        
        if not product:
            flash('Product not found or not authorized', 'danger')
            return redirect(url_for('seller_view_products'))
        
        # Delete the product from database
        cursor.execute("""
            DELETE FROM products 
            WHERE product_id = %s AND seller_id = %s
            """, (product_id, session['seller_id']))
        connection.commit()
        
        # Delete the associated image file if it exists
        if product['image_path']:
            filepath = os.path.join('static', product['image_path'])
            if os.path.exists(filepath):
                os.remove(filepath)
        
        flash('Product deleted successfully!', 'success')
    except Error as e:
        connection.rollback()
        flash(f'Error deleting product: {e}', 'danger')
    finally:
        cursor.close()
        connection.close()
    
    return redirect(url_for('seller_view_products'))

@app.route('/seller_add_staff', methods=['GET', 'POST'])
def seller_add_staff():
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    if request.method == 'POST':
        staff_id = "STAFF" + str(random.randint(10**8, 10**9-1))
        password = request.form['password']
        
        staff_data = {
            'staff_id': staff_id,
            'staff_name': request.form['staff_name'],
            'salary': float(request.form['salary']),
            'speciality': request.form['speciality'],
            'gender': request.form['gender'],
            'comfortable_working_with': request.form['comfortable_working_with'],
            'seller_id': session['seller_id'],
            'shift_timing': request.form['shift_timing'],
            'password': password
        }
        
        connection = create_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute("""
                    INSERT INTO staff 
                    (staff_id, staff_name, join_date, salary, speciality, 
                     gender, comfortable_working_with, seller_id, shift_timing, password)
                    VALUES (%(staff_id)s, %(staff_name)s, CURDATE(), %(salary)s, 
                            %(speciality)s, %(gender)s, %(comfortable_working_with)s, 
                            %(seller_id)s, %(shift_timing)s, %(password)s)
                    """, staff_data)
                connection.commit()
                flash('Staff member added successfully!', 'success')
                return redirect(url_for('seller_view_staff'))
            except Error as e:
                connection.rollback()
                flash(f'Error adding staff: {e}', 'danger')
            finally:
                cursor.close()
                connection.close()
    
    return render_template('seller_add_staff.html')

@app.route('/seller_edit_staff/<staff_id>', methods=['GET', 'POST'])
def seller_edit_staff(staff_id):
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    connection = create_db_connection()
    if not connection:
        flash('Database connection error', 'danger')
        return redirect(url_for('seller_view_staff'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get the current staff data
        cursor.execute("""
            SELECT * FROM staff 
            WHERE staff_id = %s AND seller_id = %s
            """, (staff_id, session['seller_id']))
        staff = cursor.fetchone()
        
        if not staff:
            flash('Staff member not found or not authorized', 'danger')
            return redirect(url_for('seller_view_staff'))
        
        if request.method == 'POST':
            # Update staff data
            update_data = {
                'staff_id': staff_id,
                'staff_name': request.form['staff_name'],
                'salary': float(request.form['salary']),
                'speciality': request.form['speciality'],
                'gender': request.form['gender'],
                'comfortable_working_with': request.form['comfortable_working_with'],
                'shift_timing': request.form['shift_timing'],
                'password': request.form['password'],
                'seller_id': session['seller_id']
            }
            
            try:
                cursor.execute("""
                    UPDATE staff 
                    SET staff_name = %(staff_name)s,
                        salary = %(salary)s,
                        speciality = %(speciality)s,
                        gender = %(gender)s,
                        comfortable_working_with = %(comfortable_working_with)s,
                        shift_timing = %(shift_timing)s,
                        password = %(password)s
                    WHERE staff_id = %(staff_id)s AND seller_id = %(seller_id)s
                    """, update_data)
                connection.commit()
                flash('Staff member updated successfully!', 'success')
                return redirect(url_for('seller_view_staff'))
            except Error as e:
                connection.rollback()
                flash(f'Error updating staff: {e}', 'danger')
        
        return render_template('seller_edit_staff.html', staff=staff)
        
    except Error as e:
        flash(f'Error retrieving staff: {e}', 'danger')
    finally:
        cursor.close()
        connection.close()
    
    return redirect(url_for('seller_view_staff'))

@app.route('/seller_delete_staff/<staff_id>', methods=['POST'])
def seller_delete_staff(staff_id):
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    connection = create_db_connection()
    if not connection:
        flash('Database connection error', 'danger')
        return redirect(url_for('seller_view_staff'))
    
    try:
        cursor = connection.cursor()
        
        # Check if staff has any assignments
        cursor.execute("""
            SELECT COUNT(*) as assignment_count 
            FROM assignments 
            WHERE staff_id = %s
            """, (staff_id,))
        result = cursor.fetchone()
        
        if result['assignment_count'] > 0:
            flash('Cannot delete staff member with active assignments', 'danger')
            return redirect(url_for('seller_view_staff'))
        
        # Delete the staff member
        cursor.execute("""
            DELETE FROM staff 
            WHERE staff_id = %s AND seller_id = %s
            """, (staff_id, session['seller_id']))
        connection.commit()
        
        flash('Staff member deleted successfully!', 'success')
    except Error as e:
        connection.rollback()
        flash(f'Error deleting staff: {e}', 'danger')
    finally:
        cursor.close()
        connection.close()
    
    return redirect(url_for('seller_view_staff'))

@app.route('/seller_view_products')
def seller_view_products():
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM products 
                WHERE seller_id = %s
                ORDER BY created_at DESC
                """, (session['seller_id'],))
            products = cursor.fetchall()
            
            # Add full image path to each product
            for product in products:
                if product['image_path']:
                    product['full_image_path'] = os.path.join('static', product['image_path'])
                else:
                    product['full_image_path'] = None
            
            return render_template('seller_view_products.html', products=products)
        except Error as e:
            flash(f'Error retrieving products: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('seller_view_products.html', products=[])

@app.route('/seller_view_staff')
def seller_view_staff():
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM staff 
                WHERE seller_id = %s
                ORDER BY join_date DESC
                """, (session['seller_id'],))
            staff_members = cursor.fetchall()
            
            return render_template('seller_view_staff.html', staff_members=staff_members)
        except Error as e:
            flash(f'Error retrieving staff: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('seller_view_staff.html', staff_members=[])

@app.route('/seller_view_orders')
def seller_view_orders():
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT o.order_id, o.order_date, o.total_amount, 
                       u.name as user_name, COUNT(oi.order_item_id) as item_count,
                       o.status as order_status
                FROM orders o
                JOIN users u ON o.user_id = u.user_id
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN products p ON oi.product_id = p.product_id
                WHERE p.seller_id = %s
                GROUP BY o.order_id
                ORDER BY o.order_date DESC
                """, (session['seller_id'],))
            orders = cursor.fetchall()
            
            return render_template('seller_view_orders.html', orders=orders)
        except Error as e:
            flash(f'Error retrieving orders: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('seller_view_orders.html', orders=[])

@app.route('/seller_order_details/<order_id>')
def seller_order_details(order_id):
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get order header
            cursor.execute("""
                SELECT o.*, u.name as user_name, u.contact as user_contact
                FROM orders o
                JOIN users u ON o.user_id = u.user_id
                WHERE o.order_id = %s
                """, (order_id,))
            order = cursor.fetchone()
            
            if not order:
                flash('Order not found', 'danger')
                return redirect(url_for('seller_view_orders'))
            
            # Get order items
            cursor.execute("""
                SELECT oi.*, p.product_name, p.product_price, p.image_path,
                       s.staff_name, a.booking_date, a.booking_time, a.status as appointment_status
                FROM order_items oi
                JOIN products p ON oi.product_id = p.product_id
                LEFT JOIN assignments a ON oi.order_item_id = a.order_item_id
                LEFT JOIN staff s ON a.staff_id = s.staff_id
                WHERE oi.order_id = %s AND p.seller_id = %s
                """, (order_id, session['seller_id']))
            items = cursor.fetchall()
            
            # Add full image path to each item
            for item in items:
                if item['image_path']:
                    item['full_image_path'] = os.path.join('static', item['image_path'])
                else:
                    item['full_image_path'] = None
            
            return render_template('seller_order_details.html', order=order, items=items)
        except Error as e:
            flash(f'Error retrieving order details: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return redirect(url_for('seller_view_orders'))

@app.route('/seller_view_appointments')
def seller_view_appointments():
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get all appointments (past and future)
            cursor.execute("""
                SELECT a.assignment_id, a.booking_date, 
                       TIME_FORMAT(a.booking_time, '%%h:%%i %%p') as formatted_time,
                       u.name as user_name, u.contact as user_contact,
                       p.product_name, s.staff_name, a.status
                FROM assignments a
                JOIN order_items oi ON a.order_item_id = oi.order_item_id
                JOIN products p ON oi.product_id = p.product_id
                JOIN users u ON a.user_id = u.user_id
                JOIN staff s ON a.staff_id = s.staff_id
                WHERE p.seller_id = %s
                ORDER BY a.booking_date DESC, a.booking_time DESC
                """, (session['seller_id'],))
            appointments = cursor.fetchall()
            
            return render_template('seller_view_appointments.html', appointments=appointments)
        except Error as e:
            flash(f'Error retrieving appointments: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('seller_view_appointments.html', appointments=[])

@app.route('/seller_update_appointment_status/<assignment_id>', methods=['POST'])
def seller_update_appointment_status(assignment_id):
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    new_status = request.form['status']
    
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            # Verify the assignment belongs to the seller
            cursor.execute("""
                SELECT a.assignment_id
                FROM assignments a
                JOIN order_items oi ON a.order_item_id = oi.order_item_id
                JOIN products p ON oi.product_id = p.product_id
                WHERE a.assignment_id = %s AND p.seller_id = %s
                """, (assignment_id, session['seller_id']))
            assignment = cursor.fetchone()
            
            if not assignment:
                flash('Appointment not found or not authorized', 'danger')
                return redirect(url_for('seller_view_appointments'))
            
            # Update the status
            cursor.execute("""
                UPDATE assignments
                SET status = %s
                WHERE assignment_id = %s
                """, (new_status, assignment_id))
            connection.commit()
            
            flash('Appointment status updated successfully!', 'success')
        except Error as e:
            connection.rollback()
            flash(f'Error updating appointment status: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return redirect(url_for('seller_view_appointments'))

@app.route('/seller_view_reports')
def seller_view_reports():
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get sales report (last 30 days)
            cursor.execute("""
                SELECT DATE(o.order_date) as order_day, 
                       COUNT(DISTINCT o.order_id) as order_count,
                       SUM(oi.price * oi.quantity) as daily_revenue
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN products p ON oi.product_id = p.product_id
                WHERE p.seller_id = %s AND o.order_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                GROUP BY DATE(o.order_date)
                ORDER BY DATE(o.order_date) DESC
                """, (session['seller_id'],))
            sales_report = cursor.fetchall()
            
            # Get top products
            cursor.execute("""
                SELECT p.product_id, p.product_name, 
                       SUM(oi.quantity) as total_quantity,
                       SUM(oi.price * oi.quantity) as total_revenue
                FROM products p
                JOIN order_items oi ON p.product_id = oi.product_id
                WHERE p.seller_id = %s
                GROUP BY p.product_id
                ORDER BY total_revenue DESC
                LIMIT 5
                """, (session['seller_id'],))
            top_products = cursor.fetchall()
            
            # Get staff performance
            cursor.execute("""
                SELECT s.staff_id, s.staff_name, 
                       COUNT(a.assignment_id) as completed_assignments,
                       COUNT(DISTINCT oi.order_id) as orders_handled
                FROM staff s
                LEFT JOIN assignments a ON s.staff_id = a.staff_id AND a.status = 'completed'
                LEFT JOIN order_items oi ON a.order_item_id = oi.order_item_id
                WHERE s.seller_id = %s
                GROUP BY s.staff_id
                ORDER BY completed_assignments DESC
                """, (session['seller_id'],))
            staff_performance = cursor.fetchall()
            
            return render_template('seller_view_reports.html',
                                sales_report=sales_report,
                                top_products=top_products,
                                staff_performance=staff_performance)
        except Error as e:
            flash(f'Error generating reports: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('seller_view_reports.html')

@app.route('/seller_profile', methods=['GET', 'POST'])
def seller_profile():
    if 'seller_id' not in session:
        return redirect(url_for('seller_login'))
    
    connection = create_db_connection()
    if not connection:
        flash('Database connection error', 'danger')
        return redirect(url_for('seller_dashboard'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get current seller data
        cursor.execute("""
            SELECT * FROM seller 
            WHERE seller_id = %s
            """, (session['seller_id'],))
        seller = cursor.fetchone()
        
        if not seller:
            flash('Seller not found', 'danger')
            return redirect(url_for('seller_dashboard'))
        
        if request.method == 'POST':
            # Update seller data
            update_data = {
                'seller_id': session['seller_id'],
                'seller_name': request.form['seller_name'],
                'seller_location': request.form['seller_location'],
                'email': request.form['email'],
                'password': request.form['password']
            }
            
            try:
                cursor.execute("""
                    UPDATE seller 
                    SET seller_name = %(seller_name)s,
                        seller_location = %(seller_location)s,
                        email = %(email)s,
                        password = %(password)s
                    WHERE seller_id = %(seller_id)s
                    """, update_data)
                connection.commit()
                
                # Update session data
                session['seller_name'] = update_data['seller_name']
                
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('seller_profile'))
            except Error as e:
                connection.rollback()
                flash(f'Error updating profile: {e}', 'danger')
        
        return render_template('seller_profile.html', seller=seller)
        
    except Error as e:
        flash(f'Error retrieving profile: {e}', 'danger')
    finally:
        cursor.close()
        connection.close()
    
    return redirect(url_for('seller_dashboard'))

@app.route('/seller_logout')
def seller_logout():
    session.clear()
    return redirect(url_for('seller_index'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5001, debug=True)