# B.Tech Software Engineering Project Report
# Simple Banking Management System

---

## 1. Project Title & Overview
- **Project Title:** Simple Banking Management System (Apex Horizon National Bank)
- **Academic Domain:** B.Tech Computer Science & Engineering / Information Technology
- **Subject:** Software Engineering & Database Management Systems
- **Architecture Model:** Three-Tier Architecture (Client-Side Presentation, Application Logic / REST API, Relational Database Layer)

---

## 2. Problem Statement & Objectives
Traditional legacy banking software often suffers from fragmented user experiences, unintuitive workflows, and lack of clear separation of concerns across user roles.

### Objectives:
1. Deliver a secure, responsive, role-based banking prototype supporting **Admin**, **Employee**, and **Customer** personas.
2. Implement core double-entry banking operations: **Cash Deposit**, **Cash Withdrawal**, and **Atomic Inter-Account Fund Transfer**.
3. Guarantee database integrity and ACID compliance (Atomicity, Consistency, Isolation, Durability) to eliminate race conditions and partial balance mutations.
4. Provide comprehensive auditing, telemetry dashboards, interactive Chart.js visualizations, and downloadable account statements.

---

## 3. System Architecture Diagram

```mermaid
flowchart TD
    subgraph ClientLayer ["1. Presentation Layer (Browser UI)"]
        UI_Dash["Responsive Dashboard (HTML5/CSS3)"]
        UI_Charts["Chart.js Analytics (Trends & Flow)"]
        UI_Portal["Auth & Registration Portal"]
        UI_Stmt["Official Printable Statement View"]
    end

    subgraph AppLayer ["2. Application Logic Layer (Python Flask REST API)"]
        AuthModule["Authentication & RBAC Middleware"]
        OpsModule["Banking Operations Engine (Deposit, Withdraw, Transfer)"]
        CustModule["Customer & Account Lifecycle Manager"]
        AuditModule["Security & Audit Log Service"]
    end

    subgraph DataLayer ["3. Database & Persistence Layer"]
        DBManager["Database Abstraction (MySQL / PyMySQL)"]
        DBSQLite["Embedded SQLite Fallback Engine"]
        DBStore[("Relational Database: simple_banking_db")]
    end

    ClientLayer <-->|JSON / REST HTTP Requests| AppLayer
    AppLayer <-->|ACID Transactions & SQL Queries| DataLayer
```

---

