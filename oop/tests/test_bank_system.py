"""Tests for bank module."""

import unittest
from datetime import date
from decimal import Decimal

from bank_account import AccountStatus, BankAccount, Currency, InvalidOperationError
from bank_system import (
    AuthenticationError,
    Bank,
    Client,
    ClientBlockedError,
    NightOperationError,
)


class TestClientCreation(unittest.TestCase):

    def test_valid_client(self):
        c = Client("Test Name", "C001", date(1990, 1, 1), "1234")
        self.assertEqual(c.name, "Test Name")
        self.assertEqual(c.client_id, "C001")
        self.assertEqual(c.pin, "1234")
        self.assertEqual(c.account_ids, [])
        self.assertFalse(c.is_blocked)
        self.assertEqual(c.failed_attempts, 0)
        self.assertEqual(c.status, "active")

    def test_status_reflects_blocked(self):
        c = Client("Test", "C001", date(1990, 1, 1), "1234")
        self.assertEqual(c.status, "active")
        c.is_blocked = True
        self.assertEqual(c.status, "blocked")

    def test_with_contacts(self):
        c = Client("Test", "C001", date(1990, 1, 1), "1234", contacts=["C002", "C003"])
        self.assertEqual(c.contacts, ["C002", "C003"])

    def test_underage_raises(self):
        today = date.today()
        underage_dob = date(today.year - 17, today.month, today.day)
        with self.assertRaises(InvalidOperationError):
            Client("Test", "C001", underage_dob, "1234")

    def test_exactly_18_accepted(self):
        today = date.today()
        dob_18 = date(today.year - 18, today.month, today.day)
        c = Client("Test", "C001", dob_18, "1234")
        self.assertEqual(c.name, "Test")

    def test_empty_name_raises(self):
        with self.assertRaises(InvalidOperationError):
            Client("", "C001", date(1990, 1, 1), "1234")

    def test_empty_id_raises(self):
        with self.assertRaises(InvalidOperationError):
            Client("Test", "", date(1990, 1, 1), "1234")

    def test_pin_not_4_digits_raises(self):
        with self.assertRaises(InvalidOperationError):
            Client("Test", "C001", date(1990, 1, 1), "123")

    def test_pin_non_numeric_raises(self):
        with self.assertRaises(InvalidOperationError):
            Client("Test", "C001", date(1990, 1, 1), "abcd")

    def test_str(self):
        c = Client("Test Name", "C001", date(1990, 1, 1), "1234")
        s = str(c)
        self.assertIn("Test Name", s)
        self.assertIn("C001", s)


class TestBankClients(unittest.TestCase):

    def setUp(self):
        self.bank = Bank()
        self.client = Client("Test", "C001", date(1990, 1, 1), "1234")

    def test_add_client(self):
        self.bank.add_client(self.client, is_night=False)
        self.assertIn("C001", self.bank._clients)

    def test_add_duplicate_raises(self):
        self.bank.add_client(self.client, is_night=False)
        with self.assertRaises(InvalidOperationError):
            self.bank.add_client(self.client, is_night=False)


class TestAuthentication(unittest.TestCase):

    def setUp(self):
        self.bank = Bank()
        self.client = Client("Test", "C001", date(1990, 1, 1), "1234")
        self.bank.add_client(self.client, is_night=False)

    def test_correct_pin(self):
        result = self.bank.authenticate_client("C001", "1234")
        self.assertEqual(result.name, "Test")

    def test_wrong_pin_raises(self):
        with self.assertRaises(AuthenticationError):
            self.bank.authenticate_client("C001", "0000")

    def test_wrong_pin_increments_counter(self):
        try:
            self.bank.authenticate_client("C001", "0000")
        except AuthenticationError:
            pass
        self.assertEqual(self.client.failed_attempts, 1)

    def test_correct_pin_resets_counter(self):
        try:
            self.bank.authenticate_client("C001", "0000")
        except AuthenticationError:
            pass
        self.bank.authenticate_client("C001", "1234")
        self.assertEqual(self.client.failed_attempts, 0)

    def test_three_failures_blocks(self):
        for _ in range(3):
            try:
                self.bank.authenticate_client("C001", "0000")
            except (AuthenticationError, ClientBlockedError):
                pass
        self.assertTrue(self.client.is_blocked)

    def test_blocked_client_raises(self):
        for _ in range(3):
            try:
                self.bank.authenticate_client("C001", "0000")
            except (AuthenticationError, ClientBlockedError):
                pass
        with self.assertRaises(ClientBlockedError):
            self.bank.authenticate_client("C001", "1234")

    def test_unknown_client_raises(self):
        with self.assertRaises(AuthenticationError):
            self.bank.authenticate_client("UNKNOWN", "1234")


