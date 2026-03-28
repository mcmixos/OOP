"""Tests for bank_account_types module"""

import unittest
from decimal import Decimal

from bank_account import AccountStatus, Currency, InsufficientFundsError, InvalidOperationError, AccountFrozenError
from bank_account_types import (
    AssetType,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)


class TestSavingsAccount(unittest.TestCase):

    def test_withdraw_respects_min_balance(self):
        acc = SavingsAccount("Test", balance=5000, min_balance=1000)
        acc.withdraw(4000)
        self.assertEqual(acc.balance, Decimal("1000"))

    def test_withdraw_below_min_balance_raises(self):
        acc = SavingsAccount("Test", balance=5000, min_balance=1000)
        with self.assertRaises(InsufficientFundsError):
            acc.withdraw(4500)

    def test_apply_monthly_interest(self):
        acc = SavingsAccount("Test", balance=10000, monthly_rate=0.01)
        interest = acc.apply_monthly_interest()
        self.assertEqual(interest, Decimal("100"))
        self.assertEqual(acc.balance, Decimal("10100"))

    def test_interest_on_zero_balance(self):
        acc = SavingsAccount("Test", balance=0, monthly_rate=0.01)
        interest = acc.apply_monthly_interest()
        self.assertEqual(interest, Decimal("0"))

    def test_frozen_raises(self):
        acc = SavingsAccount("Test", balance=5000, status=AccountStatus.FROZEN)
        with self.assertRaises(AccountFrozenError):
            acc.withdraw(100)

    def test_get_account_info_serializable(self):
        acc = SavingsAccount("Test", balance=1000, min_balance=500, monthly_rate=0.02)
        info = acc.get_account_info()
        self.assertEqual(info["min_balance"], "500")
        self.assertEqual(info["monthly_rate"], "0.02")
        self.assertIsInstance(info["balance"], str)

    def test_str(self):
        acc = SavingsAccount("Test", balance=1000, monthly_rate=0.01)
        self.assertIn("SavingsAccount", str(acc))

    def test_negative_min_balance_raises(self):
        with self.assertRaises(InvalidOperationError):
            SavingsAccount("Test", min_balance=-1)

    def test_negative_rate_raises(self):
        with self.assertRaises(InvalidOperationError):
            SavingsAccount("Test", monthly_rate=-0.01)

    def test_balance_below_min_raises(self):
        with self.assertRaises(InvalidOperationError):
            SavingsAccount("Test", balance=500, min_balance=1000)


class TestPremiumAccount(unittest.TestCase):

    def test_withdraw_with_commission(self):
        acc = PremiumAccount("Test", balance=10000, commission=100)
        acc.withdraw(5000)
        self.assertEqual(acc.balance, Decimal("4900"))

    def test_withdraw_over_limit_raises(self):
        acc = PremiumAccount("Test", balance=100000, withdrawal_limit=1000)
        with self.assertRaises(InvalidOperationError):
            acc.withdraw(5000)

    def test_overdraft_allows_negative_balance(self):
        acc = PremiumAccount("Test", balance=1000, overdraft_limit=5000, commission=0)
        acc.withdraw(3000)
        self.assertEqual(acc.balance, Decimal("-2000"))

    def test_overdraft_exceeded_raises(self):
        acc = PremiumAccount("Test", balance=1000, overdraft_limit=500, commission=0)
        with self.assertRaises(InsufficientFundsError):
            acc.withdraw(2000)

    def test_commission_counted_in_overdraft(self):
        acc = PremiumAccount("Test", balance=0, overdraft_limit=1000, commission=100)
        acc.withdraw(900)
        self.assertEqual(acc.balance, Decimal("-1000"))

    def test_frozen_raises(self):
        acc = PremiumAccount("Test", balance=10000, status=AccountStatus.FROZEN)
        with self.assertRaises(AccountFrozenError):
            acc.withdraw(100)

    def test_get_account_info_serializable(self):
        acc = PremiumAccount("Test", balance=1000)
        info = acc.get_account_info()
        self.assertIsInstance(info["withdrawal_limit"], str)
        self.assertIsInstance(info["overdraft_limit"], str)
        self.assertIsInstance(info["commission"], str)

    def test_str(self):
        acc = PremiumAccount("Test", withdrawal_limit=500000)
        self.assertIn("PremiumAccount", str(acc))

    def test_zero_withdrawal_limit_raises(self):
        with self.assertRaises(InvalidOperationError):
            PremiumAccount("Test", withdrawal_limit=0)

    def test_negative_overdraft_raises(self):
        with self.assertRaises(InvalidOperationError):
            PremiumAccount("Test", overdraft_limit=-1)

    def test_negative_commission_raises(self):
        with self.assertRaises(InvalidOperationError):
            PremiumAccount("Test", commission=-5)


