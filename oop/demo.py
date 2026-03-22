"""Demo for the bank account system."""

from datetime import date

from bank_account import (
    AccountFrozenError,
    AccountStatus,
    BankAccount,
    Currency,
)
from bank_account_types import (
    AssetType,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)
from bank_system import (
    AuthenticationError,
    Bank,
    Client,
    NightOperationError,
)


if __name__ == "__main__":

    print("=== BankAccount ===\n")

    acc = BankAccount("Petrov Ivan", balance=10000, currency=Currency.RUB)
    print(f"  Active account created:\n  {acc}\n")

    acc.deposit(500)
    print(f"  After depositing 500:\n  {acc}\n")

    acc.withdraw(200)
    print(f"  After withdrawing 200:\n  {acc}\n")

    frozen = BankAccount(
        "Ivanov Petr",
        balance=5000,
        status=AccountStatus.FROZEN,
        currency=Currency.USD,
    )
    print(f"  Frozen account created:\n  {frozen}\n")

    for op_name, op in [("deposit", lambda: frozen.deposit(100)),
                         ("withdraw", lambda: frozen.withdraw(50))]:
        try:
            op()
        except AccountFrozenError as exc:
            print(f"  Attempted {op_name} on frozen account: {exc}")


    print("\n\n=== SavingsAccount ===\n")

    savings = SavingsAccount(
        "Petrov Ivan",
        balance=50000,
        min_balance=10000,
        monthly_rate=0.01,
    )
    print(f"  {savings}")
    interest = savings.apply_monthly_interest()
    print(f"  Monthly interest: +{interest:.2f}")
    print(f"  {savings}")


    print("\n\n=== PremiumAccount ===\n")

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
    print(f"  {premium}")


    print("\n\n=== InvestmentAccount ===\n")

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


    print("\n\n=== Bank System ===\n")

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

    bank.transfer(
        "ACC001", "ACC002", 60000,
        sender_client_id="C001",
        receiver_client_id="C002",
        is_night=False,
    )
    print(f"\n  After transfer 60000 (C001->C002, contact):")
    print(f"  {acc1}")
    print(f"  {acc2}")
    print(f"  Suspicious log: {bank.suspicious_log}")

    bank.transfer(
        "ACC002", "ACC001", 55000,
        sender_client_id="C002",
        receiver_client_id="C001",
        is_night=False,
    )
    print(f"\n  After transfer 55000 (C002->C001, non-contact, above threshold):")
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