class TestBankAccounts(unittest.TestCase):

    def setUp(self):
        self.bank = Bank()
        self.client = Client("Test", "C001", date(1990, 1, 1), "1234")
        self.bank.add_client(self.client, is_night=False)
        self.acc = BankAccount("Test", account_id="ACC001", balance=10000)

    def test_open_account(self):
        self.bank.open_account("C001", self.acc, is_night=False)
        self.assertIn("ACC001", self.client.account_ids)
        self.assertIn("ACC001", self.bank._accounts)

    def test_open_duplicate_account_raises(self):
        self.bank.open_account("C001", self.acc, is_night=False)
        with self.assertRaises(InvalidOperationError):
            self.bank.open_account("C001", self.acc, is_night=False)

    def test_open_account_unknown_client_raises(self):
        with self.assertRaises(InvalidOperationError):
            self.bank.open_account("UNKNOWN", self.acc, is_night=False)

    def test_close_account(self):
        self.bank.open_account("C001", self.acc, is_night=False)
        self.bank.close_account("ACC001", is_night=False)
        self.assertIs(self.acc.status, AccountStatus.CLOSED)

    def test_close_unknown_account_raises(self):
        with self.assertRaises(InvalidOperationError):
            self.bank.close_account("UNKNOWN", is_night=False)

    def test_freeze_account(self):
        self.bank.open_account("C001", self.acc, is_night=False)
        self.bank.freeze_account("ACC001", is_night=False)
        self.assertIs(self.acc.status, AccountStatus.FROZEN)

    def test_unfreeze_account(self):
        self.bank.open_account("C001", self.acc, is_night=False)
        self.bank.freeze_account("ACC001", is_night=False)
        self.bank.unfreeze_account("ACC001", is_night=False)
        self.assertIs(self.acc.status, AccountStatus.ACTIVE)

    def test_search_accounts(self):
        self.bank.open_account("C001", self.acc, is_night=False)
        results = self.bank.search_accounts("C001")
        self.assertEqual(len(results), 1)
        self.assertIs(results[0], self.acc)

    def test_search_unknown_client_raises(self):
        with self.assertRaises(InvalidOperationError):
            self.bank.search_accounts("UNKNOWN")


class TestTransfers(unittest.TestCase):

    def setUp(self):
        self.bank = Bank(suspicious_threshold=50000)
        c1 = Client("Sender", "C001", date(1990, 1, 1), "1234", contacts=["C002"])
        c2 = Client("Receiver", "C002", date(1985, 6, 15), "5678")
        self.bank.add_client(c1, is_night=False)
        self.bank.add_client(c2, is_night=False)
        self.acc1 = BankAccount("Sender", account_id="ACC001", balance=200000)
        self.acc2 = BankAccount("Receiver", account_id="ACC002", balance=10000)
        self.bank.open_account("C001", self.acc1, is_night=False)
        self.bank.open_account("C002", self.acc2, is_night=False)

    def test_transfer_moves_funds(self):
        self.bank.transfer(
            "ACC001", "ACC002", 5000,
            sender_client_id="C001", receiver_client_id="C002", is_night=False,
        )
        self.assertEqual(self.acc1.balance, Decimal("195000"))
        self.assertEqual(self.acc2.balance, Decimal("15000"))

    def test_transfer_to_contact_not_suspicious(self):
        self.bank.transfer(
            "ACC001", "ACC002", 60000,
            sender_client_id="C001", receiver_client_id="C002", is_night=False,
        )
        self.assertEqual(len(self.bank.suspicious_log), 0)

    def test_transfer_to_non_contact_above_threshold_suspicious(self):
        self.bank.transfer(
            "ACC002", "ACC001", 5000,
            sender_client_id="C002", receiver_client_id="C001", is_night=False,
        )
        # 5000 < 50000 threshold - not suspicious
        self.assertEqual(len(self.bank.suspicious_log), 0)

        self.bank.transfer(
            "ACC002", "ACC001", 5000,
            sender_client_id="C002", receiver_client_id="C001", is_night=False,
        )
        # below threshold
        self.assertEqual(len(self.bank.suspicious_log), 0)

    def test_transfer_non_contact_above_threshold_logged(self):
        self.acc2.deposit(100000)
        self.bank.transfer(
            "ACC002", "ACC001", 60000,
            sender_client_id="C002", receiver_client_id="C001", is_night=False,
        )
        # C002 has no contacts, 60000 >= 50000 - suspicious
        self.assertEqual(len(self.bank.suspicious_log), 1)
        self.assertEqual(self.bank.suspicious_log[0]["sender"], "C002")

    def test_transfer_unknown_account_raises(self):
        with self.assertRaises(InvalidOperationError):
            self.bank.transfer(
                "UNKNOWN", "ACC002", 100,
                sender_client_id="C001", receiver_client_id="C002", is_night=False,
            )

    def test_transfer_from_non_owned_account_raises(self):
        with self.assertRaises(InvalidOperationError):
            self.bank.transfer(
                "ACC001", "ACC002", 100,
                sender_client_id="C002", receiver_client_id="C001", is_night=False,
            )

    def test_transfer_atomic_on_deposit_failure(self):
        self.bank.freeze_account("ACC002", is_night=False)
        original_balance = self.acc1.balance
        with self.assertRaises(Exception):
            self.bank.transfer(
                "ACC001", "ACC002", 1000,
                sender_client_id="C001", receiver_client_id="C002", is_night=False,
            )
        # balance restored
        self.assertEqual(self.acc1.balance, original_balance)


