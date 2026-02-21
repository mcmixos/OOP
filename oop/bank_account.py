import uuid
from enum import Enum


class AccountStatus(Enum):

    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"

class Currency(Enum):

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    KZT = "KZT"
    CNY = "CNY"


class AccountError(Exception):
    """Base exception for account operations"""

class AccountFrozenError(AccountError):
    """Operation rejected — account is frozen"""

class AccountClosedError(AccountError):
    """Operation rejected — account is closed"""

class InvalidOperationError(AccountError):
    """Invalid operation"""

class InsufficientFundsError(AccountError):
    """Not enough funds"""


class AbstractAccount:
    """Abstract bank account"""

    def __init__(
        self,
        owner: str,
        *,
        account_id: str | None = None,
        balance: float = 0.0,
        status: AccountStatus = AccountStatus.ACTIVE,
    ) -> None:
        self._account_id: str = account_id or uuid.uuid4().hex[:8]
        self._owner: str = owner
        self._balance: float = balance
        self._status: AccountStatus = status

    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def status(self) -> AccountStatus:
        return self._status

    def deposit(self, amount: float) -> None:
        raise NotImplementedError

    def withdraw(self, amount: float) -> None:
        raise NotImplementedError

    def get_account_info(self) -> dict:
        raise NotImplementedError


class BankAccount(AbstractAccount):
    """Bank account with validation, statuses and currency support"""
    
    def __init__(
        self,
        owner: str,
        *,
        account_id: str | None = None,
        balance: float = 0.0,
        status: AccountStatus = AccountStatus.ACTIVE,
        currency: Currency = Currency.RUB,
    ) -> None:
        if not isinstance(owner, str) or not owner.strip():
            raise InvalidOperationError()
        if not isinstance(balance, (int, float)):
            raise InvalidOperationError()
        if balance < 0:
            raise InvalidOperationError()
        self._validate_type(status, AccountStatus, "status")
        self._validate_type(currency, Currency, "currency")

        super().__init__(
            owner,
            account_id=account_id,
            balance=balance,
            status=status,
        )
        self._currency: Currency = currency

    def __str__(self) -> str:
        last4 = self._account_id[-4:]
        return (
            f"BankAccount | {self._owner} | "
            f"****{last4} | {self._status.value} | "
            f"{self._balance:.2f} {self._currency.value}"
        )

    def __repr__(self) -> str:
        return (
            f"BankAccount(owner={self._owner!r}, account_id={self._account_id!r}, "
            f"balance={self._balance}, status={self._status!r}, "
            f"currency={self._currency!r})"
        )

    def _ensure_active(self) -> None:
        if self._status is AccountStatus.FROZEN:
            raise AccountFrozenError()
        if self._status is AccountStatus.CLOSED:
            raise AccountClosedError()

    @staticmethod
    def _validate_amount(amount: float) -> None:
        if not isinstance(amount, (int, float)):
            raise InvalidOperationError()
        if amount <= 0:
            raise InvalidOperationError()

    @staticmethod
    def _validate_type(value, expected_type: type, name: str) -> None:
        if not isinstance(value, expected_type):
            raise InvalidOperationError()

    @property
    def currency(self) -> Currency:
        return self._currency


    def deposit(self, amount: float) -> None:
        self._ensure_active()
        self._validate_amount(amount)
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        self._ensure_active()
        self._validate_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError()
        self._balance -= amount

    def get_account_info(self) -> dict:
        return {
            "account_id": self._account_id,
            "owner": self._owner,
            "balance": self._balance,
            "currency": self._currency.value,
            "status": self._status.value,
        }


if __name__ == "__main__":
    print("Demo \n")

    acc = BankAccount("Petrov Ivan", balance=10000.0, currency=Currency.RUB)
    print(f"Active account created:\n  {acc}\n")

    acc.deposit(500)
    print(f"After depositing 500:\n  {acc}\n")

    acc.withdraw(200)
    print(f"After withdrawing 200:\n  {acc}\n")

    frozen = BankAccount(
        "Ivanov Petr",
        balance=5000.0,
        status=AccountStatus.FROZEN,
        currency=Currency.USD,
    )
    print(f"Frozen account created:\n  {frozen}\n")

    for operation_name, operation in [("deposit", lambda: frozen.deposit(100)),
                                      ("withdraw", lambda: frozen.withdraw(50))]:
        try:
            operation()
        except AccountFrozenError as exc:
            print(f"Attempted {operation_name} on frozen account: {exc}")