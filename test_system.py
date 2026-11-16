import unittest
import json
from app import app
from database.db import db

class BankingSystemTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_health_and_index(self):
        res = self.app.get('/')
        self.assertEqual(res.status_code, 200)

        res_login = self.app.get('/login')
        self.assertEqual(res_login.status_code, 200)

        res_stmt = self.app.get('/statement')
        self.assertEqual(res_stmt.status_code, 200)
        print("[TEST PASS] Pages Rendered Successfully.")

    def test_02_authentication(self):
        # 1. Admin login
        res = self.app.post('/api/auth/login', json={
            'email': 'admin@bank.com',
            'password': 'Admin@123',
            'role': 'admin'
        })
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['role'], 'admin')

        # 2. Invalid password
        res_fail = self.app.post('/api/auth/login', json={
            'email': 'admin@bank.com',
            'password': 'WrongPassword!',
            'role': 'admin'
        })
        self.assertEqual(res_fail.status_code, 401)
        print("[TEST PASS] Authentication and Role Validation.")

    def test_03_customer_registration(self):
        res = self.app.post('/api/auth/register', json={
            'full_name': 'Michael Scott',
            'email': 'michael.scott@dundermifflin.com',
            'phone': '+1-555-987-6543',
            'password': 'Password@123',
            'address': '1725 Slough Ave',
            'city': 'Scranton',
            'occupation': 'Regional Manager',
            'initial_deposit': 2500.00
        })
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue('account_number' in data)
        print(f"[TEST PASS] Customer Registration Created Account: {data['account_number']}")

    def test_04_dashboard_stats(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'
            sess['full_name'] = 'System Administrator'

        res = self.app.get('/api/dashboard/stats')
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['summary']['total_accounts'], 0)
        self.assertGreater(data['summary']['total_liquidity'], 0)
        print(f"[TEST PASS] Dashboard Metrics: Liquidity ${data['summary']['total_liquidity']:,.2f}")

    def test_05_banking_operations(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        # Fetch accounts
        accs = db.query_all("SELECT * FROM accounts WHERE status = 'active' ORDER BY id ASC")
        self.assertGreaterEqual(len(accs), 2)
        acc1 = accs[0]
        acc2 = accs[1]

        # 1. Deposit
        dep_res = self.app.post('/api/operations/deposit', json={
            'account_number': acc1['account_number'],
            'amount': 500.00,
            'description': 'Automated Test Deposit'
        })
        dep_data = dep_res.get_json()
        self.assertTrue(dep_data['success'])
        self.assertEqual(dep_data['new_balance'], round(float(acc1['balance']) + 500.00, 2))

        # 2. Withdrawal (Insufficient balance rejection)
        withdraw_fail = self.app.post('/api/operations/withdraw', json={
            'account_number': acc1['account_number'],
            'amount': 99999999.00,
            'description': 'Over-limit withdrawal'
        })
        self.assertEqual(withdraw_fail.status_code, 400)

        # 3. Valid withdrawal
        withdraw_ok = self.app.post('/api/operations/withdraw', json={
            'account_number': acc1['account_number'],
            'amount': 200.00,
            'description': 'Test ATM Cash'
        })
        self.assertTrue(withdraw_ok.get_json()['success'])

        # 4. Atomic Inter-Account Fund Transfer
        bal1_before = float(db.query_one("SELECT balance FROM accounts WHERE id = %s", (acc1['id'],))['balance'])
        bal2_before = float(db.query_one("SELECT balance FROM accounts WHERE id = %s", (acc2['id'],))['balance'])

        transfer_res = self.app.post('/api/operations/transfer', json={
            'from_account': acc1['account_number'],
            'to_account': acc2['account_number'],
            'amount': 300.00,
            'description': 'Test Inter-Account Transfer'
        })
        self.assertTrue(transfer_res.get_json()['success'])

        bal1_after = float(db.query_one("SELECT balance FROM accounts WHERE id = %s", (acc1['id'],))['balance'])
        bal2_after = float(db.query_one("SELECT balance FROM accounts WHERE id = %s", (acc2['id'],))['balance'])

        self.assertEqual(round(bal1_before - 300.00, 2), round(bal1_after, 2))
        self.assertEqual(round(bal2_before + 300.00, 2), round(bal2_after, 2))
        print("[TEST PASS] Deposit, Balance Check, and Atomic Fund Transfer.")

    def test_06_statement_and_admin(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        acc = db.query_one("SELECT account_number FROM accounts LIMIT 1")
        stmt_res = self.app.get(f"/api/statement/{acc['account_number']}")
        self.assertTrue(stmt_res.get_json()['success'])

        csv_res = self.app.get(f"/api/statement/{acc['account_number']}/download-csv")
        self.assertEqual(csv_res.status_code, 200)

        audit_res = self.app.get('/api/admin/audit-logs')
        self.assertTrue(audit_res.get_json()['success'])
        self.assertGreater(len(audit_res.get_json()['audit_logs']), 0)
        print("[TEST PASS] Statement Generation, CSV Export, and Admin Audit Logging.")

if __name__ == '__main__':
    unittest.main()
