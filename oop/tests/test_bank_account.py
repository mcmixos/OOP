"""Tests for the bank_account module (unittest)."""

import unittest
from decimal import Decimal

from bank_account import (
    AbstractAccount,
    AccountClosedError,
    AccountFrozenError,
    AccountStatus,
    BankAccount,
    Currency,
    InsufficientFundsError,
    InvalidOperationError,
)


class TestAbstractAccount(unittest.TestCase):

    def test_can_instantiate(self):
        acc = AbstractAccount("Test Owner")
        self.assertEqual(acc.owner, "Test Owner")

    def test_deposit_raises_not_implemented(self):
        acc = AbstractAccount("Test Owner")
        with self.assertRaises(NotImplementedError):
            acc.deposit(100)

    def test_withdraw_raises_not_implemented(self):
        acc = AbstractAccount("Test Owner")
        with self.assertRaises(NotImplementedError):
            acc.withdraw(100)

    def test_get_account_info_raises_not_implemented(self):
        acc = AbstractAccount("Test Owner")
        with self.assertRaises(NotImplementedError):
            acc.get_account_info()


class TestBankAccountCreation(unittest.TestCase):

    def test_defaults(self):
        acc = BankAccount("Ivanov")
        self.assertEqual(acc.owner, "Ivanov")
        self.assertEqual(acc.balance, Decimal("0"))
        self.assertIs(acc.status, AccountStatus.ACTIVE)
        self.assertIs(acc.currency, Currency.RUB)

    def test_custom_params(self):
        acc = BankAccount(
            "Smith",
            account_id="ABCD1234",
            balance=500,
            status=AccountStatus.FROZEN,
            currency=Currency.USD,
        )
        self.assertEqual(acc.account_id, "ABCD1234")
        self.assertEqual(acc.balance, Decimal("500"))
        self.assertIs(acc.status, AccountStatus.FROZEN)
        self.assertIs(acc.currency, Currency.USD)

    def test_auto_generated_id_length(self):
        acc = BankAccount("Test")
        self.assertEqual(len(acc.account_id), 8)

    def test_auto_generated_id_is_hex(self):
        acc = BankAccount("Test")
        self.assertRegex(acc.account_id, r"^[0-9a-f]{8}$")

    def test_auto_generated_ids_are_unique(self):
        ids = {BankAccount("Test").account_id for _ in range(100)}
        self.assertEqual(len(ids), 100)

    def test_explicit_id_preserved(self):
        acc = BankAccount("Test", account_id="MY_ID_123")
        self.assertEqual(acc.account_id, "MY_ID_123")

    def test_empty_owner_raises(self):
        with self.assertRaises(InvalidOperationError):
            BankAccount("")

    def test_whitespace_owner_raises(self):
        with self.assertRaises(InvalidOperationError):
            BankAccount("   ")

    def test_non_string_owner_raises(self):
        with self.assertRaises(InvalidOperationError):
            BankAccount(123)

    def test_negative_balance_raises(self):
        with self.assertRaises(InvalidOperationError):
            BankAccount("Test", balance=-1)

    def test_non_numeric_balance_raises(self):
        with self.assertRaises(InvalidOperationError):
            BankAccount("Test", balance="abc")

    def test_invalid_status_raises(self):
        with self.assertRaises(InvalidOperationError):
            BankAccount("Test", status="active")

    def test_invalid_currency_raises(self):
        with self.assertRaises(InvalidOperationError):
            BankAccount("Test", currency="RUB")

    def test_integer_balance_accepted(self):
        acc = BankAccount("Test", balance=100)
        self.assertEqual(acc.balance, Decimal("100"))

    def test_decimal_balance_accepted(self):
        acc = BankAccount("Test", balance=Decimal("99.99"))
        self.assertEqual(acc.balance, Decimal("99.99"))


class TestDeposit(unittest.TestCase):

    def test_deposit_increases_balance(self):
        acc = BankAccount("Test", balance=100)
        acc.deposit(50)
        self.assertEqual(acc.balance, Decimal("150"))

    def test_deposit_integer(self):
        acc = BankAccount("Test")
        acc.deposit(200)
        self.assertEqual(acc.balance, Decimal("200"))

    def test_deposit_small_amount(self):
        acc = BankAccount("Test")
        acc.deposit(Decimal("0.01"))
        self.assertEqual(acc.balance, Decimal("0.01"))

    def test_deposit_zero_raises(self):
        acc = BankAccount("Test")
        with self.assertRaises(InvalidOperationError):
            acc.deposit(0)

    def test_deposit_negative_raises(self):
        acc = BankAccount("Test")
        with self.assertRaises(InvalidOperationError):
            acc.deposit(-10)

    def test_deposit_non_numeric_raises(self):
        acc = BankAccount("Test")
        with self.assertRaises(InvalidOperationError):
            acc.deposit("100")

    def test_deposit_frozen_raises(self):
        acc = BankAccount("Test", status=AccountStatus.FROZEN)
        with self.assertRaises(AccountFrozenError):
            acc.deposit(100)

    def test_deposit_closed_raises(self):
        acc = BankAccount("Test", status=AccountStatus.CLOSED)
        with self.assertRaises(AccountClosedError):
            acc.deposit(100)