class TestNightOperations(unittest.TestCase):

    def setUp(self):
        self.bank = Bank()
        self.client = Client("Test", "C001", date(1990, 1, 1), "1234")

    def test_add_client_at_night_raises(self):
        with self.assertRaises(NightOperationError):
            self.bank.add_client(self.client, is_night=True)

    def test_add_client_daytime_ok(self):
        self.bank.add_client(self.client, is_night=False)
        self.assertIn("C001", self.bank._clients)

    def test_open_account_at_night_raises(self):
        self.bank.add_client(self.client, is_night=False)
        acc = BankAccount("Test", account_id="ACC001")
        with self.assertRaises(NightOperationError):
            self.bank.open_account("C001", acc, is_night=True)

    def test_close_account_at_night_raises(self):
        self.bank.add_client(self.client, is_night=False)
        acc = BankAccount("Test", account_id="ACC001")
        self.bank.open_account("C001", acc, is_night=False)
        with self.assertRaises(NightOperationError):
            self.bank.close_account("ACC001", is_night=True)

    def test_freeze_at_night_raises(self):
        self.bank.add_client(self.client, is_night=False)
        acc = BankAccount("Test", account_id="ACC001")
        self.bank.open_account("C001", acc, is_night=False)
        with self.assertRaises(NightOperationError):
            self.bank.freeze_account("ACC001", is_night=True)

    def test_transfer_at_night_raises(self):
        self.bank.add_client(self.client, is_night=False)
        c2 = Client("Other", "C002", date(1990, 1, 1), "5678")
        self.bank.add_client(c2, is_night=False)
        acc1 = BankAccount("Test", account_id="ACC001", balance=10000)
        acc2 = BankAccount("Other", account_id="ACC002", balance=10000)
        self.bank.open_account("C001", acc1, is_night=False)
        self.bank.open_account("C002", acc2, is_night=False)
        with self.assertRaises(NightOperationError):
            self.bank.transfer(
                "ACC001", "ACC002", 100,
                sender_client_id="C001", receiver_client_id="C002", is_night=True,
            )


class TestReports(unittest.TestCase):

    def setUp(self):
        self.bank = Bank()
        c1 = Client("Rich", "C001", date(1990, 1, 1), "1234")
        c2 = Client("Poor", "C002", date(1985, 6, 15), "5678")
        self.bank.add_client(c1, is_night=False)
        self.bank.add_client(c2, is_night=False)
        self.bank.open_account("C001", BankAccount("Rich", account_id="A1", balance=50000), is_night=False)
        self.bank.open_account("C001", BankAccount("Rich", account_id="A2", balance=30000), is_night=False)
        self.bank.open_account("C002", BankAccount("Poor", account_id="A3", balance=10000), is_night=False)

    def test_get_total_balance(self):
        self.assertEqual(self.bank.get_total_balance("C001"), Decimal("80000"))
        self.assertEqual(self.bank.get_total_balance("C002"), Decimal("10000"))

    def test_get_total_balance_unknown_raises(self):
        with self.assertRaises(InvalidOperationError):
            self.bank.get_total_balance("UNKNOWN")

    def test_get_clients_ranking(self):
        ranking = self.bank.get_clients_ranking()
        self.assertEqual(ranking[0][0], "C001")
        self.assertEqual(ranking[1][0], "C002")
        self.assertEqual(ranking[0][1], Decimal("80000"))

    def test_ranking_empty_bank(self):
        empty_bank = Bank()
        self.assertEqual(empty_bank.get_clients_ranking(), [])


if __name__ == "__main__":
    unittest.main()