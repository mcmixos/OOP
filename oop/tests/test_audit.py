"""Tests for audit module."""

import json
import os
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from bank_account import BankAccount, Currency
from transaction import (
    Transaction,
    TransactionProcessor,
    TransactionQueue,
    TransactionStatus,
    TransactionType,
)
from audit import (
    AuditLog,
    LogLevel,
    RiskAnalyzer,
    RiskLevel,
    RiskResult,
)


class TestAuditLog(unittest.TestCase):

    def test_log_and_retrieve(self):
        log = AuditLog()
        log.log(LogLevel.INFO, "test message", txn_id="abc")
        self.assertEqual(len(log.entries), 1)
        self.assertEqual(log.entries[0]["message"], "test message")
        self.assertEqual(log.entries[0]["txn_id"], "abc")

    def test_log_levels(self):
        log = AuditLog()
        log.log(LogLevel.INFO, "info")
        log.log(LogLevel.WARNING, "warn")
        log.log(LogLevel.CRITICAL, "crit")
        self.assertEqual(len(log.entries), 3)
        self.assertEqual(log.entries[1]["level"], "warning")

    def test_filter_by_level(self):
        log = AuditLog()
        log.log(LogLevel.INFO, "info")
        log.log(LogLevel.WARNING, "warn")
        log.log(LogLevel.INFO, "info2")
        results = log.filter(level=LogLevel.WARNING)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["message"], "warn")

    def test_filter_by_time(self):
        log = AuditLog()
        log.log(LogLevel.INFO, "msg")
        after = datetime.now() + timedelta(hours=1)
        results = log.filter(after=after)
        self.assertEqual(len(results), 0)

    def test_decimal_serialized_as_str(self):
        log = AuditLog()
        log.log(LogLevel.INFO, "test", amount=Decimal("123.45"))
        self.assertEqual(log.entries[0]["amount"], "123.45")

    def test_clear(self):
        log = AuditLog()
        log.log(LogLevel.INFO, "test")
        log.clear()
        self.assertEqual(len(log.entries), 0)

    def test_file_output(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            log = AuditLog(log_file=path)
            log.log(LogLevel.INFO, "file test", txn_id="123")
            log.log(LogLevel.WARNING, "warn test")

            with open(path, "r") as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 2)
            entry = json.loads(lines[0])
            self.assertEqual(entry["message"], "file test")
            self.assertEqual(entry["txn_id"], "123")
        finally:
            os.remove(path)


class TestRiskResult(unittest.TestCase):

    def test_str(self):
        r = RiskResult(RiskLevel.HIGH, ["high amount", "night operation"])
        self.assertIn("high", str(r))


