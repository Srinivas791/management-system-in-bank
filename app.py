import os
import random
import datetime
import csv
import io
from functools import wraps
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, Response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from database.db import db

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object(Config)
CORS(app)

# ========================================================
# Helper Functions & Decorators
# ========================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Authentication required. Please login.'}), 401
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'Authentication required.'}), 401
            if session.get('role') not in allowed_roles:
                return jsonify({'success': False, 'message': 'Access forbidden: insufficient privileges.'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def generate_account_number():
    """Generates a 10-digit bank account number starting with 1001."""
    while True:
        num = f"1001{random.randint(100000, 999999)}"
        exists = db.query_one("SELECT id FROM accounts WHERE account_number = %s", (num,))
        if not exists:
            return num

def generate_transaction_ref():
    """Generates a unique transaction reference ID."""
    timestamp = datetime.datetime.now().strftime("%y%m%d")
    rnd = random.randint(10000, 99999)
    return f"TXN-{timestamp}{rnd}"

def log_audit(action, details, user_id=None):
    uid = user_id or session.get('user_id')
    ip = request.remote_addr or '127.0.0.1'
    db.execute(
        "INSERT INTO audit_logs (user_id, action, details, ip_address) VALUES (%s, %s, %s, %s)",
        (uid, action, details, ip)
    )

# ========================================================
# Authentication Endpoints
# ========================================================

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()
    role_requested = data.get('role', '').strip().lower()

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required.'}), 400

    user = db.query_one("SELECT * FROM users WHERE LOWER(email) = %s", (email,))
    if not user:
        return jsonify({'success': False, 'message': 'Invalid credentials. User not found.'}), 401

    if user['status'] != 'active':
        return jsonify({'success': False, 'message': 'Account is suspended. Please contact bank administration.'}), 403

    if not check_password_hash(user['password_hash'], password):
        return jsonify({'success': False, 'message': 'Incorrect password entered.'}), 401

    # Optional role validation from login portal tab
    if role_requested and role_requested in ['admin', 'employee', 'customer']:
        if user['role'] != role_requested:
            return jsonify({'success': False, 'message': f"Account is not registered as '{role_requested.capitalize()}'. Your role is '{user['role'].capitalize()}'."}), 403

    session['user_id'] = user['id']
    session['full_name'] = user['full_name']
    session['email'] = user['email']
    session['role'] = user['role']

    # Fetch customer accounts if customer
    accounts = []
    customer_info = None
    if user['role'] == 'customer':
        customer_info = db.query_one("SELECT * FROM customers WHERE user_id = %s", (user['id'],))
        if customer_info:
            accounts = db.query_all("SELECT * FROM accounts WHERE customer_id = %s", (customer_info['id'],))

    log_audit('LOGIN_SUCCESS', f"User {user['email']} logged in as {user['role']}", user['id'])

    return jsonify({
        'success': True,
        'message': f"Welcome back, {user['full_name']}!",
        'user': {
            'id': user['id'],
            'full_name': user['full_name'],
            'email': user['email'],
            'phone': user['phone'],
            'role': user['role']
        },
        'customer': customer_info,
        'accounts': accounts
    })

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.get_json() or {}
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip()
    address = data.get('address', '').strip()
    city = data.get('city', '').strip()
    state = data.get('state', '').strip()
    postal_code = data.get('postal_code', '').strip()
    dob = data.get('dob', '').strip() or '2000-01-01'
    id_number = data.get('id_number', '').strip() or f"ID-{random.randint(10000, 99999)}"
    occupation = data.get('occupation', '').strip() or 'Professional'
    initial_deposit = float(data.get('initial_deposit', 1000.00))

    if not full_name or not email or not phone or not password:
        return jsonify({'success': False, 'message': 'Full name, email, phone, and password are required.'}), 400

    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters long.'}), 400

    existing_user = db.query_one("SELECT id FROM users WHERE LOWER(email) = %s", (email,))
    if existing_user:
        return jsonify({'success': False, 'message': 'Email address is already registered.'}), 409

    pwd_hash = generate_password_hash(password)
    user_id, _ = db.execute(
        "INSERT INTO users (full_name, email, phone, password_hash, role, status) VALUES (%s, %s, %s, %s, 'customer', 'active')",
        (full_name, email, phone, pwd_hash)
    )

    cust_id, _ = db.execute(
        """INSERT INTO customers (user_id, date_of_birth, address, city, state, postal_code, id_number, occupation, annual_income)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (user_id, dob, address, city, state, postal_code, id_number, occupation, 60000.00)
    )

    # Automatically generate initial Savings account
    account_number = generate_account_number()
    deposit_amount = max(500.00, initial_deposit)
    acc_id, _ = db.execute(
        "INSERT INTO accounts (customer_id, account_number, account_type, balance, status) VALUES (%s, %s, 'Savings', %s, 'active')",
        (cust_id, account_number, deposit_amount)
    )

    # Record initial deposit transaction
    ref = generate_transaction_ref()
    db.execute(
        """INSERT INTO transactions (transaction_ref, from_account_id, to_account_id, transaction_type, amount, balance_after, status, description, created_by)
           VALUES (%s, %s, NULL, 'DEPOSIT', %s, %s, 'SUCCESS', 'Account Opening Initial Deposit', %s)""",
        (ref, acc_id, deposit_amount, deposit_amount, user_id)
    )

    log_audit('CUSTOMER_REGISTERED', f"New customer {email} registered with account {account_number}", user_id)

    return jsonify({
        'success': True,
        'message': f"Registration successful! Your new Savings Account number is {account_number}.",
        'account_number': account_number,
        'initial_balance': deposit_amount
    }), 201

@app.route('/api/auth/me', methods=['GET'])
def api_me():
    if 'user_id' not in session:
        return jsonify({'authenticated': False}), 200

    user = db.query_one("SELECT id, full_name, email, phone, role, status FROM users WHERE id = %s", (session['user_id'],))
    if not user or user['status'] != 'active':
        session.clear()
        return jsonify({'authenticated': False}), 200

    customer_info = None
    accounts = []
    if user['role'] == 'customer':
        customer_info = db.query_one("SELECT * FROM customers WHERE user_id = %s", (user['id'],))
        if customer_info:
            accounts = db.query_all("SELECT * FROM accounts WHERE customer_id = %s ORDER BY id ASC", (customer_info['id'],))

    return jsonify({
        'authenticated': True,
        'user': user,
        'customer': customer_info,
        'accounts': accounts
    })

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    uid = session.get('user_id')
    if uid:
        log_audit('LOGOUT', "User logged out", uid)
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully.'})

# ========================================================
# Dashboard Metrics & Analytics
# ========================================================

@app.route('/api/dashboard/stats', methods=['GET'])
@login_required
def api_dashboard_stats():
    user_role = session.get('role')
    user_id = session.get('user_id')

    if user_role in ['admin', 'employee']:
        # Overall Bank Metrics
        cust_count = db.query_one("SELECT COUNT(*) as cnt FROM customers")['cnt']
        acc_count = db.query_one("SELECT COUNT(*) as cnt FROM accounts")['cnt']
        active_acc = db.query_one("SELECT COUNT(*) as cnt FROM accounts WHERE status = 'active'")['cnt']
        total_balance = db.query_one("SELECT COALESCE(SUM(balance), 0) as total FROM accounts")['total']
        
        deposit_stats = db.query_one("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt FROM transactions WHERE transaction_type = 'DEPOSIT' AND status = 'SUCCESS'")
        withdraw_stats = db.query_one("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt FROM transactions WHERE transaction_type = 'WITHDRAWAL' AND status = 'SUCCESS'")
        transfer_stats = db.query_one("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt FROM transactions WHERE transaction_type = 'TRANSFER' AND status = 'SUCCESS'")

        # Recent transactions with account numbers
        recent_txns = db.query_all("""
            SELECT t.*, 
                   fa.account_number as from_account_number, 
                   ta.account_number as to_account_number,
                   u.full_name as created_by_name
            FROM transactions t
            LEFT JOIN accounts fa ON t.from_account_id = fa.id
            LEFT JOIN accounts ta ON t.to_account_id = ta.id
            LEFT JOIN users u ON t.created_by = u.id
            ORDER BY t.created_at DESC LIMIT 8
        """)

        # Monthly breakdown for Chart.js
        monthly_data = db.query_all("""
            SELECT 
                SUBSTR(created_at, 1, 7) as month,
                SUM(CASE WHEN transaction_type = 'DEPOSIT' THEN amount ELSE 0 END) as deposits,
                SUM(CASE WHEN transaction_type = 'WITHDRAWAL' THEN amount ELSE 0 END) as withdrawals,
                SUM(CASE WHEN transaction_type = 'TRANSFER' THEN amount ELSE 0 END) as transfers
            FROM transactions
            WHERE status = 'SUCCESS'
            GROUP BY SUBSTR(created_at, 1, 7)
            ORDER BY month ASC LIMIT 6
        """)

        # Account type distribution
        account_dist = db.query_all("""
            SELECT account_type, COUNT(*) as count, SUM(balance) as total_balance
            FROM accounts GROUP BY account_type
        """)

        return jsonify({
            'success': True,
            'role': user_role,
            'summary': {
                'total_customers': cust_count,
                'total_accounts': acc_count,
                'active_accounts': active_acc,
                'total_liquidity': round(float(total_balance), 2),
                'total_deposits': round(float(deposit_stats['total']), 2),
                'total_withdrawals': round(float(withdraw_stats['total']), 2),
                'total_transfers': round(float(transfer_stats['total']), 2),
                'deposit_count': deposit_stats['cnt'],
                'withdrawal_count': withdraw_stats['cnt'],
                'transfer_count': transfer_stats['cnt']
            },
            'recent_transactions': recent_txns,
            'monthly_trends': monthly_data,
            'account_distribution': account_dist
        })
    else:
        # Customer personal metrics
        cust = db.query_one("SELECT * FROM customers WHERE user_id = %s", (user_id,))
        if not cust:
            return jsonify({'success': False, 'message': 'Customer record not found.'}), 404

        accounts = db.query_all("SELECT * FROM accounts WHERE customer_id = %s", (cust['id'],))
        account_ids = [str(a['id']) for a in accounts] or ['0']
        ids_str = ','.join(account_ids)

        total_cust_balance = sum(a['balance'] for a in accounts)

        cust_deposits = db.query_one(f"""
            SELECT COALESCE(SUM(amount), 0) as total FROM transactions
            WHERE from_account_id IN ({ids_str}) AND transaction_type = 'DEPOSIT' AND status = 'SUCCESS'
        """)['total']

        cust_withdrawals = db.query_one(f"""
            SELECT COALESCE(SUM(amount), 0) as total FROM transactions
            WHERE from_account_id IN ({ids_str}) AND transaction_type = 'WITHDRAWAL' AND status = 'SUCCESS'
        """)['total']

        cust_transfers_out = db.query_one(f"""
            SELECT COALESCE(SUM(amount), 0) as total FROM transactions
            WHERE from_account_id IN ({ids_str}) AND transaction_type = 'TRANSFER' AND status = 'SUCCESS'
        """)['total']

        recent_txns = db.query_all(f"""
            SELECT t.*, 
                   fa.account_number as from_account_number, 
                   ta.account_number as to_account_number
            FROM transactions t
            LEFT JOIN accounts fa ON t.from_account_id = fa.id
            LEFT JOIN accounts ta ON t.to_account_id = ta.id
            WHERE t.from_account_id IN ({ids_str}) OR t.to_account_id IN ({ids_str})
            ORDER BY t.created_at DESC LIMIT 8
        """)

        monthly_data = db.query_all(f"""
            SELECT 
                SUBSTR(created_at, 1, 7) as month,
                SUM(CASE WHEN transaction_type = 'DEPOSIT' AND from_account_id IN ({ids_str}) THEN amount ELSE 0 END) as deposits,
                SUM(CASE WHEN (transaction_type = 'WITHDRAWAL' OR (transaction_type = 'TRANSFER' AND from_account_id IN ({ids_str}))) THEN amount ELSE 0 END) as expenses
            FROM transactions
            WHERE (from_account_id IN ({ids_str}) OR to_account_id IN ({ids_str})) AND status = 'SUCCESS'
            GROUP BY SUBSTR(created_at, 1, 7)
            ORDER BY month ASC LIMIT 6
        """)

        return jsonify({
            'success': True,
            'role': 'customer',
            'summary': {
                'total_accounts': len(accounts),
                'total_balance': round(float(total_cust_balance), 2),
                'total_deposits': round(float(cust_deposits), 2),
                'total_withdrawals': round(float(cust_withdrawals), 2),
                'total_transfers': round(float(cust_transfers_out), 2)
            },
            'accounts': accounts,
            'recent_transactions': recent_txns,
            'monthly_trends': monthly_data
        })

# ========================================================
# Customer Management (CRUD + Search)
# ========================================================

@app.route('/api/customers', methods=['GET'])
@login_required
@role_required(['admin', 'employee'])
def api_get_customers():
    query_search = request.args.get('q', '').strip()
    if query_search:
        term = f"%{query_search}%"
        customers = db.query_all("""
            SELECT c.*, u.full_name, u.email, u.phone, u.status as user_status,
                   COUNT(a.id) as account_count,
                   COALESCE(SUM(a.balance), 0) as total_balance
            FROM customers c
            JOIN users u ON c.user_id = u.id
            LEFT JOIN accounts a ON c.id = a.customer_id
            WHERE u.full_name LIKE %s OR u.email LIKE %s OR u.phone LIKE %s OR c.id_number LIKE %s
            GROUP BY c.id
            ORDER BY c.id DESC
        """, (term, term, term, term))
    else:
        customers = db.query_all("""
            SELECT c.*, u.full_name, u.email, u.phone, u.status as user_status,
                   COUNT(a.id) as account_count,
                   COALESCE(SUM(a.balance), 0) as total_balance
            FROM customers c
            JOIN users u ON c.user_id = u.id
            LEFT JOIN accounts a ON c.id = a.customer_id
            GROUP BY c.id
            ORDER BY c.id DESC
        """)

    return jsonify({'success': True, 'customers': customers})

@app.route('/api/customers/<int:cust_id>', methods=['GET'])
@login_required
def api_get_customer_details(cust_id):
    # Customers can only view their own profile; admins/employees can view any
    if session.get('role') == 'customer':
        own_cust = db.query_one("SELECT id FROM customers WHERE user_id = %s", (session['user_id'],))
        if not own_cust or own_cust['id'] != cust_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    customer = db.query_one("""
        SELECT c.*, u.full_name, u.email, u.phone, u.status as user_status, u.role
        FROM customers c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = %s
    """, (cust_id,))

    if not customer:
        return jsonify({'success': False, 'message': 'Customer not found.'}), 404

    accounts = db.query_all("SELECT * FROM accounts WHERE customer_id = %s ORDER BY id ASC", (cust_id,))
    return jsonify({'success': True, 'customer': customer, 'accounts': accounts})

@app.route('/api/customers', methods=['POST'])
@login_required
@role_required(['admin', 'employee'])
def api_add_customer():
    data = request.get_json() or {}
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip() or 'Customer@123'
    address = data.get('address', '').strip()
    city = data.get('city', '').strip()
    state = data.get('state', '').strip()
    postal_code = data.get('postal_code', '').strip()
    dob = data.get('dob', '').strip() or '1995-01-01'
    id_number = data.get('id_number', '').strip()
    occupation = data.get('occupation', '').strip() or 'Salaried'
    annual_income = float(data.get('annual_income', 50000.00))
    account_type = data.get('account_type', 'Savings')
    initial_deposit = float(data.get('initial_deposit', 1000.00))

    if not full_name or not email or not phone:
        return jsonify({'success': False, 'message': 'Full name, email, and phone are required.'}), 400

    existing = db.query_one("SELECT id FROM users WHERE LOWER(email) = %s", (email,))
    if existing:
        return jsonify({'success': False, 'message': 'A user with this email already exists.'}), 409

    pwd_hash = generate_password_hash(password)
    user_id, _ = db.execute(
        "INSERT INTO users (full_name, email, phone, password_hash, role, status) VALUES (%s, %s, %s, %s, 'customer', 'active')",
        (full_name, email, phone, pwd_hash)
    )

    cust_id, _ = db.execute(
        """INSERT INTO customers (user_id, date_of_birth, address, city, state, postal_code, id_number, occupation, annual_income)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (user_id, dob, address, city, state, postal_code, id_number, occupation, annual_income)
    )

    # Automatically create initial bank account
    acc_num = generate_account_number()
    acc_id, _ = db.execute(
        "INSERT INTO accounts (customer_id, account_number, account_type, balance, status) VALUES (%s, %s, %s, %s, 'active')",
        (cust_id, acc_num, account_type, initial_deposit)
    )

    if initial_deposit > 0:
        ref = generate_transaction_ref()
        db.execute(
            """INSERT INTO transactions (transaction_ref, from_account_id, to_account_id, transaction_type, amount, balance_after, status, description, created_by)
               VALUES (%s, %s, NULL, 'DEPOSIT', %s, %s, 'SUCCESS', 'Opening Initial Deposit', %s)""",
            (ref, acc_id, initial_deposit, initial_deposit, session.get('user_id'))
        )

    log_audit('CUSTOMER_CREATED', f"Created customer {email} with account {acc_num}")

    return jsonify({
        'success': True,
        'message': f"Customer created successfully! Account Number: {acc_num}",
        'customer_id': cust_id,
        'account_number': acc_num
    }), 201

@app.route('/api/customers/<int:cust_id>', methods=['PUT'])
@login_required
@role_required(['admin', 'employee'])
def api_update_customer(cust_id):
    data = request.get_json() or {}
    cust = db.query_one("SELECT * FROM customers WHERE id = %s", (cust_id,))
    if not cust:
        return jsonify({'success': False, 'message': 'Customer record not found.'}), 404

    full_name = data.get('full_name', '').strip()
    phone = data.get('phone', '').strip()
    address = data.get('address', '').strip()
    city = data.get('city', '').strip()
    state = data.get('state', '').strip()
    postal_code = data.get('postal_code', '').strip()
    occupation = data.get('occupation', '').strip()
    annual_income = float(data.get('annual_income', cust['annual_income']))

    if full_name or phone:
        db.execute(
            "UPDATE users SET full_name = COALESCE(NULLIF(%s, ''), full_name), phone = COALESCE(NULLIF(%s, ''), phone) WHERE id = %s",
            (full_name, phone, cust['user_id'])
        )

    db.execute(
        """UPDATE customers SET address = %s, city = %s, state = %s, postal_code = %s, occupation = %s, annual_income = %s
           WHERE id = %s""",
        (address, city, state, postal_code, occupation, annual_income, cust_id)
    )

    log_audit('CUSTOMER_UPDATED', f"Updated customer record ID {cust_id}")

    return jsonify({'success': True, 'message': 'Customer details updated successfully.'})

@app.route('/api/customers/<int:cust_id>', methods=['DELETE'])
@login_required
@role_required(['admin'])
def api_delete_customer(cust_id):
    cust = db.query_one("SELECT * FROM customers WHERE id = %s", (cust_id,))
    if not cust:
        return jsonify({'success': False, 'message': 'Customer not found.'}), 404

    # Check for accounts with positive balance
    active_balance = db.query_one("SELECT COALESCE(SUM(balance), 0) as bal FROM accounts WHERE customer_id = %s", (cust_id,))
    if active_balance and active_balance['bal'] > 0:
        return jsonify({
            'success': False,
            'message': f"Cannot delete customer. Linked accounts hold active funds (${active_balance['bal']:.2f}). Please withdraw or transfer funds before closing customer record."
        }), 400

    # Soft delete / cascade delete
    db.execute("UPDATE accounts SET status = 'closed' WHERE customer_id = %s", (cust_id,))
    db.execute("UPDATE users SET status = 'inactive' WHERE id = %s", (cust['user_id'],))

    log_audit('CUSTOMER_DELETED', f"Deactivated customer ID {cust_id} and associated accounts.")

    return jsonify({'success': True, 'message': 'Customer and linked accounts successfully closed and archived.'})

# ========================================================
# Bank Account Management
# ========================================================

@app.route('/api/accounts', methods=['GET'])
@login_required
def api_get_accounts():
    user_role = session.get('role')
    user_id = session.get('user_id')
    query_search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    type_filter = request.args.get('type', '').strip()

    params = []
    where_clauses = []

    if user_role == 'customer':
        cust = db.query_one("SELECT id FROM customers WHERE user_id = %s", (user_id,))
        if not cust:
            return jsonify({'success': True, 'accounts': []})
        where_clauses.append("a.customer_id = %s")
        params.append(cust['id'])
    
    if query_search:
        where_clauses.append("(a.account_number LIKE %s OR u.full_name LIKE %s)")
        params.extend([f"%{query_search}%", f"%{query_search}%"])

    if status_filter:
        where_clauses.append("a.status = %s")
        params.append(status_filter)

    if type_filter:
        where_clauses.append("a.account_type = %s")
        params.append(type_filter)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    accounts = db.query_all(f"""
        SELECT a.*, u.full_name as customer_name, u.email as customer_email, u.phone as customer_phone
        FROM accounts a
        JOIN customers c ON a.customer_id = c.id
        JOIN users u ON c.user_id = u.id
        {where_sql}
        ORDER BY a.id DESC
    """, tuple(params))

    return jsonify({'success': True, 'accounts': accounts})

@app.route('/api/accounts', methods=['POST'])
@login_required
@role_required(['admin', 'employee'])
def api_create_account():
    data = request.get_json() or {}
    customer_id = data.get('customer_id')
    account_type = data.get('account_type', 'Savings')
    initial_deposit = float(data.get('initial_deposit', 500.00))

    if not customer_id:
        return jsonify({'success': False, 'message': 'Customer ID is required.'}), 400

    cust = db.query_one("SELECT id FROM customers WHERE id = %s", (customer_id,))
    if not cust:
        return jsonify({'success': False, 'message': 'Customer does not exist.'}), 404

    acc_num = generate_account_number()
    acc_id, _ = db.execute(
        "INSERT INTO accounts (customer_id, account_number, account_type, balance, status) VALUES (%s, %s, %s, %s, 'active')",
        (customer_id, acc_num, account_type, initial_deposit)
    )

    if initial_deposit > 0:
        ref = generate_transaction_ref()
        db.execute(
            """INSERT INTO transactions (transaction_ref, from_account_id, to_account_id, transaction_type, amount, balance_after, status, description, created_by)
               VALUES (%s, %s, NULL, 'DEPOSIT', %s, %s, 'SUCCESS', 'Account Opening Deposit', %s)""",
            (ref, acc_id, initial_deposit, initial_deposit, session.get('user_id'))
        )

    log_audit('ACCOUNT_OPENED', f"Created new {account_type} account {acc_num} for customer {customer_id}")

    return jsonify({
        'success': True,
        'message': f"Account successfully created! Account Number: {acc_num}",
        'account_number': acc_num,
        'account_id': acc_id
    }), 201

@app.route('/api/accounts/<account_number>', methods=['GET'])
@login_required
def api_get_account_by_number(account_number):
    acc = db.query_one("""
        SELECT a.*, u.full_name as customer_name, u.email as customer_email, u.phone as customer_phone
        FROM accounts a
        JOIN customers c ON a.customer_id = c.id
        JOIN users u ON c.user_id = u.id
        WHERE a.account_number = %s
    """, (account_number,))

    if not acc:
        return jsonify({'success': False, 'message': 'Bank account not found.'}), 404

    # Security check for customer
    if session.get('role') == 'customer':
        own_cust = db.query_one("SELECT id FROM customers WHERE user_id = %s", (session['user_id'],))
        if not own_cust or acc['customer_id'] != own_cust['id']:
            # Customers can only see other account's holder name for verification, not balance
            return jsonify({
                'success': True,
                'account': {
                    'account_number': acc['account_number'],
                    'customer_name': acc['customer_name'],
                    'status': acc['status']
                }
            })

    return jsonify({'success': True, 'account': acc})

@app.route('/api/accounts/<int:acc_id>/status', methods=['PATCH'])
@login_required
@role_required(['admin', 'employee'])
def api_toggle_account_status(acc_id):
    data = request.get_json() or {}
    new_status = data.get('status')

    if new_status not in ['active', 'frozen', 'closed']:
        return jsonify({'success': False, 'message': "Invalid status. Must be 'active', 'frozen', or 'closed'."}), 400

    acc = db.query_one("SELECT * FROM accounts WHERE id = %s", (acc_id,))
    if not acc:
        return jsonify({'success': False, 'message': 'Account not found.'}), 404

    db.execute("UPDATE accounts SET status = %s WHERE id = %s", (new_status, acc_id))
    log_audit('ACCOUNT_STATUS_CHANGE', f"Changed account {acc['account_number']} status to {new_status}")

    return jsonify({'success': True, 'message': f"Account status updated to '{new_status}'."})

# ========================================================
# Banking Operations (Deposit, Withdraw, Atomic Transfer)
# ========================================================

@app.route('/api/operations/deposit', methods=['POST'])
@login_required
def api_deposit():
    data = request.get_json() or {}
    acc_num = data.get('account_number', '').strip()
    try:
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid deposit amount specified.'}), 400

    description = data.get('description', '').strip() or 'Online Funds Deposit'

    if amount <= 0:
        return jsonify({'success': False, 'message': 'Deposit amount must be strictly greater than $0.00.'}), 400

    acc = db.query_one("SELECT * FROM accounts WHERE account_number = %s", (acc_num,))
    if not acc:
        return jsonify({'success': False, 'message': f"Account '{acc_num}' not found."}), 404

    if acc['status'] != 'active':
        return jsonify({'success': False, 'message': f"Account is currently {acc['status']}. Operations prohibited."}), 400

    new_balance = round(float(acc['balance']) + amount, 2)
    ref = generate_transaction_ref()

    db.execute("UPDATE accounts SET balance = %s WHERE id = %s", (new_balance, acc['id']))
    db.execute(
        """INSERT INTO transactions (transaction_ref, from_account_id, to_account_id, transaction_type, amount, balance_after, status, description, created_by)
           VALUES (%s, %s, NULL, 'DEPOSIT', %s, %s, 'SUCCESS', %s, %s)""",
        (ref, acc['id'], amount, new_balance, description, session.get('user_id'))
    )

    log_audit('DEPOSIT', f"Deposited ${amount:.2f} into account {acc_num}. Ref: {ref}")

    return jsonify({
        'success': True,
        'message': f"Successfully deposited ${amount:,.2f} into Account {acc_num}!",
        'transaction_ref': ref,
        'account_number': acc_num,
        'new_balance': new_balance
    })

@app.route('/api/operations/withdraw', methods=['POST'])
@login_required
def api_withdraw():
    data = request.get_json() or {}
    acc_num = data.get('account_number', '').strip()
    try:
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid withdrawal amount specified.'}), 400

    description = data.get('description', '').strip() or 'Cash Withdrawal'

    if amount <= 0:
        return jsonify({'success': False, 'message': 'Withdrawal amount must be strictly positive.'}), 400

    acc = db.query_one("SELECT * FROM accounts WHERE account_number = %s", (acc_num,))
    if not acc:
        return jsonify({'success': False, 'message': f"Account '{acc_num}' not found."}), 404

    # Security check: Customer can only withdraw from own accounts
    if session.get('role') == 'customer':
        cust = db.query_one("SELECT id FROM customers WHERE user_id = %s", (session['user_id'],))
        if not cust or acc['customer_id'] != cust['id']:
            return jsonify({'success': False, 'message': 'You can only withdraw funds from your own accounts.'}), 403

    if acc['status'] != 'active':
        return jsonify({'success': False, 'message': f"Account is {acc['status']}. Cannot process withdrawal."}), 400

    current_balance = float(acc['balance'])
    if current_balance < amount:
        return jsonify({
            'success': False,
            'message': f"Insufficient funds. Requested: ${amount:,.2f}, Available Balance: ${current_balance:,.2f}."
        }), 400

    new_balance = round(current_balance - amount, 2)
    ref = generate_transaction_ref()

    db.execute("UPDATE accounts SET balance = %s WHERE id = %s", (new_balance, acc['id']))
    db.execute(
        """INSERT INTO transactions (transaction_ref, from_account_id, to_account_id, transaction_type, amount, balance_after, status, description, created_by)
           VALUES (%s, %s, NULL, 'WITHDRAWAL', %s, %s, 'SUCCESS', %s, %s)""",
        (ref, acc['id'], amount, new_balance, description, session.get('user_id'))
    )

    log_audit('WITHDRAWAL', f"Withdrew ${amount:.2f} from account {acc_num}. Ref: {ref}")

    return jsonify({
        'success': True,
        'message': f"Successfully withdrew ${amount:,.2f} from Account {acc_num}!",
        'transaction_ref': ref,
        'account_number': acc_num,
        'new_balance': new_balance
    })

@app.route('/api/operations/transfer', methods=['POST'])
@login_required
def api_transfer():
    data = request.get_json() or {}
    from_acc_num = data.get('from_account', '').strip()
    to_acc_num = data.get('to_account', '').strip()
    try:
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid transfer amount entered.'}), 400

    description = data.get('description', '').strip() or 'Inter-Account Fund Transfer'

    if amount <= 0:
        return jsonify({'success': False, 'message': 'Transfer amount must be strictly greater than $0.00.'}), 400

    if from_acc_num == to_acc_num:
        return jsonify({'success': False, 'message': 'Sender and Receiver account numbers cannot be identical.'}), 400

    from_acc = db.query_one("SELECT * FROM accounts WHERE account_number = %s", (from_acc_num,))
    if not from_acc:
        return jsonify({'success': False, 'message': f"Sender account '{from_acc_num}' does not exist."}), 404

    to_acc = db.query_one("SELECT * FROM accounts WHERE account_number = %s", (to_acc_num,))
    if not to_acc:
        return jsonify({'success': False, 'message': f"Receiver account '{to_acc_num}' does not exist."}), 404

    # Authorization check for customer
    if session.get('role') == 'customer':
        cust = db.query_one("SELECT id FROM customers WHERE user_id = %s", (session['user_id'],))
        if not cust or from_acc['customer_id'] != cust['id']:
            return jsonify({'success': False, 'message': 'You may only transfer funds out of your own account.'}), 403

    if from_acc['status'] != 'active':
        return jsonify({'success': False, 'message': f"Sender account is {from_acc['status']}."}), 400

    if to_acc['status'] != 'active':
        return jsonify({'success': False, 'message': f"Receiver account is {to_acc['status']}."}), 400

    from_bal = float(from_acc['balance'])
    if from_bal < amount:
        return jsonify({
            'success': False,
            'message': f"Insufficient funds in sender account. Available: ${from_bal:,.2f}, Required: ${amount:,.2f}."
        }), 400

    # Execute Atomic Fund Transfer (Database Transaction)
    conn = db.get_connection()
    ref = generate_transaction_ref()
    new_from_bal = round(from_bal - amount, 2)
    new_to_bal = round(float(to_acc['balance']) + amount, 2)

    try:
        if db.engine_type == 'mysql':
            with conn.cursor() as cur:
                cur.execute("UPDATE accounts SET balance = %s WHERE id = %s", (new_from_bal, from_acc['id']))
                cur.execute("UPDATE accounts SET balance = %s WHERE id = %s", (new_to_bal, to_acc['id']))
                cur.execute(
                    """INSERT INTO transactions (transaction_ref, from_account_id, to_account_id, transaction_type, amount, balance_after, status, description, created_by)
                       VALUES (%s, %s, %s, 'TRANSFER', %s, %s, 'SUCCESS', %s, %s)""",
                    (ref, from_acc['id'], to_acc['id'], amount, new_from_bal, description, session.get('user_id'))
                )
            conn.commit()
        else:
            cur = conn.cursor()
            cur.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_from_bal, from_acc['id']))
            cur.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_to_bal, to_acc['id']))
            cur.execute(
                """INSERT INTO transactions (transaction_ref, from_account_id, to_account_id, transaction_type, amount, balance_after, status, description, created_by)
                   VALUES (?, ?, ?, 'TRANSFER', ?, ?, 'SUCCESS', ?, ?)""",
                (ref, from_acc['id'], to_acc['id'], amount, new_from_bal, description, session.get('user_id'))
            )
            conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f"Database transaction rollback: {str(e)}"}), 500
    finally:
        conn.close()

    log_audit('TRANSFER', f"Transferred ${amount:.2f} from {from_acc_num} to {to_acc_num}. Ref: {ref}")

    return jsonify({
        'success': True,
        'message': f"Transfer of ${amount:,.2f} to Account {to_acc_num} completed successfully!",
        'transaction_ref': ref,
        'from_account': from_acc_num,
        'to_account': to_acc_num,
        'amount': amount,
        'sender_new_balance': new_from_bal
    })