class TestWithdraw(unittest.TestCase):

    def test_withdraw_decreases_balance(self):
        acc = BankAccount("Test", balance=500)
        acc.withdraw(200)
        self.assertEqual(acc.balance, Decimal("300"))

    def test_withdraw_entire_balance(self):
        acc = BankAccount("Test", balance=100)
        acc.withdraw(100)
        self.assertEqual(acc.balance, Decimal("0"))

    def test_withdraw_integer(self):
        acc = BankAccount("Test", balance=100)
        acc.withdraw(30)
        self.assertEqual(acc.balance, Decimal("70"))

    def test_withdraw_insufficient_funds_raises(self):
        acc = BankAccount("Test", balance=50)
        with self.assertRaises(InsufficientFundsError):
            acc.withdraw(100)

    def test_withdraw_zero_raises(self):
        acc = BankAccount("Test", balance=100)
        with self.assertRaises(InvalidOperationError):
            acc.withdraw(0)

    def test_withdraw_negative_raises(self):
        acc = BankAccount("Test", balance=100)
        with self.assertRaises(InvalidOperationError):
            acc.withdraw(-10)

    def test_withdraw_non_numeric_raises(self):
        acc = BankAccount("Test", balance=100)
        with self.assertRaises(InvalidOperationError):
            acc.withdraw("50")

    def test_withdraw_frozen_raises(self):
        acc = BankAccount("Test", balance=100, status=AccountStatus.FROZEN)
        with self.assertRaises(AccountFrozenError):
            acc.withdraw(10)

    def test_withdraw_closed_raises(self):
        acc = BankAccount("Test", balance=100, status=AccountStatus.CLOSED)
        with self.assertRaises(AccountClosedError):
            acc.withdraw(10)


class TestStatusCheckOrder(unittest.TestCase):

    def test_frozen_deposit_invalid_amount_raises_frozen(self):
        acc = BankAccount("Test", status=AccountStatus.FROZEN)
        with self.assertRaises(AccountFrozenError):
            acc.deposit(-999)

    def test_closed_withdraw_invalid_amount_raises_closed(self):
        acc = BankAccount("Test", balance=100, status=AccountStatus.CLOSED)
        with self.assertRaises(AccountClosedError):
            acc.withdraw(-1)


class TestSetStatus(unittest.TestCase):

    def test_set_status_frozen(self):
        acc = BankAccount("Test", balance=100)
        acc.set_status(AccountStatus.FROZEN)
        self.assertIs(acc.status, AccountStatus.FROZEN)

    def test_set_status_closed(self):
        acc = BankAccount("Test", balance=100)
        acc.set_status(AccountStatus.CLOSED)
        self.assertIs(acc.status, AccountStatus.CLOSED)

    def test_set_status_active(self):
        acc = BankAccount("Test", balance=100, status=AccountStatus.FROZEN)
        acc.set_status(AccountStatus.ACTIVE)
        self.assertIs(acc.status, AccountStatus.ACTIVE)

    def test_set_status_invalid_raises(self):
        acc = BankAccount("Test")
        with self.assertRaises(InvalidOperationError):
            acc.set_status("active")


class TestGetAccountInfo(unittest.TestCase):

    def test_info_keys(self):
        acc = BankAccount("Test", currency=Currency.EUR)
        info = acc.get_account_info()
        self.assertEqual(
            set(info.keys()),
            {"account_id", "owner", "balance", "currency", "status"},
        )

    def test_info_values_are_serializable(self):
        acc = BankAccount("Test", account_id="ABCD1234", balance=42, currency=Currency.USD)
        info = acc.get_account_info()
        self.assertEqual(info["balance"], "42")
        self.assertIsInstance(info["balance"], str)


class TestStringRepresentation(unittest.TestCase):

    def test_str_contains_required_parts(self):
        acc = BankAccount(
            "Sidorov",
            account_id="ABCD5678",
            balance=1234.56,
            currency=Currency.EUR,
        )
        s = str(acc)
        for part in ("BankAccount", "Sidorov", "5678", "active", "1234.56", "EUR"):
            self.assertIn(part, s)

    def test_str_masks_id(self):
        acc = BankAccount("Test", account_id="LONGID12345678")
        s = str(acc)
        self.assertIn("****5678", s)
        self.assertNotIn("LONGID12345678", s)

    def test_repr_contains_class_name(self):
        acc = BankAccount("Test")
        self.assertTrue(repr(acc).startswith("BankAccount("))


class TestExceptionHierarchy(unittest.TestCase):

    def test_all_inherit_from_exception(self):
        for exc_cls in (
            AccountFrozenError,
            AccountClosedError,
            InvalidOperationError,
            InsufficientFundsError,
        ):
            self.assertTrue(issubclass(exc_cls, Exception))

    def test_all_can_be_raised_and_caught(self):
        for exc_cls in (
            AccountFrozenError,
            AccountClosedError,
            InvalidOperationError,
            InsufficientFundsError,
        ):
            with self.assertRaises(exc_cls):
                raise exc_cls("test message")


class TestEnums(unittest.TestCase):

    def test_account_statuses(self):
        self.assertEqual(
            {s.value for s in AccountStatus},
            {"active", "frozen", "closed"},
        )

    def test_currencies(self):
        self.assertEqual(
            {c.value for c in Currency},
            {"RUB", "USD", "EUR", "KZT", "CNY"},
        )


if __name__ == "__main__":
    unittest.main()