class TestRiskAnalyzer(unittest.TestCase):

    def setUp(self):
        self.log = AuditLog()
        self.analyzer = RiskAnalyzer(self.log, high_amount_threshold=100000)

    def test_low_risk(self):
        txn = Transaction(TransactionType.DEPOSIT, 1000, Currency.RUB, receiver_account_id="A1")
        result = self.analyzer.analyze(txn, is_night=False)
        self.assertIs(result.risk_level, RiskLevel.LOW)
        self.assertEqual(result.reasons, [])

    def test_high_amount_medium(self):
        txn = Transaction(TransactionType.DEPOSIT, 200000, Currency.RUB, receiver_account_id="A1")
        result = self.analyzer.analyze(txn, is_night=False)
        self.assertIs(result.risk_level, RiskLevel.MEDIUM)
        self.assertIn("high amount", result.reasons)

    def test_night_medium(self):
        txn = Transaction(TransactionType.DEPOSIT, 1000, Currency.RUB, receiver_account_id="A1")
        result = self.analyzer.analyze(txn, is_night=True)
        self.assertIs(result.risk_level, RiskLevel.MEDIUM)
        self.assertIn("night operation", result.reasons)

    def test_new_receiver_medium(self):
        txn = Transaction(
            TransactionType.TRANSFER, 1000, Currency.RUB,
            sender_account_id="A1", receiver_account_id="A2",
        )
        result = self.analyzer.analyze(txn, is_night=False)
        self.assertIs(result.risk_level, RiskLevel.MEDIUM)
        self.assertIn("new receiver", result.reasons)

    def test_known_receiver_no_flag(self):
        txn1 = Transaction(
            TransactionType.TRANSFER, 1000, Currency.RUB,
            sender_account_id="A1", receiver_account_id="A2",
        )
        self.analyzer.analyze(txn1, is_night=False)
        self.analyzer.register_completed(txn1)

        txn2 = Transaction(
            TransactionType.TRANSFER, 1000, Currency.RUB,
            sender_account_id="A1", receiver_account_id="A2",
        )
        result = self.analyzer.analyze(txn2, is_night=False)
        self.assertNotIn("new receiver", result.reasons)

    def test_blocked_transfer_receiver_stays_unknown(self):
        analyzer = RiskAnalyzer(self.log, high_amount_threshold=100000)
        txn = Transaction(
            TransactionType.TRANSFER, 200000, Currency.RUB,
            sender_account_id="A1", receiver_account_id="A2",
        )
        result = analyzer.analyze(txn, is_night=True)
        self.assertIs(result.risk_level, RiskLevel.HIGH)
        # blocked — receiver NOT registered

        txn2 = Transaction(
            TransactionType.TRANSFER, 500, Currency.RUB,
            sender_account_id="A1", receiver_account_id="A2",
        )
        result2 = analyzer.analyze(txn2, is_night=False)
        self.assertIn("new receiver", result2.reasons)

    def test_high_frequency_medium(self):
        analyzer = RiskAnalyzer(self.log, frequency_limit=3)
        for _ in range(3):
            txn = Transaction(TransactionType.WITHDRAWAL, 100, Currency.RUB, sender_account_id="A1")
            analyzer.analyze(txn, is_night=False)

        txn = Transaction(TransactionType.WITHDRAWAL, 100, Currency.RUB, sender_account_id="A1")
        result = analyzer.analyze(txn, is_night=False)
        self.assertIn("high frequency", result.reasons)

    def test_two_factors_high(self):
        txn = Transaction(TransactionType.DEPOSIT, 200000, Currency.RUB, receiver_account_id="A1")
        result = self.analyzer.analyze(txn, is_night=True)
        self.assertIs(result.risk_level, RiskLevel.HIGH)
        self.assertIn("high amount", result.reasons)
        self.assertIn("night operation", result.reasons)

    def test_audit_log_populated(self):
        txn = Transaction(TransactionType.DEPOSIT, 1000, Currency.RUB, receiver_account_id="A1")
        self.analyzer.analyze(txn, is_night=False)
        self.assertEqual(len(self.log.entries), 1)
        self.assertEqual(self.log.entries[0]["txn_id"], txn.txn_id)


class TestRiskAnalyzerReports(unittest.TestCase):

    def setUp(self):
        self.log = AuditLog()
        self.analyzer = RiskAnalyzer(self.log, high_amount_threshold=100000)

    def test_get_suspicious_transactions(self):
        safe = Transaction(TransactionType.DEPOSIT, 100, Currency.RUB, receiver_account_id="A1")
        risky = Transaction(TransactionType.DEPOSIT, 200000, Currency.RUB, receiver_account_id="A1")
        self.analyzer.analyze(safe, is_night=False)
        self.analyzer.analyze(risky, is_night=False)
        suspicious = self.analyzer.get_suspicious_transactions()
        self.assertEqual(len(suspicious), 1)

    def test_get_client_risk_profile(self):
        for _ in range(3):
            txn = Transaction(TransactionType.WITHDRAWAL, 100, Currency.RUB, sender_account_id="A1")
            self.analyzer.analyze(txn, is_night=False)
        txn = Transaction(TransactionType.WITHDRAWAL, 200000, Currency.RUB, sender_account_id="A1")
        self.analyzer.analyze(txn, is_night=False)

        profile = self.analyzer.get_client_risk_profile("A1")
        self.assertEqual(profile["total_transactions"], 4)
        self.assertIn("low", profile["risk_summary"])
        self.assertIn("medium", profile["risk_summary"])

    def test_get_client_risk_profile_unknown(self):
        profile = self.analyzer.get_client_risk_profile("UNKNOWN")
        self.assertEqual(profile["total_transactions"], 0)

    def test_get_error_stats(self):
        txn = Transaction(TransactionType.WITHDRAWAL, 100, Currency.RUB, sender_account_id="A1")
        txn.status = TransactionStatus.FAILED
        txn.failure_reason = "insufficient funds"
        self.analyzer._transaction_history.append(txn)

        stats = self.analyzer.get_error_stats()
        self.assertEqual(stats["total_failed"], 1)
        self.assertEqual(stats["by_reason"]["insufficient funds"], 1)


