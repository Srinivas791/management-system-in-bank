# Simple Banking Management System
> **Academic B.Tech Software Engineering Project**  
> *A professional, modern, full-stack responsive web-based Banking Management System with Role-Based Access Control (RBAC), atomic fund transfers, Chart.js financial analytics, and official statement generation.*

---

## 🏛️ Project Overview
**Simple Banking Management System** is an enterprise-grade academic demonstration prototype built to model modern retail and commercial banking workflows. Designed with a clean dark-navy & royal-blue theme, this application supports three distinct user roles (**Admin**, **Employee**, **Customer**), enforces strict database transaction atomicity for fund transfers, and includes complete audit logging, customer KYC tracking, and account statement generation.

---

## 🚀 Key Features

### 1. Modern Banking UI/UX
- Responsive dashboard optimized for desktop, tablet, and mobile browsers.
- Navy & royal-blue color scheme with micro-interactions, subtle glassmorphism, and badge status pills.
- Interactive **Chart.js** visualizations for monthly transaction trends and account distribution.
- Interactive modal dialogs for customer management, account creation, and statement previews.

### 2. Role-Based Access Control (RBAC)
- **Customer Portal**: View personal accounts, live balances, deposit funds, withdraw funds, execute inter-account fund transfers, inspect personal ledger, and download/print official e-statements.
- **Employee Portal**: Manage customer records, view KYC details, open new savings/current accounts, execute counter transactions, freeze/unfreeze accounts.
- **Admin Portal**: System-wide oversight, manage banking personnel (add staff, assign roles, toggle access), monitor real-time security audit logs, review large-value transaction reports and top-capital accounts.

### 3. Core Banking Operations
- **Deposit**: Select target account, enter amount with quick-selection chips (+\$100, +\$500, +\$1,000, +\$5,000), update balances atomically, and record audit trail.
- **Withdrawal**: Validates active account status, verifies available balance, rejects insufficient-balance requests with clean error feedback.
- **Inter-Account Fund Transfer**: Real-time beneficiary account verification, self-transfer guard, atomic balance adjustment (debits sender, credits receiver within a single database transaction), and double-entry transaction referencing.

### 4. Statements & Reporting
- Comprehensive transaction history filterable by transaction type, account number, or keyword.
- **Printable Bank Statement**: Formatted as an official bank e-statement with institution header, customer KYC info, debit/credit ledger, and print dialog trigger (`window.print()`).
- **CSV Ledger Export**: Instant Excel-compatible spreadsheet download.

---

## 👥 Demo Credentials

For quick academic demonstration and viva presentations, one-click demo autofill buttons are provided on the login page:

| Role | Email | Password | Permissions |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@bank.com` | `Admin@123` | Full system access, staff management, audit logs, reports |
| **Employee** | `employee@bank.com` | `Employee@123` | Customer onboarding, account opening, counter operations |
| **Customer 1** | `john.doe@gmail.com` | `Customer@123` | Savings Account (1001002345) &bull; Balance: \$14,650+ |
| **Customer 2** | `jane.smith@gmail.com` | `Customer@123` | Current Account (1001005678) &bull; Balance: \$8,920+ |
| **Customer 3** | `robert.chen@gmail.com` | `Customer@123` | Savings Account (1001009012) &bull; Balance: \$25,100+ |

---

## 🛠️ Technology Stack
- **Frontend**: HTML5, CSS3 (Modern Flexbox & CSS Grid, responsive design), Vanilla JavaScript (Modular ES6), Chart.js.
- **Backend**: Python Flask REST API, Flask-CORS, Werkzeug Security (pbkdf2:sha256 password hashing).
- **Database**:
  - **MySQL**: Native support via PyMySQL. Complete SQL scripts provided in `database/mysql_schema.sql` and `database/seed_data.sql`.
  - **Embedded SQLite Fallback**: Automatic failover ensures the system runs immediately even if a local MySQL daemon is not running.

---

## 📂 Project Directory Structure

```text
banking-system/
├── app.py                      # Main Flask web application & REST API routes
├── config.py                   # System configuration & DB parameters
├── requirements.txt            # Python dependencies
├── run.bat                     # Windows 1-click startup launcher
├── test_system.py              # Automated test suite
├── database/
│   ├── db.py                   # Smart database connection manager (MySQL/SQLite dual support)
│   ├── mysql_schema.sql        # MySQL table definitions & foreign key constraints
│   ├── seed_data.sql           # Realistic demonstration dataset
│   └── banking_system.db       # Embedded database (auto-generated)
├── static/
│   ├── css/
│   │   ├── style.css           # Navy & blue banking design system
│   │   └── print.css           # Official bank statement print stylesheet
│   └── js/
│       ├── api.js              # Fetch client, toast notifications, UI helpers
│       ├── app.js              # Dashboard controller, Chart.js, CRUD operations
│       └── auth.js             # Authentication, password toggle, demo autofill
└── templates/
    ├── index.html              # Modern unified single-page dashboard
    ├── login.html              # Multi-role authentication & registration portal
    └── statement.html          # Official printable bank account statement
```

---

## ⚡ Setup & Execution Guide

### Option 1: One-Click Startup (Windows)
Double-click `run.bat` in the project directory, or run from PowerShell:
```powershell
.\run.bat
```
Then open your web browser to: **`http://127.0.0.1:5000`**

### Option 2: Manual Command Line Startup
1. Open PowerShell / Command Prompt in `banking-system/`.
2. (Optional) Configure MySQL in `config.py` or environment variables:
   ```powershell
   $env:MYSQL_HOST = "localhost"
   $env:MYSQL_USER = "root"
   $env:MYSQL_PASSWORD = ""
   $env:MYSQL_DB = "simple_banking_db"
   ```
3. Run the application:
   ```powershell
   python app.py
   ```
4. Access the portal at `http://127.0.0.1:5000/login`.

---

## 🧪 Running Automated Tests
To verify all unit tests and banking operations:
```powershell
python test_system.py
```
Expected output:
```text
Ran 6 tests in 0.4s
OK
[TEST PASS] Pages Rendered Successfully.
[TEST PASS] Authentication and Role Validation.
[TEST PASS] Customer Registration Created Account.
[TEST PASS] Dashboard Metrics: Liquidity Calculation.
[TEST PASS] Deposit, Balance Check, and Atomic Fund Transfer.
[TEST PASS] Statement Generation, CSV Export, and Admin Audit Logging.
```

---

## ⚖️ Academic Disclaimer
*This project is strictly for academic and software engineering evaluation purposes. All data, account numbers, and monetary figures are simulated mock values. It does not connect to real financial payment gateways or banking clearinghouses.*
