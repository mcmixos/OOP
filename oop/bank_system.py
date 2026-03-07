"""Bank system with clients, accounts and security."""

from datetime import date, datetime
from decimal import Decimal

from bank_account import (
    AccountStatus,
    BankAccount,
    Currency,
    InvalidOperationError,
)


class AuthenticationError(Exception):
    """Authentication failed."""


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
        self.status = "active"

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
        self._suspicious_threshold = Decimal(str(suspicious_threshold))

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
        self._accounts[account_id]._status = AccountStatus.CLOSED

    def freeze_account(self, account_id: str, *, is_night: bool | None = None) -> None:
        self._check_night(is_night)
        if account_id not in self._accounts:
            raise InvalidOperationError()
        self._accounts[account_id]._status = AccountStatus.FROZEN

    def unfreeze_account(self, account_id: str, *, is_night: bool | None = None) -> None:
        self._check_night(is_night)
        if account_id not in self._accounts:
            raise InvalidOperationError()
        self._accounts[account_id]._status = AccountStatus.ACTIVE

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

        amount = Decimal(str(amount))
        sender = self._clients.get(sender_client_id)
        if not sender:
            raise InvalidOperationError()

        if (amount >= self._suspicious_threshold
                and receiver_client_id not in sender.contacts):
            self._suspicious_log.append({
                "sender": sender_client_id,
                "receiver": receiver_client_id,
                "amount": str(amount),
                "reason": "high amount to non-contact",
            })

        self._accounts[from_account_id].withdraw(amount)
        self._accounts[to_account_id].deposit(amount)

    def get_total_balance(self, client_id: str) -> Decimal:
        accounts = self.search_accounts(client_id)
        return sum((acc.balance for acc in accounts), Decimal("0"))

    def get_clients_ranking(self) -> list[tuple[str, Decimal]]:
        ranking = []
        for client_id in self._clients:
            total = self.get_total_balance(client_id)
            ranking.append((client_id, total))
        ranking.sort(key=lambda x: x[1], reverse=True)
        return ranking

    @property
    def suspicious_log(self) -> list[dict]:
        return list(self._suspicious_log)


if __name__ == "__main__":
    print("=== Bank Demo ===\n")

    bank = Bank(suspicious_threshold=50000)

    client1 = Client(
        "Petrov Ivan",
        "C001",
        date(1990, 5, 15),
        "1234",
        contacts=["C002"],
    )
    client2 = Client(
        "Sidorov Anton",
        "C002",
        date(1985, 8, 20),
        "5678",
    )

    bank.add_client(client1, is_night=False)
    bank.add_client(client2, is_night=False)
    print(f"  {client1}")
    print(f"  {client2}\n")

    acc1 = BankAccount("Petrov Ivan", account_id="ACC001", balance=200000, currency=Currency.RUB)
    acc2 = BankAccount("Sidorov Anton", account_id="ACC002", balance=50000, currency=Currency.RUB)

    bank.open_account("C001", acc1, is_night=False)
    bank.open_account("C002", acc2, is_night=False)
    print(f"  {acc1}")
    print(f"  {acc2}\n")

    authenticated = bank.authenticate_client("C001", "1234")
    print(f"  Authenticated: {authenticated.name}")

    try:
        bank.authenticate_client("C001", "0000")
    except AuthenticationError:
        print("  Wrong pin — auth failed")

    bank.transfer("ACC001", "ACC002", 60000, sender_client_id="C001", receiver_client_id="C002", is_night=False)
    print(f"\n  After transfer 60000 (C001→C002, contact):")
    print(f"  {acc1}")
    print(f"  {acc2}")
    print(f"  Suspicious log: {bank.suspicious_log}")

    bank.transfer("ACC002", "ACC001", 55000, sender_client_id="C002", receiver_client_id="C001", is_night=False)
    print(f"\n  After transfer 55000 (C002→C001, non-contact, above threshold):")
    print(f"  {acc1}")
    print(f"  {acc2}")
    print(f"  Suspicious log: {bank.suspicious_log}")

    bank.freeze_account("ACC002", is_night=False)
    print(f"\n  After freezing ACC002: {acc2}")

    print(f"\n  Ranking: {bank.get_clients_ranking()}")

    try:
        bank.open_account("C001", BankAccount("Test", account_id="ACC003"), is_night=True)
    except NightOperationError:
        print("  Night operation blocked")