class TestProcessorRiskIntegration(unittest.TestCase):

    def test_high_risk_blocks_transaction(self):
        log = AuditLog()
        analyzer = RiskAnalyzer(log, high_amount_threshold=100000)
        acc = BankAccount("Test", account_id="A1", balance=500000)
        processor = TransactionProcessor({"A1": acc}, risk_analyzer=analyzer)

        txn = Transaction(TransactionType.WITHDRAWAL, 200000, Currency.RUB, sender_account_id="A1")
        # high amount + night = HIGH risk - immediate block
        processor.process(txn, is_night=True)

        self.assertIs(txn.status, TransactionStatus.FAILED)
        self.assertIn("blocked", txn.failure_reason)
        self.assertEqual(acc.balance, Decimal("500000"))
        # only 1 audit log entry, not 3
        self.assertEqual(len(log.entries), 1)

    def test_medium_risk_allowed(self):
        log = AuditLog()
        analyzer = RiskAnalyzer(log, high_amount_threshold=100000)
        acc = BankAccount("Test", account_id="A1", balance=500000)
        processor = TransactionProcessor({"A1": acc}, risk_analyzer=analyzer)

        txn = Transaction(TransactionType.WITHDRAWAL, 200000, Currency.RUB, sender_account_id="A1")
        processor.process(txn, is_night=False)

        self.assertIs(txn.status, TransactionStatus.COMPLETED)
        self.assertEqual(acc.balance, Decimal("300000"))

    def test_no_analyzer_works_as_before(self):
        acc = BankAccount("Test", account_id="A1", balance=10000)
        processor = TransactionProcessor({"A1": acc})

        txn = Transaction(TransactionType.WITHDRAWAL, 5000, Currency.RUB, sender_account_id="A1")
        processor.process(txn)

        self.assertIs(txn.status, TransactionStatus.COMPLETED)
        self.assertEqual(acc.balance, Decimal("5000"))

    def test_queue_with_risk_analyzer(self):
        log = AuditLog()
        analyzer = RiskAnalyzer(log, high_amount_threshold=100000)
        acc = BankAccount("Test", account_id="A1", balance=1000000)
        processor = TransactionProcessor({"A1": acc}, risk_analyzer=analyzer)
        queue = TransactionQueue()

        safe = Transaction(TransactionType.WITHDRAWAL, 1000, Currency.RUB, sender_account_id="A1")
        risky = Transaction(TransactionType.WITHDRAWAL, 200000, Currency.RUB, sender_account_id="A1")
        queue.add(safe)
        queue.add(risky)

        results = processor.process_queue(queue, is_night=True)
        statuses = {t.amount: t.status for t in results}
        # 1000 at night = MEDIUM (1 factor) — allowed
        self.assertIs(statuses[Decimal("1000")], TransactionStatus.COMPLETED)
        # 200000 at night = HIGH (2 factors) — blocked
        self.assertIs(statuses[Decimal("200000")], TransactionStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