class TestInvestmentAccount(unittest.TestCase):

    def test_empty_portfolio_by_default(self):
        acc = InvestmentAccount("Test", balance=10000)
        info = acc.get_account_info()
        self.assertEqual(info["portfolio"], {})

    def test_portfolio_via_init(self):
        acc = InvestmentAccount(
            "Test", balance=10000,
            portfolio={AssetType.STOCKS: 5000, AssetType.BONDS: 3000},
        )
        info = acc.get_account_info()
        self.assertEqual(info["portfolio"], {"stocks": "5000", "bonds": "3000"})
        self.assertEqual(info["portfolio_value"], "8000")

    def test_project_yearly_growth(self):
        acc = InvestmentAccount(
            "Test", balance=10000,
            portfolio={AssetType.STOCKS: 10000, AssetType.BONDS: 10000},
        )
        self.assertEqual(acc.project_yearly_growth(), Decimal("1400"))

    def test_project_empty_portfolio(self):
        acc = InvestmentAccount("Test", balance=10000)
        self.assertEqual(acc.project_yearly_growth(), Decimal("0"))

    def test_withdraw(self):
        acc = InvestmentAccount("Test", balance=10000)
        acc.withdraw(3000)
        self.assertEqual(acc.balance, Decimal("7000"))

    def test_withdraw_exceeds_balance_raises(self):
        acc = InvestmentAccount("Test", balance=1000)
        with self.assertRaises(InsufficientFundsError):
            acc.withdraw(5000)

    def test_get_account_info_serializable(self):
        acc = InvestmentAccount(
            "Test", balance=10000,
            portfolio={AssetType.STOCKS: 2000},
        )
        info = acc.get_account_info()
        self.assertIsInstance(info["portfolio"]["stocks"], str)
        self.assertIsInstance(info["portfolio_value"], str)

    def test_str(self):
        acc = InvestmentAccount("Test", balance=10000)
        self.assertIn("InvestmentAccount", str(acc))

    def test_invalid_portfolio_key_raises(self):
        with self.assertRaises(InvalidOperationError):
            InvestmentAccount("Test", balance=10000, portfolio={"stocks": 5000})

    def test_valid_portfolio_key_accepted(self):
        acc = InvestmentAccount(
            "Test", balance=10000,
            portfolio={AssetType.ETF: 1000},
        )
        self.assertEqual(acc.project_yearly_growth(), Decimal("70"))


class TestPolymorphism(unittest.TestCase):

    def test_all_types_withdraw(self):
        accounts = [
            SavingsAccount("A", balance=10000),
            PremiumAccount("B", balance=10000),
            InvestmentAccount("C", balance=10000),
        ]
        for acc in accounts:
            acc.withdraw(100)
            self.assertLess(acc.balance, 10000)

    def test_all_types_get_account_info(self):
        accounts = [
            SavingsAccount("A", balance=1000),
            PremiumAccount("B", balance=1000),
            InvestmentAccount("C", balance=1000),
        ]
        for acc in accounts:
            info = acc.get_account_info()
            self.assertIn("account_id", info)
            self.assertIn("balance", info)
            self.assertIsInstance(info["balance"], str)

    def test_all_types_str(self):
        accounts = [
            SavingsAccount("A", balance=1000),
            PremiumAccount("B", balance=1000),
            InvestmentAccount("C", balance=1000),
        ]
        for acc in accounts:
            self.assertIsInstance(str(acc), str)

    def test_deposit_inherited(self):
        accounts = [
            SavingsAccount("A", balance=1000),
            PremiumAccount("B", balance=1000),
            InvestmentAccount("C", balance=1000),
        ]
        for acc in accounts:
            acc.deposit(500)
            self.assertEqual(acc.balance, Decimal("1500"))


if __name__ == "__main__":
    unittest.main()
