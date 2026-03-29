"""Bank system with clients, accounts and security."""

from datetime import date, datetime
from decimal import Decimal

from bank_account import (
    AccountError,
    AccountStatus,
    BankAccount,
    Currency,
    InvalidOperationError,
    to_decimal,
)

from transaction import EXCHANGE_RATES


class AuthenticationError(AccountError):
    """Authentication failed."""

class ClientBlockedError(AccountError):
    """Client is blocked due to failed login attempts."""

class NightOperationError(AccountError):
    """Operation rejected — night hours (00:00–05:00)."""

class ClientBlockedError(Exception):
    """Client is blocked due to failed login attempts."""

class NightOperationError(Exception):
    """Operation rejected — night hours (00:00–05:00)."""

class Client:
    """Bank client with personal data, accounts and contacts."""

    def __init__(
        self,
        name: str,
        client_id: str,
        date_of_birth: date,
        pin: str,
        *,
        contacts: list[str] | None = None,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise InvalidOperationError()
        if not isinstance(client_id, str) or not client_id.strip():
            raise InvalidOperationError()
        if not isinstance(pin, str) or len(pin) != 4 or not pin.isdigit():
            raise InvalidOperationError()

        today = date.today()
        age = today.year - date_of_birth.year - (
            (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
        )
        if age < 18:
            raise InvalidOperationError()

        self.name = name
        self.client_id = client_id
        self.date_of_birth = date_of_birth
        self.pin = pin
        self.contacts: list[str] = contacts or []
        self.account_ids: list[str] = []
        self.is_blocked = False
        self.failed_attempts = 0

    @property
    def status(self) -> str:
        return "blocked" if self.is_blocked else "active"

    def __str__(self) -> str:
        return (
            f"Client | {self.name} | {self.client_id} | "
            f"{self.status} | accounts: {len(self.account_ids)}"
        )


class Bank:
    """Bank managing clients, accounts and security."""

    MAX_FAILED_ATTEMPTS = 3
    NIGHT_START = 0
    NIGHT_END = 5

    def __init__(self, *, suspicious_threshold: int | float | Decimal = 100000) -> None:
        self._clients: dict[str, Client] = {}
        self._accounts: dict[str, BankAccount] = {}
        self._suspicious_log: list[dict] = []
        self._suspicious_threshold = to_decimal(suspicious_threshold)


    def _check_night(self, is_night: bool | None = None) -> None:
        if is_night is None:
            is_night = self.NIGHT_START <= datetime.now().hour < self.NIGHT_END
        if is_night:
            raise NightOperationError()


    def add_client(self, client: Client, *, is_night: bool | None = None) -> None:
        self._check_night(is_night)
        if client.client_id in self._clients:
            raise InvalidOperationError()
        self._clients[client.client_id] = client

    def authenticate_client(self, client_id: str, pin: str) -> Client:
        if client_id not in self._clients:
            raise AuthenticationError()
        client = self._clients[client_id]
        if client.is_blocked:
            raise ClientBlockedError()
        if client.pin != pin:
            client.failed_attempts += 1
            if client.failed_attempts >= self.MAX_FAILED_ATTEMPTS:
                client.is_blocked = True
                raise ClientBlockedError()
            raise AuthenticationError()
        client.failed_attempts = 0
        return client


    def open_account(
        self,
        client_id: str,
        account: BankAccount,
        *,
        is_night: bool | None = None,
    ) -> None:
        self._check_night(is_night)
        if client_id not in self._clients:
            raise InvalidOperationError()
        if account.account_id in self._accounts:
            raise InvalidOperationError()
        self._clients[client_id].account_ids.append(account.account_id)
        self._accounts[account.account_id] = account

    def close_account(self, account_id: str, *, is_night: bool | None = None) -> None:
        self._check_night(is_night)
        if account_id not in self._accounts:
            raise InvalidOperationError()
        self._accounts[account_id].set_status(AccountStatus.CLOSED)

    def freeze_account(self, account_id: str, *, is_night: bool | None = None) -> None:
        self._check_night(is_night)
        if account_id not in self._accounts:
            raise InvalidOperationError()
        self._accounts[account_id].set_status(AccountStatus.FROZEN)

    def unfreeze_account(self, account_id: str, *, is_night: bool | None = None) -> None:
        self._check_night(is_night)
        if account_id not in self._accounts:
            raise InvalidOperationError()
        self._accounts[account_id].set_status(AccountStatus.ACTIVE)

    def search_accounts(self, client_id: str) -> list[BankAccount]:
        if client_id not in self._clients:
            raise InvalidOperationError()
        client = self._clients[client_id]
        return [self._accounts[aid] for aid in client.account_ids if aid in self._accounts]


    def transfer(
        self,
        from_account_id: str,
        to_account_id: str,
        amount: int | float | Decimal,
        *,
        sender_client_id: str,
        receiver_client_id: str,
        is_night: bool | None = None,
    ) -> None:
        self._check_night(is_night)
        if from_account_id not in self._accounts or to_account_id not in self._accounts:
            raise InvalidOperationError()

        sender = self._clients.get(sender_client_id)
        if not sender:
            raise InvalidOperationError()
        if from_account_id not in sender.account_ids:
            raise InvalidOperationError()

        receiver = self._clients.get(receiver_client_id)
        if not receiver:
            raise InvalidOperationError()
        if to_account_id not in receiver.account_ids:
            raise InvalidOperationError()

        amount = to_decimal(amount)

        if (amount >= self._suspicious_threshold
                and receiver_client_id not in sender.contacts):
            self._suspicious_log.append({
                "sender": sender_client_id,
                "receiver": receiver_client_id,
                "amount": str(amount),
                "reason": "high amount to non-contact",
            })

        from_acc = self._accounts[from_account_id]
        to_acc = self._accounts[to_account_id]

        from_acc.withdraw(amount)
        try:
            to_acc.deposit(amount)
        except Exception:
            from_acc.deposit(amount)
            raise


    def get_total_balance(self, client_id: str, *, base_currency: Currency = Currency.RUB) -> Decimal:
        accounts = self.search_accounts(client_id)
        total = Decimal("0")
        for acc in accounts:
            if acc.currency is base_currency:
                total += acc.balance
            else:
                rate_from = EXCHANGE_RATES[acc.currency]
                rate_to = EXCHANGE_RATES[base_currency]
                total += (acc.balance / rate_from * rate_to).quantize(Decimal("0.01"))
        return total

    def get_clients_ranking(self, *, base_currency: Currency = Currency.RUB) -> list[tuple[str, Decimal]]:
        ranking = []
        for client_id in self._clients:
            total = self.get_total_balance(client_id, base_currency=base_currency)
            ranking.append((client_id, total))
        ranking.sort(key=lambda x: x[1], reverse=True)
        return ranking

    @property
    def suspicious_log(self) -> list[dict]:
        return list(self._suspicious_log)