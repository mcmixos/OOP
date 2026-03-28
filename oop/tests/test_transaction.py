"""Tests for transaction module"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from bank_account import (
    AccountFrozenError,
    AccountStatus,
    BankAccount,
    Currency,
    InsufficientFundsError,
    InvalidOperationError,
)
from bank_account_types import PremiumAccount, SavingsAccount
from transaction import (
    EXCHANGE_RATES,
    Priority,
    Transaction,
    TransactionProcessor,
    TransactionQueue,
    TransactionStatus,
    TransactionType,
)


class TestTransactionCreation(unittest.TestCase):

    def test_transfer(self):
        txn = Transaction(
            TransactionType.TRANSFER, 1000, Currency.RUB,
            sender_account_id="A1", receiver_account_id="A2",
        )
        self.assertEqual(txn.amount, Decimal("1000"))
        self.assertEqual(txn.txn_type, TransactionType.TRANSFER)
        self.assertIs(txn.status, TransactionStatus.PENDING)
        self.assertEqual(len(txn.txn_id), 8)

    def test_deposit(self):
        txn = Transaction(TransactionType.DEPOSIT, 500, Currency.USD, receiver_account_id="A1")
        self.assertEqual(txn.receiver_account_id, "A1")

    def test_withdrawal(self):
        txn = Transaction(TransactionType.WITHDRAWAL, 300, Currency.EUR, sender_account_id="A1")
        self.assertEqual(txn.sender_account_id, "A1")

    def test_external_transfer_no_receiver(self):
        txn = Transaction(
            TransactionType.TRANSFER, 1000, Currency.RUB,
            sender_account_id="A1", is_external=True,
        )
        self.assertTrue(txn.is_external)
        self.assertIsNone(txn.receiver_account_id)

    def test_transfer_no_sender_raises(self):
        with self.assertRaises(InvalidOperationError):
            Transaction(TransactionType.TRANSFER, 1000, Currency.RUB, receiver_account_id="A2")

    def test_transfer_no_receiver_not_external_raises(self):
        with self.assertRaises(InvalidOperationError):
            Transaction(TransactionType.TRANSFER, 1000, Currency.RUB, sender_account_id="A1")

    def test_deposit_no_receiver_raises(self):
        with self.assertRaises(InvalidOperationError):
            Transaction(TransactionType.DEPOSIT, 500, Currency.USD)

    def test_withdrawal_no_sender_raises(self):
        with self.assertRaises(InvalidOperationError):
            Transaction(TransactionType.WITHDRAWAL, 300, Currency.EUR)

    def test_zero_amount_raises(self):
        with self.assertRaises(InvalidOperationError):
            Transaction(TransactionType.DEPOSIT, 0, Currency.RUB, receiver_account_id="A1")

    def test_negative_amount_raises(self):
        with self.assertRaises(InvalidOperationError):
            Transaction(TransactionType.DEPOSIT, -100, Currency.RUB, receiver_account_id="A1")

    def test_scheduled(self):
        future = datetime.now() + timedelta(hours=1)
        txn = Transaction(
            TransactionType.DEPOSIT, 100, Currency.RUB,
            receiver_account_id="A1", scheduled_at=future,
        )
        self.assertEqual(txn.scheduled_at, future)

    def test_priority(self):
        txn = Transaction(
            TransactionType.DEPOSIT, 100, Currency.RUB,
            receiver_account_id="A1", priority=Priority.HIGH,
        )
        self.assertIs(txn.priority, Priority.HIGH)

    def test_str(self):
        txn = Transaction(TransactionType.DEPOSIT, 100, Currency.RUB, receiver_account_id="A1")
        self.assertIn("deposit", str(txn))
        self.assertIn("pending", str(txn))


class TestTransactionQueue(unittest.TestCase):

    def test_add_and_count(self):
        q = TransactionQueue()
        txn = Transaction(TransactionType.DEPOSIT, 100, Currency.RUB, receiver_account_id="A1")
        q.add(txn)
        self.assertEqual(q.pending_count, 1)

    def test_add_delayed(self):
        q = TransactionQueue()
        future = datetime.now() + timedelta(hours=1)
        txn = Transaction(
            TransactionType.DEPOSIT, 100, Currency.RUB,
            receiver_account_id="A1", scheduled_at=future,
        )
        q.add(txn)
        self.assertEqual(q.pending_count, 0)
        self.assertEqual(q.delayed_count, 1)

    def test_get_next_by_priority(self):
        q = TransactionQueue()
        low = Transaction(TransactionType.DEPOSIT, 10, Currency.RUB, receiver_account_id="A1", priority=Priority.LOW)
        high = Transaction(TransactionType.DEPOSIT, 20, Currency.RUB, receiver_account_id="A1", priority=Priority.HIGH)
        normal = Transaction(TransactionType.DEPOSIT, 30, Currency.RUB, receiver_account_id="A1", priority=Priority.NORMAL)
        q.add(low)
        q.add(high)
        q.add(normal)
        self.assertIs(q.get_next(), high)
        self.assertIs(q.get_next(), normal)
        self.assertIs(q.get_next(), low)

    def test_get_next_empty(self):
        q = TransactionQueue()
        self.assertIsNone(q.get_next())

    def test_cancel(self):
        q = TransactionQueue()
        txn = Transaction(TransactionType.DEPOSIT, 100, Currency.RUB, receiver_account_id="A1")
        q.add(txn)
        result = q.cancel(txn.txn_id)
        self.assertIs(result.status, TransactionStatus.CANCELLED)
        self.assertEqual(q.pending_count, 0)

    def test_cancel_delayed(self):
        q = TransactionQueue()
        future = datetime.now() + timedelta(hours=1)
        txn = Transaction(
            TransactionType.DEPOSIT, 100, Currency.RUB,
            receiver_account_id="A1", scheduled_at=future,
        )
        q.add(txn)
        result = q.cancel(txn.txn_id)
        self.assertIs(result.status, TransactionStatus.CANCELLED)
        self.assertEqual(q.delayed_count, 0)

    def test_cancel_nonexistent(self):
        q = TransactionQueue()
        self.assertIsNone(q.cancel("nonexistent"))

    def test_release_delayed(self):
        q = TransactionQueue()
        past = datetime.now() - timedelta(hours=1)
        future = datetime.now() + timedelta(hours=1)
        txn_ready = Transaction(
            TransactionType.DEPOSIT, 100, Currency.RUB,
            receiver_account_id="A1", scheduled_at=past,
        )
        txn_not_ready = Transaction(
            TransactionType.DEPOSIT, 200, Currency.RUB,
            receiver_account_id="A1", scheduled_at=future,
        )
        q.add(txn_ready)
        q.add(txn_not_ready)
        released = q.release_delayed(current_time=datetime.now())
        self.assertEqual(released, 1)
        self.assertEqual(q.pending_count, 1)
        self.assertEqual(q.delayed_count, 1)

    def test_add_non_pending_raises(self):
        q = TransactionQueue()
        txn = Transaction(TransactionType.DEPOSIT, 100, Currency.RUB, receiver_account_id="A1")
        txn.status = TransactionStatus.COMPLETED
        with self.assertRaises(InvalidOperationError):
            q.add(txn)


class TestCurrencyConversion(unittest.TestCase):

    def test_same_currency(self):
        result = TransactionProcessor.convert_currency(Decimal("100"), Currency.RUB, Currency.RUB)
        self.assertEqual(result, Decimal("100"))

    def test_rub_to_usd(self):
        result = TransactionProcessor.convert_currency(Decimal("9000"), Currency.RUB, Currency.USD)
        self.assertEqual(result, Decimal("100"))

    def test_usd_to_rub(self):
        result = TransactionProcessor.convert_currency(Decimal("100"), Currency.USD, Currency.RUB)
        self.assertEqual(result, Decimal("9000"))

    def test_eur_to_rub(self):
        result = TransactionProcessor.convert_currency(Decimal("92"), Currency.EUR, Currency.RUB)
        self.assertEqual(result, Decimal("9000"))


class TestProcessor(unittest.TestCase):

    def setUp(self):
        self.acc1 = BankAccount("Sender", account_id="A1", balance=100000, currency=Currency.RUB)
        self.acc2 = BankAccount("Receiver", account_id="A2", balance=50000, currency=Currency.RUB)
        self.accounts = {"A1": self.acc1, "A2": self.acc2}
        self.processor = TransactionProcessor(self.accounts)

    def test_deposit(self):
        txn = Transaction(TransactionType.DEPOSIT, 5000, Currency.RUB, receiver_account_id="A2")
        self.processor.process(txn)
        self.assertIs(txn.status, TransactionStatus.COMPLETED)
        self.assertEqual(self.acc2.balance, Decimal("55000"))

    def test_withdrawal(self):
        txn = Transaction(TransactionType.WITHDRAWAL, 3000, Currency.RUB, sender_account_id="A1")
        self.processor.process(txn)
        self.assertIs(txn.status, TransactionStatus.COMPLETED)
        self.assertEqual(self.acc1.balance, Decimal("97000"))

    def test_transfer(self):
        txn = Transaction(
            TransactionType.TRANSFER, 10000, Currency.RUB,
            sender_account_id="A1", receiver_account_id="A2",
        )
        self.processor.process(txn)
        self.assertIs(txn.status, TransactionStatus.COMPLETED)
        self.assertEqual(self.acc1.balance, Decimal("90000"))
        self.assertEqual(self.acc2.balance, Decimal("60000"))

    def test_external_transfer_commission(self):
        txn = Transaction(
            TransactionType.TRANSFER, 10000, Currency.RUB,
            sender_account_id="A1", is_external=True,
        )
        self.processor.process(txn)
        self.assertIs(txn.status, TransactionStatus.COMPLETED)
        # 10000 + 2% commission = 10200 
        self.assertEqual(self.acc1.balance, Decimal("89800"))
        self.assertEqual(txn.commission, Decimal("200"))

    def test_internal_transfer_no_commission(self):
        txn = Transaction(
            TransactionType.TRANSFER, 10000, Currency.RUB,
            sender_account_id="A1", receiver_account_id="A2",
        )
        self.processor.process(txn)
        self.assertEqual(txn.commission, Decimal("0"))

    def test_insufficient_funds_regular(self):
        txn = Transaction(
            TransactionType.WITHDRAWAL, 999999, Currency.RUB,
            sender_account_id="A1",
        )
        # 3 retries then fail
        self.processor.process(txn)
        self.processor.process(txn)
        self.processor.process(txn)
        self.assertIs(txn.status, TransactionStatus.FAILED)
        self.assertIsNotNone(txn.failure_reason)

    def test_frozen_account_fails(self):
        self.acc1.set_status(AccountStatus.FROZEN)
        txn = Transaction(TransactionType.WITHDRAWAL, 100, Currency.RUB, sender_account_id="A1")
        self.processor.process(txn)
        self.processor.process(txn)
        self.processor.process(txn)
        self.assertIs(txn.status, TransactionStatus.FAILED)

    def test_retries_then_fail(self):
        txn = Transaction(TransactionType.WITHDRAWAL, 999999, Currency.RUB, sender_account_id="A1")
        self.processor.process(txn)
        self.assertEqual(txn.retries, 1)
        self.assertIs(txn.status, TransactionStatus.PENDING)
        self.processor.process(txn)
        self.assertEqual(txn.retries, 2)
        self.processor.process(txn)
        self.assertEqual(txn.retries, 3)
        self.assertIs(txn.status, TransactionStatus.FAILED)

    def test_error_log(self):
        txn = Transaction(TransactionType.WITHDRAWAL, 999999, Currency.RUB, sender_account_id="A1")
        self.processor.process(txn)
        self.processor.process(txn)
        self.processor.process(txn)
        self.assertEqual(len(self.processor.error_log), 1)
        self.assertEqual(self.processor.error_log[0]["txn_id"], txn.txn_id)

    def test_transfer_atomic_rollback(self):
        self.acc2.set_status(AccountStatus.FROZEN)
        txn = Transaction(
            TransactionType.TRANSFER, 5000, Currency.RUB,
            sender_account_id="A1", receiver_account_id="A2",
        )
        self.processor.process(txn)
        self.processor.process(txn)
        self.processor.process(txn)
        # balance restored after failed deposit
        self.assertEqual(self.acc1.balance, Decimal("100000"))

    def test_completed_at_set(self):
        txn = Transaction(TransactionType.DEPOSIT, 100, Currency.RUB, receiver_account_id="A1")
        self.processor.process(txn)
        self.assertIsNotNone(txn.completed_at)

    def test_skip_non_pending(self):
        txn = Transaction(TransactionType.DEPOSIT, 100, Currency.RUB, receiver_account_id="A1")
        txn.status = TransactionStatus.COMPLETED
        self.processor.process(txn)
        # balance unchanged
        self.assertEqual(self.acc1.balance, Decimal("100000"))


class TestCrossCurrencyProcessor(unittest.TestCase):

    def test_deposit_usd_to_rub_account(self):
        acc = BankAccount("Test", account_id="A1", balance=0, currency=Currency.RUB)
        processor = TransactionProcessor({"A1": acc})
        txn = Transaction(TransactionType.DEPOSIT, 100, Currency.USD, receiver_account_id="A1")
        processor.process(txn)
        self.assertEqual(acc.balance, Decimal("9000"))

    def test_transfer_different_currencies(self):
        acc_rub = BankAccount("A", account_id="A1", balance=90000, currency=Currency.RUB)
        acc_usd = BankAccount("B", account_id="A2", balance=0, currency=Currency.USD)
        processor = TransactionProcessor({"A1": acc_rub, "A2": acc_usd})
        txn = Transaction(
            TransactionType.TRANSFER, 90000, Currency.RUB,
            sender_account_id="A1", receiver_account_id="A2",
        )
        processor.process(txn)
        self.assertEqual(acc_rub.balance, Decimal("0"))
        self.assertEqual(acc_usd.balance, Decimal("1000"))


class TestPremiumOverdraft(unittest.TestCase):

    def test_premium_can_go_negative(self):
        acc = PremiumAccount("VIP", account_id="P1", balance=1000, overdraft_limit=5000, commission=0)
        processor = TransactionProcessor({"P1": acc})
        txn = Transaction(TransactionType.WITHDRAWAL, 3000, Currency.RUB, sender_account_id="P1")
        processor.process(txn)
        self.assertIs(txn.status, TransactionStatus.COMPLETED)
        self.assertEqual(acc.balance, Decimal("-2000"))

    def test_regular_cannot_go_negative(self):
        acc = BankAccount("Regular", account_id="R1", balance=1000)
        processor = TransactionProcessor({"R1": acc})
        txn = Transaction(TransactionType.WITHDRAWAL, 3000, Currency.RUB, sender_account_id="R1")
        processor.process(txn)
        processor.process(txn)
        processor.process(txn)
        self.assertIs(txn.status, TransactionStatus.FAILED)
        self.assertEqual(acc.balance, Decimal("1000"))

    def test_premium_external_no_double_commission(self):
        acc = PremiumAccount("VIP", account_id="P1", balance=10000, commission=100, overdraft_limit=0)
        processor = TransactionProcessor({"P1": acc})
        txn = Transaction(
            TransactionType.TRANSFER, 5000, Currency.RUB,
            sender_account_id="P1", is_external=True,
        )
        processor.process(txn)
        self.assertEqual(txn.commission, Decimal("100"))
        self.assertEqual(acc.balance, Decimal("4900"))

    def test_premium_withdrawal_limit_enforced(self):
        acc = PremiumAccount("VIP", account_id="P1", balance=100000, withdrawal_limit=5000, commission=0, overdraft_limit=0)
        processor = TransactionProcessor({"P1": acc})
        txn = Transaction(TransactionType.WITHDRAWAL, 10000, Currency.RUB, sender_account_id="P1")
        processor.process(txn)
        processor.process(txn)
        processor.process(txn)
        self.assertIs(txn.status, TransactionStatus.FAILED)
        self.assertEqual(acc.balance, Decimal("100000"))

    def test_premium_within_limit_ok(self):
        acc = PremiumAccount("VIP", account_id="P1", balance=100000, withdrawal_limit=50000, commission=0, overdraft_limit=0)
        processor = TransactionProcessor({"P1": acc})
        txn = Transaction(TransactionType.WITHDRAWAL, 30000, Currency.RUB, sender_account_id="P1")
        processor.process(txn)
        self.assertIs(txn.status, TransactionStatus.COMPLETED)
        self.assertEqual(acc.balance, Decimal("70000"))


class TestSavingsViaProcessor(unittest.TestCase):

    def test_savings_min_balance_enforced(self):
        acc = SavingsAccount("Saver", account_id="S1", balance=10000, min_balance=5000)
        processor = TransactionProcessor({"S1": acc})
        txn = Transaction(TransactionType.WITHDRAWAL, 8000, Currency.RUB, sender_account_id="S1")
        processor.process(txn)
        processor.process(txn)
        processor.process(txn)
        self.assertIs(txn.status, TransactionStatus.FAILED)
        self.assertEqual(acc.balance, Decimal("10000"))

    def test_savings_within_min_balance_ok(self):
        acc = SavingsAccount("Saver", account_id="S1", balance=10000, min_balance=5000)
        processor = TransactionProcessor({"S1": acc})
        txn = Transaction(TransactionType.WITHDRAWAL, 4000, Currency.RUB, sender_account_id="S1")
        processor.process(txn)
        self.assertIs(txn.status, TransactionStatus.COMPLETED)
        self.assertEqual(acc.balance, Decimal("6000"))


class TestCommissionCurrency(unittest.TestCase):

    def test_commission_converted_to_sender_currency(self):
        acc = BankAccount("Test", account_id="A1", balance=10000, currency=Currency.USD)
        processor = TransactionProcessor({"A1": acc})
        txn = Transaction(
            TransactionType.TRANSFER, 90000, Currency.RUB,
            sender_account_id="A1", is_external=True,
        )
        processor.process(txn)
        # 90000 RUB -> 1000 USD, commission 1800 RUB -> 20 USD, total 1020
        self.assertIs(txn.status, TransactionStatus.COMPLETED)
        self.assertEqual(acc.balance, Decimal("8980.00"))


class TestProcessQueue(unittest.TestCase):

    def test_process_queue(self):
        acc = BankAccount("Test", account_id="A1", balance=100000)
        processor = TransactionProcessor({"A1": acc})
        queue = TransactionQueue()

        for i in range(10):
            txn = Transaction(
                TransactionType.DEPOSIT, 100, Currency.RUB,
                receiver_account_id="A1",
            )
            queue.add(txn)

        results = processor.process_queue(queue)
        self.assertEqual(len(results), 10)
        completed = [t for t in results if t.status is TransactionStatus.COMPLETED]
        self.assertEqual(len(completed), 10)
        self.assertEqual(acc.balance, Decimal("101000"))

    def test_process_queue_with_delayed(self):
        acc = BankAccount("Test", account_id="A1", balance=10000)
        processor = TransactionProcessor({"A1": acc})
        queue = TransactionQueue()

        past = datetime.now() - timedelta(hours=1)
        future = datetime.now() + timedelta(hours=1)

        txn_ready = Transaction(
            TransactionType.DEPOSIT, 100, Currency.RUB,
            receiver_account_id="A1", scheduled_at=past,
        )
        txn_not_ready = Transaction(
            TransactionType.DEPOSIT, 200, Currency.RUB,
            receiver_account_id="A1", scheduled_at=future,
        )
        queue.add(txn_ready)
        queue.add(txn_not_ready)

        results = processor.process_queue(queue)
        self.assertEqual(len(results), 1)
        self.assertEqual(acc.balance, Decimal("10100"))
        self.assertEqual(queue.delayed_count, 1)

    def test_process_queue_priority_order(self):
        acc = BankAccount("Test", account_id="A1", balance=100000)
        processor = TransactionProcessor({"A1": acc})
        queue = TransactionQueue()

        low = Transaction(TransactionType.DEPOSIT, 1, Currency.RUB, receiver_account_id="A1", priority=Priority.LOW)
        high = Transaction(TransactionType.DEPOSIT, 1, Currency.RUB, receiver_account_id="A1", priority=Priority.HIGH)
        queue.add(low)
        queue.add(high)

        results = processor.process_queue(queue)
        self.assertIs(results[0].priority, Priority.HIGH)
        self.assertIs(results[1].priority, Priority.LOW)


if __name__ == "__main__":
    unittest.main()