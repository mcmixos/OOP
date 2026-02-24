from enum import Enum

from bank_account import (
    BankAccount,
    Currency,
    InsufficientFundsError,
    InvalidOperationError,
)


class AssetType(Enum):

    STOCKS = "stocks"
    BONDS = "bonds"
    ETF = "etf"

ASSET_GROWTH_RATES = {
    AssetType.STOCKS: 0.10,
    AssetType.BONDS: 0.04,
    AssetType.ETF: 0.07,
}


class SavingsAccount(BankAccount):
    """Savings account with minimum balance and monthly interest."""

    def __init__(self, owner, *, min_balance=0, monthly_rate=0.005, **kwargs):
        super().__init__(owner, **kwargs)
        self._min_balance = min_balance
        self._monthly_rate = monthly_rate

    def withdraw(self, amount):
        self._ensure_active()
        self._validate_amount(amount)
        if self._balance - amount < self._min_balance:
            raise InsufficientFundsError()
        self._balance -= amount

    def apply_monthly_interest(self):
        self._ensure_active()
        interest = self._balance * self._monthly_rate
        self._balance += interest
        return interest

    def get_account_info(self):
        info = super().get_account_info()
        info["min_balance"] = self._min_balance
        info["monthly_rate"] = self._monthly_rate
        return info

    def __str__(self):
        last4 = self._account_id[-4:]
        return (
            f"SavingsAccount | {self._owner} | "
            f"****{last4} | {self._status.value} | "
            f"{self._balance:.2f} {self._currency.value} | "
            f"rate {self._monthly_rate:.2%}"
        )


class PremiumAccount(BankAccount):
    """Premium account with higher withdrawal limit, overdraft and fixed commission."""

    def __init__(self, owner, *, withdrawal_limit=1000000,
                 overdraft_limit=50000, commission=100, **kwargs):
        super().__init__(owner, **kwargs)
        self._withdrawal_limit = withdrawal_limit
        self._overdraft_limit = overdraft_limit
        self._commission = commission

    def withdraw(self, amount):
        self._ensure_active()
        self._validate_amount(amount)
        if amount > self._withdrawal_limit:
            raise InvalidOperationError()
        total = amount + self._commission
        if total > self._balance + self._overdraft_limit:
            raise InsufficientFundsError()
        self._balance -= total

    def get_account_info(self):
        info = super().get_account_info()
        info["withdrawal_limit"] = self._withdrawal_limit
        info["overdraft_limit"] = self._overdraft_limit
        info["commission"] = self._commission
        return info

    def __str__(self):
        last4 = self._account_id[-4:]
        return (
            f"PremiumAccount | {self._owner} | "
            f"****{last4} | {self._status.value} | "
            f"{self._balance:.2f} {self._currency.value} | "
            f"limit {self._withdrawal_limit:.0f}"
        )


class InvestmentAccount(BankAccount):
    """Investment account with portfolio of virtual assets."""

    def __init__(self, owner, *, portfolio=None, **kwargs):
        super().__init__(owner, **kwargs)
        self._portfolio: dict[AssetType, float] = portfolio or {}

    def project_yearly_growth(self):
        projected = 0
        for asset_type, amount in self._portfolio.items():
            rate = ASSET_GROWTH_RATES.get(asset_type, 0)
            projected += amount * (1 + rate)
        return projected

    def withdraw(self, amount):
        self._ensure_active()
        self._validate_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError()
        self._balance -= amount

    def get_account_info(self):
        info = super().get_account_info()
        info["portfolio"] = {k.value: v for k, v in self._portfolio.items()}
        info["portfolio_value"] = sum(self._portfolio.values())
        return info

    def __str__(self):
        last4 = self._account_id[-4:]
        portfolio_value = sum(self._portfolio.values())
        return (
            f"InvestmentAccount | {self._owner} | "
            f"****{last4} | {self._status.value} | "
            f"{self._balance:.2f} {self._currency.value} | "
            f"portfolio {portfolio_value:.2f}"
        )


if __name__ == "__main__":
    print("Demo \n")
    print("SavingsAccount\n")

    savings = SavingsAccount(
        "Petrov Ivan",
        balance=50000,
        min_balance=10000,
        monthly_rate=0.01,
    )
    print(f"  {savings}")
    interest = savings.apply_monthly_interest()
    print(f"  Monthly interest: +{interest:.2f}")
    print(f"  {savings}\n")

    print("PremiumAccount\n")

    premium = PremiumAccount(
        "Sidorov Anton",
        balance=200000,
        currency=Currency.USD,
        withdrawal_limit=500000,
        overdraft_limit=100000,
        commission=150,
    )
    print(f"  {premium}")
    premium.withdraw(250000)
    print(f"  After withdrawing 250000 (+150 commission):")
    print(f"  {premium}\n")

    print("InvestmentAccount\n")

    invest = InvestmentAccount(
        "Kozlov Ivan",
        balance=250000,
        portfolio={
            AssetType.STOCKS: 400000,
            AssetType.BONDS: 200000,
            AssetType.ETF: 150000,
        },
    )
    print(f"  {invest}")
    print(f"  Projected yearly growth: {invest.project_yearly_growth():.2f}")