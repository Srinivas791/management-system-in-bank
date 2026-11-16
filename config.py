import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'simple-banking-super-secret-key-2026')
    
    # Database mode: 'auto', 'mysql', or 'sqlite'
    # 'auto' tries MySQL first; if unreachable, falls back gracefully to SQLite.
    DB_TYPE = os.environ.get('DB_TYPE', 'auto')
    
    # MySQL Configuration
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'simple_banking_db')
    
    # SQLite fallback file path
    SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'banking_system.db')
    
    # Banking business rules
    MIN_SAVINGS_BALANCE = 500.00
    MAX_DAILY_TRANSFER_LIMIT = 50000.00
    OVERDRAFT_LIMIT_CURRENT = 10000.00
