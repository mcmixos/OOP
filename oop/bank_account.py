import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
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


def to_decimal(value) -> Decimal:
    """Convert a numeric value to Decimal. Rejects bool and str."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise InvalidOperationError()
    return Decimal(str(value))


class AbstractAccount(ABC):
    """Abstract bank account"""

    def __init__(
        self,
        owner: str,
        *,
        account_id: str | None = None,
        balance: Decimal = Decimal("0"),
        status: AccountStatus = AccountStatus.ACTIVE,
    ) -> None:
        self._account_id: str = account_id or uuid.uuid4().hex[:8]
        self._owner: str = owner
        self._balance: Decimal = balance
        self._status: AccountStatus = status

    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def balance(self) -> Decimal:
        return self._balance

    @property
    def status(self) -> AccountStatus:
        return self._status

    @abstractmethod
    def deposit(self, amount: int | float | Decimal) -> None: ...

    @abstractmethod
    def withdraw(self, amount: int | float | Decimal) -> None: ...

    @abstractmethod
    def get_account_info(self) -> dict: ...


class BankAccount(AbstractAccount):
    """Bank account with validation, statuses and currency support"""
    
    def __init__(
        self,
        owner: str,
        *,
        account_id: str | None = None,
        balance=0,
        status: AccountStatus = AccountStatus.ACTIVE,
        currency: Currency = Currency.RUB,
    ) -> None:
        if not isinstance(owner, str) or not owner.strip():
            raise InvalidOperationError()
        balance = to_decimal(balance)
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

    def set_status(self, status: AccountStatus) -> None:
        self._validate_type(status, AccountStatus, "status")
        self._status = status

    @staticmethod
    def _validate_amount(amount: int | float | Decimal) -> Decimal:
        amount = to_decimal(amount)
        if amount <= 0:
            raise InvalidOperationError()
        return amount

    @staticmethod
    def _validate_type(value, expected_type: type, name: str) -> None:
        if not isinstance(value, expected_type):
            raise InvalidOperationError()

    @property
    def currency(self) -> Currency:
        return self._currency


    def deposit(self, amount: int | float | Decimal) -> None:
        self._ensure_active()
        amount = self._validate_amount(amount)
        self._balance += amount

    def withdraw(self, amount: int | float | Decimal) -> None:
        self._ensure_active()
        amount = self._validate_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError()
        self._balance -= amount

    def get_account_info(self) -> dict:
        return {
            "account_id": self._account_id,
            "owner": self._owner,
            "balance": str(self._balance),
            "currency": self._currency.value,
            "status": self._status.value,
        }