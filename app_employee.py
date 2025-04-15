from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date, timedelta
import os
import random
import uuid
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

def get_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

@app.route('/')
def staff_index():
    return render_template('staff_index.html')

@app.route('/staff_login', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        staff_id = request.form['staff_id']
        password = request.form['password']
        
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                query = """
                SELECT s.*, sl.seller_name, sl.seller_location 
                FROM staff s
                JOIN seller sl ON s.seller_id = sl.seller_id
                WHERE s.staff_id = %s AND s.password = %s
                """
                cursor.execute(query, (staff_id, password))
                staff = cursor.fetchone()
                
                if staff:
                    session['staff_id'] = staff['staff_id']
                    session['staff_name'] = staff['staff_name']
                    session['seller_id'] = staff['seller_id']
                    session['seller_name'] = staff['seller_name']
                    session['seller_location'] = staff['seller_location']
                    return redirect(url_for('staff_dashboard'))
                else:
                    flash('Invalid staff ID or password', 'danger')
            except Error as e:
                print(f"Error: {e}")
                flash('Database error occurred', 'danger')
            finally:
                cursor.close()
                connection.close()
        else:
            flash('Could not connect to database', 'danger')
    
    return render_template('staff_login.html')

@app.route('/staff_dashboard')
def staff_dashboard():
    if 'staff_id' not in session:
        return redirect(url_for('staff_login'))
    
    staff_id = session['staff_id']
    today = date.today()
    
    # Initialize metrics
    metrics = {
        'pending_assignments': 0,
        'completed_today': 0,
        'total_completed': 0,
        'total_revenue': 0
    }
    
    assignments = []
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get metrics (updated to remove billing_date dependency)
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_assignments,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as total_completed,
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN b.amount ELSE 0 END), 0) as total_revenue
                FROM assignments a
                LEFT JOIN billing b ON a.order_item_id = b.order_item_id
                WHERE a.staff_id = %s
            """, (staff_id,))
            metrics = cursor.fetchone()
            
            # Get today's pending assignments
            cursor.execute("""
                SELECT a.*, u.name as user_name, p.product_name, 
                       TIME_FORMAT(a.booking_time, '%%h:%%i %%p') as formatted_time
                FROM assignments a
                JOIN users u ON a.user_id = u.user_id
                JOIN order_items oi ON a.order_item_id = oi.order_item_id
                JOIN products p ON oi.product_id = p.product_id
                WHERE a.staff_id = %s AND a.status = 'pending' AND a.booking_date = %s
                ORDER BY a.booking_time
            """, (staff_id, today))
            assignments = cursor.fetchall()
            
        except Error as e:
            print(f"Error: {e}")
            flash('Error fetching dashboard data', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('staff_dashboard.html', 
                     staff_name=session['staff_name'],
                     seller_name=session['seller_name'],
                     metrics=metrics,
                     assignments=assignments,
                     today=today)

@app.route('/staff_assignments')
def staff_assignments():
    if 'staff_id' not in session:
        return redirect(url_for('staff_login'))
    
    staff_id = session['staff_id']
    assignments = []
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get all assignments (updated to remove billing_date)
            cursor.execute("""
                SELECT a.*, u.name as user_name, p.product_name, 
                       TIME_FORMAT(a.booking_time, '%%h:%%i %%p') as formatted_time,
                       b.amount, b.payment_method
                FROM assignments a
                JOIN users u ON a.user_id = u.user_id
                JOIN order_items oi ON a.order_item_id = oi.order_item_id
                JOIN products p ON oi.product_id = p.product_id
                LEFT JOIN billing b ON a.order_item_id = b.order_item_id
                WHERE a.staff_id = %s
                ORDER BY a.booking_date DESC, a.booking_time DESC
            """, (staff_id,))
            assignments = cursor.fetchall()
            
            # Convert booking_date to date object if it's a string
            for assignment in assignments:
                if isinstance(assignment['booking_date'], str):
                    try:
                        assignment['booking_date'] = datetime.strptime(assignment['booking_date'], '%Y-%m-%d').date()
                    except ValueError:
                        try:
                            assignment['booking_date'] = datetime.strptime(assignment['booking_date'], '%Y-%m-%d %H:%M:%S').date()
                        except ValueError:
                            print(f"Could not convert date: {assignment['booking_date']}")
            
        except Error as e:
            print(f"Error: {e}")
            flash('Error fetching assignments', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('staff_assignments.html', assignments=assignments)

@app.route('/staff_assignment_details/<assignment_id>')
def staff_assignment_details(assignment_id):
    if 'staff_id' not in session:
        return redirect(url_for('staff_login'))
    
    assignment_details = None
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get assignment details (updated to remove billing_date)
            cursor.execute("""
                SELECT a.*, u.name as user_name, u.contact, u.gender,
                       p.product_name, p.product_type, p.product_size, p.product_price,
                       o.order_date, o.order_time, o.total_amount,
                       b.bill_id, b.amount, b.payment_method
                FROM assignments a
                JOIN users u ON a.user_id = u.user_id
                JOIN order_items oi ON a.order_item_id = oi.order_item_id
                JOIN products p ON oi.product_id = p.product_id
                JOIN orders o ON a.order_id = o.order_id
                LEFT JOIN billing b ON a.order_item_id = b.order_item_id
                WHERE a.assignment_id = %s AND a.staff_id = %s
            """, (assignment_id, session['staff_id']))
            assignment_details = cursor.fetchone()
            
            if not assignment_details:
                flash('Assignment not found or not authorized', 'danger')
                return redirect(url_for('staff_assignments'))
            
        except Error as e:
            print(f"Error: {e}")
            flash('Error fetching assignment details', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('staff_assignment_details.html', assignment=assignment_details)

@app.route('/staff_create_bill/<order_item_id>', methods=['GET', 'POST'])
def staff_create_bill(order_item_id):
    if 'staff_id' not in session:
        return redirect(url_for('staff_login'))

    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            payment_method = request.form['payment_method']
            notes = request.form.get('notes', '')
            
            connection = get_db_connection()
            if connection:
                cursor = connection.cursor()
                try:
                    connection.start_transaction()
                    
                    cursor.execute("""
                        SELECT a.assignment_id, o.user_id
                        FROM assignments a
                        JOIN order_items oi ON a.order_item_id = oi.order_item_id
                        JOIN orders o ON oi.order_id = o.order_id
                        WHERE a.order_item_id = %s AND a.staff_id = %s AND a.status = 'pending'
                    """, (order_item_id, session['staff_id']))
                    assignment = cursor.fetchone()
                    
                    if not assignment:
                        flash('Assignment not found or already completed', 'danger')
                        return redirect(url_for('staff_assignments'))
                    
                    bill_id = "BILL" + str(random.randint(10**8, 10**9-1))
                    
                    cursor.execute("""
                        INSERT INTO billing 
                        (bill_id, order_item_id, staff_id, user_id, amount, payment_method, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (bill_id, order_item_id, session['staff_id'], assignment[1], amount, payment_method, notes))
                    
                    cursor.execute("""
                        UPDATE assignments 
                        SET status = 'completed' 
                        WHERE order_item_id = %s AND staff_id = %s
                    """, (order_item_id, session['staff_id']))
                    
                    connection.commit()
                    flash('Bill created successfully!', 'success')
                    return redirect(url_for('staff_view_bill', bill_id=bill_id))
                    
                except Error as e:
                    connection.rollback()
                    print(f"Error: {e}")
                    flash('Error processing bill', 'danger')
                finally:
                    cursor.close()
                    connection.close()
        except ValueError:
            flash('Invalid amount', 'danger')
    
    # GET request handling
    order_details = None
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT oi.*, p.product_name, p.product_price, u.name as user_name,
                       a.booking_date, a.booking_time
                FROM order_items oi
                JOIN products p ON oi.product_id = p.product_id
                JOIN orders o ON oi.order_id = o.order_id
                JOIN users u ON o.user_id = u.user_id
                JOIN assignments a ON oi.order_item_id = a.order_item_id
                WHERE oi.order_item_id = %s AND a.staff_id = %s AND a.status = 'pending'
            """, (order_item_id, session['staff_id']))
            order_details = cursor.fetchone()
            
            if not order_details:
                flash('Order not found or already billed', 'danger')
                return redirect(url_for('staff_assignments'))
                
        except Error as e:
            print(f"Error: {e}")
            flash('Error fetching order details', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('staff_billing.html', order=order_details)

@app.route('/staff_view_bill/<bill_id>')
def staff_view_bill(bill_id):
    if 'staff_id' not in session:
        return redirect(url_for('staff_login'))
    
    connection = get_db_connection()
    bill_details = None

    if connection:
        try:
            cursor = connection.cursor(dictionary=True)

            # Fetch bill details
            cursor.execute("""
                SELECT b.*, s.staff_name, u.name AS user_name, 
                       p.product_name, p.product_price, oi.quantity,
                       (b.amount) AS total_amount,
                       sl.seller_name, sl.seller_location
                FROM billing b
                JOIN staff s ON b.staff_id = s.staff_id
                JOIN users u ON b.user_id = u.user_id
                JOIN order_items oi ON b.order_item_id = oi.order_item_id
                JOIN products p ON oi.product_id = p.product_id
                JOIN seller sl ON p.seller_id = sl.seller_id
                WHERE b.bill_id = %s AND b.staff_id = %s
            """, (bill_id, session['staff_id']))

            bill_details = cursor.fetchone()

            if not bill_details:
                flash('Bill not found or not authorized', 'danger')
                return redirect(url_for('staff_assignments'))

        except Exception as e:
            print(f"Error: {e}")
            flash('Error fetching bill details', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('staff_bill_details.html', bill=bill_details)


@app.route('/staff_schedule')
def staff_schedule():
    if 'staff_id' not in session:
        return redirect(url_for('staff_login'))
    
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    schedule = defaultdict(list)
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT a.booking_date, 
                       TIME_FORMAT(a.booking_time, '%%h:%%i %%p') as formatted_time,
                       u.name as user_name, p.product_name, a.status
                FROM assignments a
                JOIN users u ON a.user_id = u.user_id
                JOIN order_items oi ON a.order_item_id = oi.order_item_id
                JOIN products p ON oi.product_id = p.product_id
                WHERE a.staff_id = %s 
                AND a.booking_date BETWEEN %s AND %s
                ORDER BY a.booking_date, a.booking_time
            """, (session['staff_id'], start_of_week, end_of_week))
            
            for appointment in cursor:
                schedule[appointment['booking_date']].append(appointment)
                
        except Error as e:
            print(f"Error: {e}")
            flash('Error fetching schedule', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    week_days = [start_of_week + timedelta(days=i) for i in range(7)]
    
    return render_template('staff_schedule.html', 
                         schedule=schedule,
                         week_days=week_days,
                         today=today)

@app.route('/staff_profile', methods=['GET', 'POST'])
def staff_profile():
    if 'staff_id' not in session:
        return redirect(url_for('staff_login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection error', 'danger')
        return redirect(url_for('staff_dashboard'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.*, sl.seller_name 
            FROM staff s
            JOIN seller sl ON s.seller_id = sl.seller_id
            WHERE s.staff_id = %s
        """, (session['staff_id'],))
        staff = cursor.fetchone()
        
        if not staff:
            flash('Staff not found', 'danger')
            return redirect(url_for('staff_dashboard'))
        
        if request.method == 'POST':
            update_data = {
                'staff_id': session['staff_id'],
                'staff_name': request.form['staff_name'],
                'gender': request.form['gender'],
                'shift_timing': request.form['shift_timing'],
                'comfortable_working_with': request.form['comfortable_working_with'],
                'password': request.form['password']
            }
            
            try:
                cursor.execute("""
                    UPDATE staff 
                    SET staff_name = %(staff_name)s,
                        gender = %(gender)s,
                        shift_timing = %(shift_timing)s,
                        comfortable_working_with = %(comfortable_working_with)s,
                        password = %(password)s
                    WHERE staff_id = %(staff_id)s
                """, update_data)
                connection.commit()
                session['staff_name'] = update_data['staff_name']
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('staff_profile'))
            except Error as e:
                connection.rollback()
                flash(f'Error updating profile: {e}', 'danger')
        
        return render_template('staff_profile.html', staff=staff)
        
    except Error as e:
        flash(f'Error retrieving profile: {e}', 'danger')
    finally:
        cursor.close()
        connection.close()
    
    return redirect(url_for('staff_dashboard'))

@app.route('/staff_logout')
def staff_logout():
    session.clear()
    return redirect(url_for('staff_index'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5002, debug=True)