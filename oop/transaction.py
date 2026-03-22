"""Transaction model, queue and processor."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from bank_account import (
    AccountFrozenError,
    AccountClosedError,
    AccountStatus,
    BankAccount,
    Currency,
    InsufficientFundsError,
    InvalidOperationError,
)
from bank_account_types import PremiumAccount

class TransactionType(Enum):
    TRANSFER = "transfer"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
class TransactionStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
class Priority(Enum):
    HIGH = 1
    NORMAL = 2
    LOW = 3

EXCHANGE_RATES = {
    Currency.USD: Decimal("1"),
    Currency.RUB: Decimal("90"),
    Currency.EUR: Decimal("0.92"),
    Currency.KZT: Decimal("450"),
    Currency.CNY: Decimal("7.2"),
}

class Transaction:
    """Single financial transaction."""

    def __init__(
        self,
        txn_type: TransactionType,
        amount: int | float | Decimal,
        currency: Currency,
        *,
        sender_account_id: str | None = None,
        receiver_account_id: str | None = None,
        is_external: bool = False,
        priority: Priority = Priority.NORMAL,
        scheduled_at: datetime | None = None,
    ) -> None:
        if not isinstance(txn_type, TransactionType):
            raise InvalidOperationError()
        if not isinstance(currency, Currency):
            raise InvalidOperationError()
        if not isinstance(priority, Priority):
            raise InvalidOperationError()

        amount = Decimal(str(amount))
        if amount <= 0:
            raise InvalidOperationError()

        if txn_type is TransactionType.TRANSFER and not sender_account_id:
            raise InvalidOperationError()
        if txn_type is TransactionType.TRANSFER and not is_external and not receiver_account_id:
            raise InvalidOperationError()
        if txn_type is TransactionType.DEPOSIT and not receiver_account_id:
            raise InvalidOperationError()
        if txn_type is TransactionType.WITHDRAWAL and not sender_account_id:
            raise InvalidOperationError()

        self.txn_id = uuid.uuid4().hex[:8]
        self.txn_type = txn_type
        self.amount = amount
        self.currency = currency
        self.commission = Decimal("0")
        self.sender_account_id = sender_account_id
        self.receiver_account_id = receiver_account_id
        self.is_external = is_external
        self.priority = priority
        self.scheduled_at = scheduled_at
        self.status = TransactionStatus.PENDING
        self.failure_reason: str | None = None
        self.retries = 0
        self.created_at = datetime.now()
        self.completed_at: datetime | None = None

    def __str__(self) -> str:
        return (
            f"Transaction {self.txn_id} | {self.txn_type.value} | "
            f"{self.amount} {self.currency.value} | {self.status.value}"
        )

class TransactionQueue:
    """Priority queue with delayed transaction support."""

    def __init__(self) -> None:
        self._pending: list[Transaction] = []
        self._delayed: list[Transaction] = []

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def delayed_count(self) -> int:
        return len(self._delayed)

    def add(self, txn: Transaction) -> None:
        if txn.status is not TransactionStatus.PENDING:
            raise InvalidOperationError()
        if txn.scheduled_at is not None:
            self._delayed.append(txn)
        else:
            self._pending.append(txn)

    def cancel(self, txn_id: str) -> Transaction | None:
        for pool in (self._pending, self._delayed):
            for txn in pool:
                if txn.txn_id == txn_id:
                    txn.status = TransactionStatus.CANCELLED
                    pool.remove(txn)
                    return txn
        return None

    def release_delayed(self, *, current_time: datetime | None = None) -> int:
        now = current_time or datetime.now()
        released = 0
        still_delayed = []
        for txn in self._delayed:
            if txn.scheduled_at <= now:
                self._pending.append(txn)
                released += 1
            else:
                still_delayed.append(txn)
        self._delayed = still_delayed
        return released

    def get_next(self) -> Transaction | None:
        if not self._pending:
            return None
        self._pending.sort(key=lambda t: t.priority.value)
        return self._pending.pop(0)

    def get_all_pending(self) -> list[Transaction]:
        self._pending.sort(key=lambda t: t.priority.value)
        result = list(self._pending)
        self._pending.clear()
        return result

class TransactionProcessor:
    """Processes transactions with commissions, conversion and retries."""

    def __init__(
        self,
        accounts: dict[str, BankAccount],
        *,
        external_commission_rate: Decimal = Decimal("0.02"),
        max_retries: int = 3,
    ) -> None:
        self._accounts = accounts
        self._external_commission_rate = external_commission_rate
        self._max_retries = max_retries
        self._error_log: list[dict] = []

    @property
    def error_log(self) -> list[dict]:
        return list(self._error_log)


    @staticmethod
    def convert_currency(
        amount: Decimal,
        from_currency: Currency,
        to_currency: Currency,
    ) -> Decimal:
        if from_currency is to_currency:
            return amount
        from_rate = EXCHANGE_RATES[from_currency]
        to_rate = EXCHANGE_RATES[to_currency]
        return amount / from_rate * to_rate


    def process(self, txn: Transaction) -> None:
        if txn.status is not TransactionStatus.PENDING:
            return

        try:
            self._validate(txn)
            self._calculate_commission(txn)
            self._execute(txn)
            txn.status = TransactionStatus.COMPLETED
            txn.completed_at = datetime.now()
        except Exception as exc:
            txn.retries += 1
            if txn.retries >= self._max_retries:
                txn.status = TransactionStatus.FAILED
                txn.failure_reason = str(exc) or type(exc).__name__
                self._error_log.append({
                    "txn_id": txn.txn_id,
                    "error": txn.failure_reason,
                    "retries": txn.retries,
                })

    def process_queue(
        self,
        queue: TransactionQueue,
        *,
        current_time: datetime | None = None,
    ) -> list[Transaction]:
        queue.release_delayed(current_time=current_time)
        transactions = queue.get_all_pending()
        for txn in transactions:
            while txn.status is TransactionStatus.PENDING:
                self.process(txn)
        return transactions


    def _validate(self, txn: Transaction) -> None:
        if txn.sender_account_id:
            sender = self._accounts.get(txn.sender_account_id)
            if not sender:
                raise InvalidOperationError()
            if sender.status is AccountStatus.FROZEN:
                raise AccountFrozenError()
            if sender.status is AccountStatus.CLOSED:
                raise AccountClosedError()

        if txn.receiver_account_id:
            receiver = self._accounts.get(txn.receiver_account_id)
            if not receiver:
                raise InvalidOperationError()
            if receiver.status is AccountStatus.FROZEN:
                raise AccountFrozenError()
            if receiver.status is AccountStatus.CLOSED:
                raise AccountClosedError()

    def _calculate_commission(self, txn: Transaction) -> None:
        if txn.is_external:
            txn.commission = txn.amount * self._external_commission_rate

    def _execute(self, txn: Transaction) -> None:
        if txn.txn_type is TransactionType.DEPOSIT:
            receiver = self._accounts[txn.receiver_account_id]
            deposit_amount = self.convert_currency(txn.amount, txn.currency, receiver.currency)
            receiver.deposit(deposit_amount)

        elif txn.txn_type is TransactionType.WITHDRAWAL:
            sender = self._accounts[txn.sender_account_id]
            withdraw_amount = self.convert_currency(txn.amount, txn.currency, sender.currency)
            total = withdraw_amount + txn.commission
            self._withdraw_with_check(sender, total)

        elif txn.txn_type is TransactionType.TRANSFER:
            sender = self._accounts[txn.sender_account_id]
            withdraw_amount = self.convert_currency(txn.amount, txn.currency, sender.currency)
            total = withdraw_amount + txn.commission
            self._withdraw_with_check(sender, total)

            if not txn.is_external and txn.receiver_account_id:
                receiver = self._accounts[txn.receiver_account_id]
                deposit_amount = self.convert_currency(txn.amount, txn.currency, receiver.currency)
                try:
                    receiver.deposit(deposit_amount)
                except Exception:
                    sender.deposit(total)
                    raise

    @staticmethod
    def _withdraw_with_check(account: BankAccount, amount: Decimal) -> None:
        if not isinstance(account, PremiumAccount) and account.balance < amount:
            raise InsufficientFundsError()
        account.withdraw(amount)