# ========================================================
# Transaction History & Statement Generation
# ========================================================

@app.route('/api/transactions', methods=['GET'])
@login_required
def api_get_transactions():
    user_role = session.get('role')
    user_id = session.get('user_id')
    txn_type = request.args.get('type', '').strip()
    acc_filter = request.args.get('account_number', '').strip()
    search = request.args.get('q', '').strip()

    params = []
    where_clauses = []

    if user_role == 'customer':
        cust = db.query_one("SELECT id FROM customers WHERE user_id = %s", (user_id,))
        if not cust:
            return jsonify({'success': True, 'transactions': []})
        cust_accs = db.query_all("SELECT id FROM accounts WHERE customer_id = %s", (cust['id'],))
        ids = [str(a['id']) for a in cust_accs] or ['0']
        where_clauses.append(f"(t.from_account_id IN ({','.join(ids)}) OR t.to_account_id IN ({','.join(ids)}))")

    if txn_type:
        where_clauses.append("t.transaction_type = %s")
        params.append(txn_type)

    if acc_filter:
        where_clauses.append("(fa.account_number = %s OR ta.account_number = %s)")
        params.extend([acc_filter, acc_filter])

    if search:
        where_clauses.append("(t.transaction_ref LIKE %s OR t.description LIKE %s OR fa.account_number LIKE %s OR ta.account_number LIKE %s)")
        term = f"%{search}%"
        params.extend([term, term, term, term])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    txns = db.query_all(f"""
        SELECT t.*,
               fa.account_number as from_account_number,
               ta.account_number as to_account_number,
               u.full_name as created_by_name
        FROM transactions t
        LEFT JOIN accounts fa ON t.from_account_id = fa.id
        LEFT JOIN accounts ta ON t.to_account_id = ta.id
        LEFT JOIN users u ON t.created_by = u.id
        {where_sql}
        ORDER BY t.created_at DESC
        LIMIT 200
    """, tuple(params))

    return jsonify({'success': True, 'transactions': txns})

