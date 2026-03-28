"""Tests for report module"""

import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from bank_account import BankAccount, Currency
from bank_system import Bank, Client
from transaction import (
    Transaction,
    TransactionProcessor,
    TransactionQueue,
    TransactionType,
)
from audit import AuditLog, RiskAnalyzer
from report import ReportBuilder


class ReportTestBase(unittest.TestCase):
    """Shared setup for report tests"""

    def setUp(self):
        self.bank = Bank()
        self.audit_log = AuditLog()
        self.analyzer = RiskAnalyzer(self.audit_log, high_amount_threshold=100000)

        c1 = Client("Alice", "C1", date(1990, 1, 1), "1234", contacts=["C2"])
        c2 = Client("Bob", "C2", date(1985, 6, 15), "5678")
        self.bank.add_client(c1, is_night=False)
        self.bank.add_client(c2, is_night=False)

        self.acc1 = BankAccount("Alice", account_id="A1", balance=100000, currency=Currency.RUB)
        self.acc2 = BankAccount("Bob", account_id="A2", balance=50000, currency=Currency.RUB)
        self.acc3 = BankAccount("Bob", account_id="A3", balance=5000, currency=Currency.USD)
        self.bank.open_account("C1", self.acc1, is_night=False)
        self.bank.open_account("C2", self.acc2, is_night=False)
        self.bank.open_account("C2", self.acc3, is_night=False)

        self.accounts = {"A1": self.acc1, "A2": self.acc2, "A3": self.acc3}
        self.processor = TransactionProcessor(self.accounts, risk_analyzer=self.analyzer)

        txns = [
            Transaction(TransactionType.DEPOSIT, 10000, Currency.RUB, receiver_account_id="A1"),
            Transaction(TransactionType.WITHDRAWAL, 5000, Currency.RUB, sender_account_id="A1"),
            Transaction(TransactionType.TRANSFER, 20000, Currency.RUB, sender_account_id="A1", receiver_account_id="A2"),
            Transaction(TransactionType.TRANSFER, 15000, Currency.RUB, sender_account_id="A2", receiver_account_id="A1"),
            Transaction(TransactionType.DEPOSIT, 3000, Currency.RUB, receiver_account_id="A2"),
        ]
        queue = TransactionQueue()
        for t in txns:
            queue.add(t)
        self.processor.process_queue(queue, is_night=False)

        self.builder = ReportBuilder(self.bank, self.analyzer, self.processor)
        import tempfile
        self.output_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)


class TestClientReport(ReportTestBase):

    def test_client_report_structure(self):
        report = self.builder.client_report("C1")
        self.assertEqual(report["client_id"], "C1")
        self.assertEqual(report["name"], "Alice")
        self.assertIn("accounts", report)
        self.assertIn("transaction_count", report)
        self.assertIn("risk_profiles", report)

    def test_client_report_accounts(self):
        report = self.builder.client_report("C1")
        self.assertEqual(len(report["accounts"]), 1)
        self.assertEqual(report["accounts"][0]["account_id"], "A1")

    def test_client_report_unknown(self):
        report = self.builder.client_report("UNKNOWN")
        self.assertEqual(report, {})

    def test_client_report_transaction_count(self):
        report = self.builder.client_report("C1")
        self.assertGreater(report["transaction_count"], 0)


class TestBankReport(ReportTestBase):

    def test_bank_report_structure(self):
        report = self.builder.bank_report()
        self.assertEqual(report["total_clients"], 2)
        self.assertEqual(report["total_accounts"], 3)
        self.assertIn("top_clients", report)
        self.assertIn("transactions", report)
        self.assertIn("total_balance_by_currency", report)

    def test_bank_report_transactions(self):
        report = self.builder.bank_report()
        self.assertEqual(report["transactions"]["total"], 5)
        self.assertIn("deposit", report["transactions"]["by_type"])

    def test_bank_report_top_clients(self):
        report = self.builder.bank_report()
        self.assertGreater(len(report["top_clients"]), 0)
        self.assertIn("name", report["top_clients"][0])


class TestRiskReport(ReportTestBase):

    def test_risk_report_structure(self):
        report = self.builder.risk_report()
        self.assertIn("risk_distribution", report)
        self.assertIn("suspicious_count", report)
        self.assertIn("error_stats", report)

    def test_risk_report_distribution(self):
        report = self.builder.risk_report()
        dist = report["risk_distribution"]
        self.assertIn("low", dist)
        self.assertIn("medium", dist)
        self.assertIn("high", dist)


class TestTextFormat(ReportTestBase):

    def test_format_text(self):
        report = self.builder.bank_report()
        text = self.builder.format_text(report, "Bank Report")
        self.assertIn("Bank Report", text)
        self.assertIn("total_clients", text)


class TestExportJson(ReportTestBase):

    def test_export_to_json(self):
        report = self.builder.bank_report()
        path = self.output_dir / "bank.json"
        self.builder.export_to_json(report, path)
        with open(path) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["total_clients"], 2)

    def test_export_client_to_json(self):
        report = self.builder.client_report("C1")
        path = self.output_dir / "client.json"
        self.builder.export_to_json(report, path)
        self.assertTrue(path.exists())


class TestExportCsv(ReportTestBase):

    def test_export_to_csv(self):
        report = self.builder.bank_report()
        rows = [
            {"client_id": c["client_id"], "name": c["name"], "total": c["total"]}
            for c in report["top_clients"]
        ]
        path = self.output_dir / "clients.csv"
        self.builder.export_to_csv(rows, path)
        with open(path) as f:
            content = f.read()
        self.assertIn("client_id", content)
        self.assertIn("Alice", content)

    def test_export_empty_csv(self):
        path = self.output_dir / "empty.csv"
        self.builder.export_to_csv([], path)
        self.assertFalse(path.exists())


class TestCharts(ReportTestBase):

    def test_chart_transactions_by_type(self):
        path = self.output_dir / "pie.png"
        self.builder.chart_transactions_by_type(path)
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 0)

    def test_chart_client_balances(self):
        path = self.output_dir / "bar.png"
        self.builder.chart_client_balances(path)
        self.assertTrue(path.exists())

    def test_chart_balance_history(self):
        path = self.output_dir / "line.png"
        self.builder.chart_balance_history("A1", path)
        self.assertTrue(path.exists())

    def test_chart_balance_history_unknown(self):
        path = self.output_dir / "unknown.png"
        self.builder.chart_balance_history("UNKNOWN", path)
        self.assertFalse(path.exists())

    def test_save_charts(self):
        saved = self.builder.save_charts(self.output_dir / "all")
        self.assertGreater(len(saved), 0)
        for p in saved:
            self.assertTrue(Path(p).exists())


if __name__ == "__main__":
    unittest.main()