## 4. Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    USERS ||--o| CUSTOMERS : "extends"
    USERS ||--o{ AUDIT_LOGS : "triggers"
    CUSTOMERS ||--|{ ACCOUNTS : "owns"
    ACCOUNTS ||--o{ TRANSACTIONS : "debit_from"
    ACCOUNTS ||--o{ TRANSACTIONS : "credit_to"

    USERS {
        int id PK
        string full_name
        string email UK
        string phone
        string password_hash
        string role "admin | employee | customer"
        string status "active | inactive"
        datetime created_at
    }

    CUSTOMERS {
        int id PK
        int user_id FK
        date date_of_birth
        string address
        string city
        string state
        string postal_code
        string id_number
        string occupation
        decimal annual_income
    }

    ACCOUNTS {
        int id PK
        int customer_id FK
        string account_number UK
        string account_type "Savings | Current"
        decimal balance
        string status "active | frozen | closed"
        datetime created_at
    }

    TRANSACTIONS {
        int id PK
        string transaction_ref UK
        int from_account_id FK
        int to_account_id FK
        string transaction_type "DEPOSIT | WITHDRAWAL | TRANSFER"
        decimal amount
        decimal balance_after
        string status "SUCCESS | PENDING | FAILED"
        string description
        int created_by FK
        datetime created_at
    }

    AUDIT_LOGS {
        int id PK
        int user_id FK
        string action
        text details
        string ip_address
        datetime created_at
    }
```

---

## 5. Data Flow Diagrams (DFD)

### Level 0 DFD (Context Diagram)

```mermaid
flowchart LR
    User["Bank User (Customer / Staff / Admin)"] -->|1. Credentials / Request Data| BankSystem["Simple Banking Management System"]
    BankSystem -->|2. Authentication Status, Dashboards, Statements, Receipts| User
    BankSystem <-->|3. Balance updates, Transaction Records, Audit Logs| Database[("Banking Database Engine")]
```

### Level 1 DFD (Banking Operations Breakdown)

```mermaid
flowchart TD
    User["Authenticated User"]

    User -->|Deposit Request| P1["Process Deposit"]
    P1 -->|Increment Balance| AccDB[("Accounts Table")]
    P1 -->|Write Record| TxnDB[("Transactions Table")]

    User -->|Withdrawal Request| P2["Process Withdrawal"]
    P2 -->|Check Balance >= Amount| AccDB
    P2 -->|Decrement Balance| AccDB
    P2 -->|Write Record| TxnDB

    User -->|Transfer Request| P3["Process Inter-Account Transfer"]
    P3 -->|Validate Both Accounts & Balance| AccDB
    P3 -->|Atomic Transaction: Debit Sender & Credit Receiver| AccDB
    P3 -->|Insert Transfer Record| TxnDB
```

---

## 6. Database Dictionary

| Table Name | Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `users` | `id` | INT / INTEGER | PK, AUTO_INCREMENT | Unique user identifier |
| `users` | `full_name` | VARCHAR(100) | NOT NULL | User's legal name |
| `users` | `email` | VARCHAR(120) | UNIQUE, NOT NULL | Login credential |
| `users` | `password_hash` | VARCHAR(255) | NOT NULL | Secure salted hash (pbkdf2:sha256) |
| `users` | `role` | VARCHAR(20) | ENUM('admin','employee','customer') | RBAC permission level |
| `customers` | `id` | INT / INTEGER | PK, AUTO_INCREMENT | Customer identity |
| `customers` | `user_id` | INT / INTEGER | FK -> users(id) | Associated user account |
| `customers` | `id_number` | VARCHAR(50) | NULL | National ID / Government proof |
| `accounts` | `id` | INT / INTEGER | PK, AUTO_INCREMENT | Account primary key |
| `accounts` | `customer_id` | INT / INTEGER | FK -> customers(id) | Account owner reference |
| `accounts` | `account_number` | VARCHAR(20) | UNIQUE, NOT NULL | 10-digit bank account number |
| `accounts` | `account_type` | VARCHAR(20) | Savings, Current | Retail product category |
| `accounts` | `balance` | DECIMAL(15,2) | NOT NULL, DEFAULT 0.00 | Real-time available ledger balance |
| `accounts` | `status` | VARCHAR(20) | active, frozen, closed | Operational state |
| `transactions` | `id` | INT / INTEGER | PK, AUTO_INCREMENT | Transaction row ID |
| `transactions` | `transaction_ref` | VARCHAR(30) | UNIQUE, NOT NULL | Unique reference code (e.g. TXN-...) |
| `transactions` | `transaction_type` | VARCHAR(20) | DEPOSIT, WITHDRAWAL, TRANSFER | Accounting operation type |
| `transactions` | `amount` | DECIMAL(15,2) | NOT NULL, > 0.00 | Monetary value |
| `transactions` | `balance_after` | DECIMAL(15,2) | NOT NULL | Resulting balance post-mutation |
| `audit_logs` | `id` | INT / INTEGER | PK, AUTO_INCREMENT | Audit log primary key |
| `audit_logs` | `action` | VARCHAR(100) | NOT NULL | Security / operational event name |

---

## 7. Security Architecture & Implementation

1. **Password Hashing**: Passwords are never stored in plaintext. Passwords are transformed using PBKDF2 with SHA-256 and cryptographic salts via `werkzeug.security`.
2. **Atomic Fund Transfers (ACID Compliance)**: Fund transfers update both sender and receiver accounts inside an isolated transaction block (`BEGIN ... COMMIT`). If an exception or database disconnect occurs, a complete `ROLLBACK` is issued to prevent money creation or destruction.
3. **Role-Based Access Control (RBAC)**: Enforced both on the client UI and verified strictly server-side using the `@role_required(['admin', 'employee'])` Python decorator.
4. **Input Sanitization & Validation**:
   - Negative amounts and zero transfers are rejected with HTTP 400.
   - Sender cannot transfer funds to their own account.
   - Withdrawals exceeding available balances are blocked before executing database writes.

---

## 8. Academic Viva & Review Questions

**Q1: How does the system handle atomicity during fund transfers?**  
*Answer:* The application wraps debit and credit database operations in a single atomic database transaction. If the receiver credit fails after the sender debit, the transaction context triggers a rollback, restoring the original balance without side-effects.

**Q2: What is the benefit of the dual MySQL/SQLite database manager?**  
*Answer:* In real-world software engineering, dependency on external services must not prevent evaluation or development. The database layer (`DatabaseManager`) seamlessly connects to MySQL if available, but falls back to SQLite transparently while using the exact same schema and SQL queries.

**Q3: How are passwords secured against rainbow table attacks?**  
*Answer:* Werkzeug's `generate_password_hash` applies PBKDF2 with HMAC-SHA256 and an automatically generated cryptographic salt, ensuring identical plaintext passwords produce distinct hashes.
