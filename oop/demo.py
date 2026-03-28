"""Full banking system demonstration."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from bank_account import (
    AccountFrozenError,
    AccountClosedError,
    AccountStatus,
    BankAccount,
    Currency,
    InsufficientFundsError,
    InvalidOperationError,
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
    ClientBlockedError,
    NightOperationError,
)
from transaction import (
    Priority,
    Transaction,
    TransactionProcessor,
    TransactionQueue,
    TransactionStatus,
    TransactionType,
)
from audit import (
    AuditLog,
    RiskAnalyzer,
)
from report import ReportBuilder


def print_header(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def print_section(title):
    print(f"\n--- {title} ---\n")


def get_client_transactions(analyzer, bank, client_id):
    """Get all analyzed transactions for a client's accounts."""
    accounts = bank.search_accounts(client_id)
    account_ids = {acc.account_id for acc in accounts}
    return [
        t for t in analyzer._transaction_history
        if t.sender_account_id in account_ids or t.receiver_account_id in account_ids
    ]


if __name__ == "__main__":

    print_header("BANK INITIALIZATION")

    bank = Bank(suspicious_threshold=100000)
    audit_log = AuditLog()
    analyzer = RiskAnalyzer(audit_log, high_amount_threshold=200000, frequency_limit=5)


    clients_data = [
        ("Petrov Ivan", "C001", date(1990, 5, 15), "1234", ["C002", "C003"]),
        ("Ivanov Petr", "C002", date(1985, 8, 20), "5678", ["C001"]),
        ("Bill Gates", "C003", date(1992, 3, 10), "9012", ["C001"]),
        ("Donald Trump", "C004", date(1978, 12, 1), "3456", []),
        ("Golovach Elena", "C005", date(1995, 7, 25), "7890", ["C003"]),
        ("Elon Musk", "C006", date(1988, 1, 30), "2345", []),
        ("Buterin Vitalik", "C007", date(2000, 11, 5), "6789", ["C001", "C002"]),
    ]

    for name, cid, dob, pin, contacts in clients_data:
        client = Client(name, cid, dob, pin, contacts=contacts)
        bank.add_client(client, is_night=False)
        print(f"  {client}")


    print_section("Accounts")

    accounts_data = [
        ("C001", BankAccount("Petrov Ivan", account_id="ACC001", balance=500000, currency=Currency.RUB)),
        ("C001", SavingsAccount("Petrov Ivan", account_id="ACC002", balance=300000, min_balance=50000, monthly_rate=0.01, currency=Currency.RUB)),
        ("C002", BankAccount("Ivanov Petr", account_id="ACC003", balance=150000, currency=Currency.RUB)),
        ("C002", PremiumAccount("Ivanov Petr", account_id="ACC004", balance=1000000, currency=Currency.USD, withdrawal_limit=500000, overdraft_limit=200000, commission=50)),
        ("C003", BankAccount("Bill Gates", account_id="ACC005", balance=80000, currency=Currency.RUB)),
        ("C003", InvestmentAccount("Bill Gates", account_id="ACC006", balance=200000, currency=Currency.RUB, portfolio={AssetType.STOCKS: 300000, AssetType.BONDS: 150000, AssetType.ETF: 100000})),
        ("C004", BankAccount("Donald Trump", account_id="ACC007", balance=45000, currency=Currency.EUR)),
        ("C004", SavingsAccount("Donald Trump", account_id="ACC008", balance=120000, min_balance=20000, currency=Currency.RUB)),
        ("C005", PremiumAccount("Golovach Elena", account_id="ACC009", balance=750000, currency=Currency.RUB, withdrawal_limit=300000, overdraft_limit=100000, commission=75)),
        ("C005", BankAccount("Golovach Elena", account_id="ACC010", balance=50000, currency=Currency.USD)),
        ("C006", BankAccount("Elon Musk", account_id="ACC011", balance=25000, currency=Currency.RUB)),
        ("C007", BankAccount("Buterin Vitalik", account_id="ACC012", balance=90000, currency=Currency.RUB)),
    ]

    all_accounts = {}
    for client_id, account in accounts_data:
        bank.open_account(client_id, account, is_night=False)
        all_accounts[account.account_id] = account
        print(f"  [{client_id}] {account}")

    processor = TransactionProcessor(all_accounts, risk_analyzer=analyzer)


    print_header("AUTHENTICATION")

    print("  Correct pin:")
    result = bank.authenticate_client("C001", "1234")
    print(f"    {result.name} — authenticated\n")

    print("  Wrong pin (3 attempts, C006):")
    for i in range(3):
        try:
            bank.authenticate_client("C006", "0000")
        except AuthenticationError:
            print(f"    Attempt {i + 1}: wrong pin")
        except ClientBlockedError:
            print(f"    Attempt {i + 1}: BLOCKED")

    print(f"    C006 status: {bank._clients['C006'].status}")


    print_header("TRANSACTION SIMULATION")

    queue = TransactionQueue()

    transactions = [
        # --- Normal operations ---
        Transaction(TransactionType.DEPOSIT, 15000, Currency.RUB, receiver_account_id="ACC001"),
        Transaction(TransactionType.DEPOSIT, 25000, Currency.RUB, receiver_account_id="ACC003"),
        Transaction(TransactionType.WITHDRAWAL, 10000, Currency.RUB, sender_account_id="ACC001"),
        Transaction(TransactionType.WITHDRAWAL, 5000, Currency.RUB, sender_account_id="ACC005"),
        Transaction(TransactionType.TRANSFER, 30000, Currency.RUB, sender_account_id="ACC001", receiver_account_id="ACC003"),
        Transaction(TransactionType.TRANSFER, 20000, Currency.RUB, sender_account_id="ACC003", receiver_account_id="ACC001"),
        Transaction(TransactionType.DEPOSIT, 50000, Currency.RUB, receiver_account_id="ACC008"),
        Transaction(TransactionType.WITHDRAWAL, 8000, Currency.RUB, sender_account_id="ACC012"),
        Transaction(TransactionType.TRANSFER, 15000, Currency.RUB, sender_account_id="ACC005", receiver_account_id="ACC012"),
        Transaction(TransactionType.DEPOSIT, 5000, Currency.USD, receiver_account_id="ACC010"),

        # --- External transfers (with commission) ---
        Transaction(TransactionType.TRANSFER, 50000, Currency.RUB, sender_account_id="ACC001", is_external=True),
        Transaction(TransactionType.TRANSFER, 100000, Currency.RUB, sender_account_id="ACC009", is_external=True),
        Transaction(TransactionType.TRANSFER, 10000, Currency.USD, sender_account_id="ACC004", is_external=True),
        Transaction(TransactionType.TRANSFER, 5000, Currency.EUR, sender_account_id="ACC007", is_external=True),

        # --- Cross-currency transfers ---
        Transaction(TransactionType.TRANSFER, 90000, Currency.RUB, sender_account_id="ACC001", receiver_account_id="ACC010"),
        Transaction(TransactionType.TRANSFER, 1000, Currency.USD, sender_account_id="ACC010", receiver_account_id="ACC005"),

        # --- High priority ---
        Transaction(TransactionType.DEPOSIT, 100000, Currency.RUB, receiver_account_id="ACC009", priority=Priority.HIGH),
        Transaction(TransactionType.TRANSFER, 75000, Currency.RUB, sender_account_id="ACC009", receiver_account_id="ACC001", priority=Priority.HIGH),

        # --- Low priority ---
        Transaction(TransactionType.DEPOSIT, 3000, Currency.RUB, receiver_account_id="ACC011", priority=Priority.LOW),
        Transaction(TransactionType.WITHDRAWAL, 2000, Currency.RUB, sender_account_id="ACC011", priority=Priority.LOW),

        # --- Delayed (past — will execute) ---
        Transaction(TransactionType.DEPOSIT, 7000, Currency.RUB, receiver_account_id="ACC001", scheduled_at=datetime.now() - timedelta(seconds=1)),
        Transaction(TransactionType.DEPOSIT, 12000, Currency.RUB, receiver_account_id="ACC003", scheduled_at=datetime.now() - timedelta(minutes=1)),

        # --- Delayed (future — will stay in queue) ---
        Transaction(TransactionType.DEPOSIT, 99000, Currency.RUB, receiver_account_id="ACC001", scheduled_at=datetime.now() + timedelta(hours=2)),

        # --- Suspicious: high amount ---
        Transaction(TransactionType.WITHDRAWAL, 250000, Currency.RUB, sender_account_id="ACC001"),
        Transaction(TransactionType.TRANSFER, 300000, Currency.RUB, sender_account_id="ACC009", receiver_account_id="ACC001"),

        # --- Suspicious: new receiver ---
        Transaction(TransactionType.TRANSFER, 5000, Currency.RUB, sender_account_id="ACC011", receiver_account_id="ACC001"),
        Transaction(TransactionType.TRANSFER, 5000, Currency.RUB, sender_account_id="ACC011", receiver_account_id="ACC005"),

        # --- Error: insufficient funds on regular account ---
        Transaction(TransactionType.WITHDRAWAL, 999999, Currency.RUB, sender_account_id="ACC011"),

        # --- Error: insufficient funds on savings (min_balance) ---
        Transaction(TransactionType.WITHDRAWAL, 280000, Currency.RUB, sender_account_id="ACC002"),

        # --- More normal transfers ---
        Transaction(TransactionType.TRANSFER, 10000, Currency.RUB, sender_account_id="ACC001", receiver_account_id="ACC012"),
        Transaction(TransactionType.TRANSFER, 20000, Currency.RUB, sender_account_id="ACC012", receiver_account_id="ACC005"),
        Transaction(TransactionType.DEPOSIT, 40000, Currency.RUB, receiver_account_id="ACC002"),
        Transaction(TransactionType.WITHDRAWAL, 15000, Currency.RUB, sender_account_id="ACC003"),
        Transaction(TransactionType.TRANSFER, 8000, Currency.RUB, sender_account_id="ACC005", receiver_account_id="ACC003"),

        # --- More external ---
        Transaction(TransactionType.TRANSFER, 20000, Currency.RUB, sender_account_id="ACC012", is_external=True),
        Transaction(TransactionType.TRANSFER, 30000, Currency.RUB, sender_account_id="ACC005", is_external=True),

        # --- Fill up to 40 ---
        Transaction(TransactionType.DEPOSIT, 10000, Currency.RUB, receiver_account_id="ACC005"),
        Transaction(TransactionType.DEPOSIT, 6000, Currency.RUB, receiver_account_id="ACC011"),
        Transaction(TransactionType.WITHDRAWAL, 3000, Currency.RUB, sender_account_id="ACC001"),
    ]

    print(f"  Total transactions created: {len(transactions)}")

    for txn in transactions:
        queue.add(txn)

    cancelled = queue.cancel(transactions[19].txn_id)
    print(f"  Cancelled: {cancelled}")

    print(f"  Queue: {queue.pending_count} pending, {queue.delayed_count} delayed\n")


    print_section("Processing")

    results = processor.process_queue(queue, is_night=False)

    completed = [t for t in results if t.status is TransactionStatus.COMPLETED]
    failed = [t for t in results if t.status is TransactionStatus.FAILED]
    cancelled_list = [t for t in results if t.status is TransactionStatus.CANCELLED]

    print(f"  Processed: {len(results)} transactions")
    print(f"  Completed: {len(completed)}")
    print(f"  Failed:    {len(failed)}")
    print(f"  Delayed (still in queue): {queue.delayed_count}")

    if failed:
        print_section("Failed transactions")
        for t in failed:
            print(f"  {t.txn_id} | {t.txn_type.value} | {t.amount} {t.currency.value} | {t.failure_reason}")

    # --- savings interest ---

    print_section("Monthly interest")

    for acc_id in ["ACC002", "ACC008"]:
        acc = all_accounts[acc_id]
        interest = acc.apply_monthly_interest()
        print(f"  {acc_id}: +{interest:.2f} {acc.currency.value}")

    # --- Freeze an account ---

    print_section("Account freeze")

    bank.freeze_account("ACC011", is_night=False)
    print(f"  ACC011 frozen: {all_accounts['ACC011'].status.value}")

    # --- Night operation attempt ---

    print_section("Night operation attempt")

    try:
        bank.open_account("C001", BankAccount("Test", account_id="NIGHT1"), is_night=True)
    except NightOperationError:
        print("  Blocked: night operation (00:00-05:00)")


    print_header("USER SCENARIOS")

    # --- Client accounts ---

    print_section("C001 (Petrov Ivan) — accounts")

    for acc in bank.search_accounts("C001"):
        print(f"  {acc}")

    # --- Client transaction history ---

    print_section("C001 — transaction history")

    c001_txns = get_client_transactions(analyzer, bank, "C001")
    for t in c001_txns[:10]:
        direction = "OUT" if t.sender_account_id in {"ACC001", "ACC002"} else "IN"
        print(f"  {direction} | {t.txn_type.value:10} | {t.amount:>10} {t.currency.value} | {t.status.value}")
    if len(c001_txns) > 10:
        print(f"  ... and {len(c001_txns) - 10} more")

    # --- Suspicious operations ---

    print_section("Suspicious operations")

    suspicious = analyzer.get_suspicious_transactions()
    for s in suspicious[:5]:
        print(f"  [{s['risk_level']}] txn={s['txn_id']} | {s['txn_type']} | {s['amount']} | {s['reasons']}")
    if len(suspicious) > 5:
        print(f"  ... and {len(suspicious) - 5} more")

    # --- Investment portfolio ---

    print_section("C003 — investment portfolio")

    inv_acc = all_accounts["ACC006"]
    print(f"  {inv_acc}")
    print(f"  Projected yearly growth: {inv_acc.project_yearly_growth():.2f} RUB")


    print_header("REPORTS")

    print_section("Top 3 clients by total balance")

    ranking = bank.get_clients_ranking()
    for i, (cid, total) in enumerate(ranking[:3], 1):
        name = bank._clients[cid].name
        print(f"  {i}. {name} ({cid}): {total:.2f}")

    print_section("Transaction statistics")

    all_txns = analyzer._transaction_history
    total = len(all_txns)
    by_type = {}
    for t in all_txns:
        by_type[t.txn_type.value] = by_type.get(t.txn_type.value, 0) + 1
    by_status = {}
    for t in all_txns:
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1

    print(f"  Total analyzed: {total}")
    print(f"  By type: {by_type}")
    print(f"  By status: {by_status}")


    print_section("Error statistics")

    error_stats = analyzer.get_error_stats()
    print(f"  Total failed: {error_stats['total_failed']}")
    for reason, count in error_stats["by_reason"].items():
        print(f"    {reason}: {count}")


    print_section("Risk profiles")

    for cid in ["C001", "C002", "C005", "C006"]:
        accounts = bank.search_accounts(cid)
        for acc in accounts:
            profile = analyzer.get_client_risk_profile(acc.account_id)
            if profile["total_transactions"] > 0:
                name = bank._clients[cid].name
                print(f"  {name} ({acc.account_id}): {profile['risk_summary']}")


    print_section("Total bank balance")

    total_by_currency = {}
    for acc in all_accounts.values():
        cur = acc.currency.value
        total_by_currency[cur] = total_by_currency.get(cur, Decimal("0")) + acc.balance
    for cur, total in sorted(total_by_currency.items()):
        print(f"  {cur}: {total:.2f}")


    print_header("REPORT GENERATION")
 
    builder = ReportBuilder(bank, analyzer, processor)
 
    print_section("Bank report (text)")
 
    bank_report = builder.bank_report()
    text = builder.format_text(bank_report, "Bank Summary")
    print(text)
 
 
    print_section("Client report — C001")
 
    client_report = builder.client_report("C001")
    print(f"  Name: {client_report['name']}")
    print(f"  Accounts: {len(client_report['accounts'])}")
    print(f"  Transactions: {client_report['transaction_count']}")
 
 
    print_section("Risk report")
 
    risk_report = builder.risk_report()
    print(f"  Distribution: {risk_report['risk_distribution']}")
    print(f"  Suspicious: {risk_report['suspicious_count']}")
    print(f"  Errors: {risk_report['error_stats']}")
 
 
    print_section("Export")
 
    builder.export_to_json(bank_report, "demo_bank_report.json")
    print("  Saved: demo_bank_report.json")
 
    builder.export_to_json(risk_report, "demo_risk_report.json")
    print("  Saved: demo_risk_report.json")
 
    csv_rows = [
        {"client_id": c["client_id"], "name": c["name"], "total": c["total"]}
        for c in bank_report["top_clients"]
    ]
    builder.export_to_csv(csv_rows, "demo_top_clients.csv")
    print("  Saved: demo_top_clients.csv")
 
    saved_charts = builder.save_charts("demo_charts")
    for path in saved_charts:
        print(f"  Chart: {path}")