@app.route('/api/statement/<account_number>', methods=['GET'])
@login_required
def api_account_statement(account_number):
    acc = db.query_one("""
        SELECT a.*, c.address, c.city, c.state, c.postal_code, c.id_number,
               u.full_name, u.email, u.phone
        FROM accounts a
        JOIN customers c ON a.customer_id = c.id
        JOIN users u ON c.user_id = u.id
        WHERE a.account_number = %s
    """, (account_number,))

    if not acc:
        return jsonify({'success': False, 'message': 'Account not found.'}), 404

    # Security check for customer
    if session.get('role') == 'customer':
        cust = db.query_one("SELECT id FROM customers WHERE user_id = %s", (session['user_id'],))
        if not cust or acc['customer_id'] != cust['id']:
            return jsonify({'success': False, 'message': 'Unauthorized access to account statement.'}), 403

    txns = db.query_all("""
        SELECT t.*,
               fa.account_number as from_account_number,
               ta.account_number as to_account_number
        FROM transactions t
        LEFT JOIN accounts fa ON t.from_account_id = fa.id
        LEFT JOIN accounts ta ON t.to_account_id = ta.id
        WHERE t.from_account_id = %s OR t.to_account_id = %s
        ORDER BY t.created_at ASC
    """, (acc['id'], acc['id']))

    return jsonify({
        'success': True,
        'account': acc,
        'transactions': txns,
        'generated_at': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/api/statement/<account_number>/download-csv', methods=['GET'])
@login_required
def api_download_statement_csv(account_number):
    acc = db.query_one("""
        SELECT a.*, u.full_name FROM accounts a
        JOIN customers c ON a.customer_id = c.id
        JOIN users u ON c.user_id = u.id
        WHERE a.account_number = %s
    """, (account_number,))

    if not acc:
        return "Account not found", 404

    if session.get('role') == 'customer':
        cust = db.query_one("SELECT id FROM customers WHERE user_id = %s", (session['user_id'],))
        if not cust or acc['customer_id'] != cust['id']:
            return "Unauthorized", 403

    txns = db.query_all("""
        SELECT t.transaction_ref, t.created_at, t.transaction_type, t.amount, t.balance_after, t.status, t.description,
               fa.account_number as from_acc, ta.account_number as to_acc
        FROM transactions t
        LEFT JOIN accounts fa ON t.from_account_id = fa.id
        LEFT JOIN accounts ta ON t.to_account_id = ta.id
        WHERE t.from_account_id = %s OR t.to_account_id = %s
        ORDER BY t.created_at DESC
    """, (acc['id'], acc['id']))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Apex Horizon National Bank - Account Statement'])
    writer.writerow(['Account Number:', acc['account_number'], 'Holder:', acc['full_name']])
    writer.writerow(['Account Type:', acc['account_type'], 'Current Balance:', f"${acc['balance']:.2f}"])
    writer.writerow(['Generated At:', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])
    writer.writerow(['Reference ID', 'Date & Time', 'Type', 'Amount ($)', 'Balance After ($)', 'From Account', 'To Account', 'Status', 'Description'])

    for t in txns:
        writer.writerow([
            t['transaction_ref'],
            t['created_at'],
            t['transaction_type'],
            f"{t['amount']:.2f}",
            f"{t['balance_after']:.2f}",
            t['from_acc'] or '-',
            t['to_acc'] or '-',
            t['status'],
            t['description'] or ''
        ])

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=Statement_{account_number}.csv"}
    )

# ========================================================
# Admin Management (Employees, Audit Logs, Reports)
# ========================================================

@app.route('/api/admin/employees', methods=['GET'])
@login_required
@role_required(['admin'])
def api_admin_employees():
    employees = db.query_all("""
        SELECT id, full_name, email, phone, role, status, created_at
        FROM users WHERE role IN ('employee', 'admin')
        ORDER BY id ASC
    """)
    return jsonify({'success': True, 'employees': employees})

@app.route('/api/admin/employees', methods=['POST'])
@login_required
@role_required(['admin'])
def api_admin_add_employee():
    data = request.get_json() or {}
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    role = data.get('role', 'employee')
    password = data.get('password', 'Employee@123').strip()

    if not full_name or not email or not phone:
        return jsonify({'success': False, 'message': 'Full name, email, and phone are required.'}), 400

    if role not in ['employee', 'admin']:
        return jsonify({'success': False, 'message': 'Invalid employee role.'}), 400

    existing = db.query_one("SELECT id FROM users WHERE LOWER(email) = %s", (email,))
    if existing:
        return jsonify({'success': False, 'message': 'User with this email already exists.'}), 409

    pwd_hash = generate_password_hash(password)
    emp_id, _ = db.execute(
        "INSERT INTO users (full_name, email, phone, password_hash, role, status) VALUES (%s, %s, %s, %s, %s, 'active')",
        (full_name, email, phone, pwd_hash, role)
    )

    log_audit('EMPLOYEE_CREATED', f"Created staff member {email} ({role})")

    return jsonify({'success': True, 'message': f"Staff member '{full_name}' added as {role.capitalize()}."}), 201

@app.route('/api/admin/users/<int:user_id>/status', methods=['PATCH'])
@login_required
@role_required(['admin'])
def api_admin_user_status(user_id):
    if user_id == session.get('user_id'):
        return jsonify({'success': False, 'message': 'You cannot deactivate your own administrative account.'}), 400

    data = request.get_json() or {}
    new_status = data.get('status')
    if new_status not in ['active', 'inactive']:
        return jsonify({'success': False, 'message': "Status must be 'active' or 'inactive'."}), 400

    db.execute("UPDATE users SET status = %s WHERE id = %s", (new_status, user_id))
    log_audit('USER_STATUS_CHANGE', f"Changed user {user_id} status to {new_status}")

    return jsonify({'success': True, 'message': f"User status set to {new_status}."})

@app.route('/api/admin/audit-logs', methods=['GET'])
@login_required
@role_required(['admin'])
def api_admin_audit_logs():
    logs = db.query_all("""
        SELECT a.*, u.full_name as user_name, u.email as user_email
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.created_at DESC
        LIMIT 100
    """)
    return jsonify({'success': True, 'audit_logs': logs})

@app.route('/api/admin/reports', methods=['GET'])
@login_required
@role_required(['admin'])
def api_admin_reports():
    top_accounts = db.query_all("""
        SELECT a.account_number, a.account_type, a.balance, u.full_name as customer_name
        FROM accounts a
        JOIN customers c ON a.customer_id = c.id
        JOIN users u ON c.user_id = u.id
        ORDER BY a.balance DESC
        LIMIT 5
    """)

    large_txns = db.query_all("""
        SELECT t.*, fa.account_number as from_acc, ta.account_number as to_acc
        FROM transactions t
        LEFT JOIN accounts fa ON t.from_account_id = fa.id
        LEFT JOIN accounts ta ON t.to_account_id = ta.id
        ORDER BY t.amount DESC
        LIMIT 5
    """)

    return jsonify({
        'success': True,
        'top_accounts': top_accounts,
        'large_transactions': large_txns
    })

# ========================================================
# Frontend Page Routes
# ========================================================

@app.route('/')
def page_index():
    return render_template('index.html')

@app.route('/login')
def page_login():
    return render_template('login.html')

@app.route('/statement')
def page_statement():
    return render_template('statement.html')

if __name__ == '__main__':
    print("[SERVER] Starting Simple Banking Management System...")
    print("[SERVER] Accessible at: http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
