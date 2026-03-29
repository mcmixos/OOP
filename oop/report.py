"""Report generation and visualization for the banking system."""

import csv
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bank_account import BankAccount
from bank_account_types import PremiumAccount
from bank_system import Bank
from transaction import TransactionProcessor, TransactionStatus, TransactionType
from audit import RiskAnalyzer


class ReportBuilder:
    """Generates text, JSON, CSV reports and charts."""

    def __init__(
        self,
        bank: Bank,
        analyzer: RiskAnalyzer,
        processor: TransactionProcessor,
    ) -> None:
        self._bank = bank
        self._analyzer = analyzer
        self._processor = processor

    def client_report(self, client_id: str) -> dict:
        """Generate a report for a single client."""
        client = self._bank._clients.get(client_id)
        if not client:
            return {}

        accounts = self._bank.search_accounts(client_id)
        account_ids = {acc.account_id for acc in accounts}
        txns = [
            t for t in self._analyzer._transaction_history
            if t.sender_account_id in account_ids
            or t.receiver_account_id in account_ids
        ]

        return {
            "client_id": client_id,
            "name": client.name,
            "status": client.status,
            "accounts": [
                {
                    "account_id": acc.account_id,
                    "type": type(acc).__name__,
                    "balance": str(acc.balance),
                    "currency": acc.currency.value,
                    "status": acc.status.value,
                }
                for acc in accounts
            ],
            "total_balance_by_currency": self._balance_by_currency(accounts),
            "transaction_count": len(txns),
            "risk_profiles": {
                acc.account_id: self._analyzer.get_client_risk_profile(acc.account_id)
                for acc in accounts
            },
        }

    def bank_report(self) -> dict:
        """Generate a full bank report."""
        all_accounts = list(self._bank._accounts.values())
        txns = self._analyzer._transaction_history

        by_type = {}
        by_status = {}
        for t in txns:
            by_type[t.txn_type.value] = by_type.get(t.txn_type.value, 0) + 1
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1

        return {
            "generated_at": datetime.now().isoformat(),
            "total_clients": len(self._bank._clients),
            "total_accounts": len(all_accounts),
            "total_balance_by_currency": self._balance_by_currency(all_accounts),
            "top_clients": [
                {"client_id": cid, "name": self._bank._clients[cid].name, "total": str(total)}
                for cid, total in self._bank.get_clients_ranking()[:5]
            ],
            "transactions": {
                "total": len(txns),
                "by_type": by_type,
                "by_status": by_status,
            },
        }

    def risk_report(self) -> dict:
        """Generate a risk analysis report."""
        suspicious = self._analyzer.get_suspicious_transactions()
        error_stats = self._analyzer.get_error_stats()

        risk_counts = {"low": 0, "medium": 0, "high": 0}
        for entry in self._analyzer._audit_log.entries:
            level = entry.get("risk_level")
            if level in risk_counts:
                risk_counts[level] += 1

        return {
            "generated_at": datetime.now().isoformat(),
            "risk_distribution": risk_counts,
            "suspicious_count": len(suspicious),
            "suspicious_transactions": [
                {
                    "txn_id": s["txn_id"],
                    "risk_level": s["risk_level"],
                    "reasons": s["reasons"],
                    "amount": s["amount"],
                    "txn_type": s["txn_type"],
                }
                for s in suspicious
            ],
            "error_stats": error_stats,
        }

    def format_text(self, report: dict, title: str = "Report") -> str:
        """Format a report dict as readable text."""
        lines = [title, "=" * len(title), ""]
        self._dict_to_text(report, lines, indent=0)
        return "\n".join(lines)

    def export_to_json(self, report: dict, path: str | Path) -> None:
        """Export a report to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    def export_to_csv(self, rows: list[dict], path: str | Path) -> None:
        """Export a list of flat dicts to CSV file."""
        if not rows:
            return
        fieldnames = list(rows[0].keys())
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def chart_transactions_by_type(self, path: str | Path) -> None:
        """Pie chart: transaction distribution by type."""
        txns = self._analyzer._transaction_history
        by_type = {}
        for t in txns:
            by_type[t.txn_type.value] = by_type.get(t.txn_type.value, 0) + 1

        if not by_type:
            return

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.pie(by_type.values(), labels=by_type.keys(), autopct="%1.1f%%", startangle=90)
        ax.set_title("Transactions by Type")
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)

    def chart_client_balances(self, path: str | Path) -> None:
        """Bar chart: top client balances (in primary currency)."""
        ranking = self._bank.get_clients_ranking()[:10]
        if not ranking:
            return

        names = [self._bank._clients[cid].name for cid, _ in ranking]
        balances = [float(total) for _, total in ranking]

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(names[::-1], balances[::-1])
        ax.set_xlabel("Total Balance")
        ax.set_title("Top Clients by Balance")
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)

    def chart_balance_history(self, account_id: str, path: str | Path) -> None:
        """Line chart: balance movement for an account across transactions."""
        account = self._bank._accounts.get(account_id)
        if not account:
            return

        txns = [
            t for t in self._analyzer._transaction_history
            if (t.sender_account_id == account_id or t.receiver_account_id == account_id)
            and t.status is TransactionStatus.COMPLETED
        ]

        if not txns:
            return

        convert = TransactionProcessor.convert_currency
        balance = account.balance
        points = []
        premium_fee = account.commission if isinstance(account, PremiumAccount) else Decimal("0")
        for t in reversed(txns):
            points.insert(0, float(balance))
            if t.sender_account_id == account_id:
                amount = convert(t.amount, t.currency, account.currency)
                commission = convert(t.commission, t.currency, account.currency)
                balance += amount + commission + premium_fee
            elif t.receiver_account_id == account_id:
                amount = convert(t.amount, t.currency, account.currency)
                balance -= amount
        points.insert(0, float(balance))

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(range(len(points)), points, marker="o", linewidth=2, markersize=4)
        ax.set_xlabel("Transaction #")
        ax.set_ylabel("Balance")
        ax.set_title(f"Balance History — {account_id}")
        ax.grid(True, alpha=0.3)
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)

    def save_charts(self, output_dir: str | Path) -> list[str]:
        """Generate and save all charts. Returns list of saved file paths."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        saved = []

        path = output_dir / "transactions_by_type.png"
        self.chart_transactions_by_type(path)
        if path.exists():
            saved.append(str(path))

        path = output_dir / "client_balances.png"
        self.chart_client_balances(path)
        if path.exists():
            saved.append(str(path))

        for acc_id in list(self._bank._accounts.keys())[:3]:
            path = output_dir / f"balance_history_{acc_id}.png"
            self.chart_balance_history(acc_id, path)
            if path.exists():
                saved.append(str(path))

        return saved

    @staticmethod
    def _balance_by_currency(accounts: list[BankAccount]) -> dict[str, str]:
        totals: dict[str, Decimal] = {}
        for acc in accounts:
            cur = acc.currency.value
            totals[cur] = totals.get(cur, Decimal("0")) + acc.balance
        return {k: str(v) for k, v in totals.items()}

    @staticmethod
    def _dict_to_text(data, lines: list[str], indent: int) -> None:
        prefix = "  " * indent
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{prefix}{key}:")
                    ReportBuilder._dict_to_text(value, lines, indent + 1)
                else:
                    lines.append(f"{prefix}{key}: {value}")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    ReportBuilder._dict_to_text(item, lines, indent)
                    lines.append("")
                else:
                    lines.append(f"{prefix}- {item}")