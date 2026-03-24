"""Audit logging and risk analysis for banking operations."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path

from transaction import Transaction, TransactionStatus, TransactionType


class LogLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskResult:
    """Result of a risk analysis for a single transaction."""

    def __init__(self, risk_level: RiskLevel, reasons: list[str]) -> None:
        self.risk_level = risk_level
        self.reasons = reasons

    def __str__(self) -> str:
        return f"RiskResult({self.risk_level.value}, {self.reasons})"


class AuditLog:
    """Audit log with in-memory storage and optional file output."""

    def __init__(self, *, log_file: str | Path | None = None) -> None:
        self._entries: list[dict] = []
        self._log_file = Path(log_file) if log_file else None

    @property
    def entries(self) -> list[dict]:
        return list(self._entries)

    def log(self, level: LogLevel, message: str, **metadata) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level.value,
            "message": message,
        }
        for key, value in metadata.items():
            if isinstance(value, Decimal):
                entry[key] = str(value)
            else:
                entry[key] = value

        self._entries.append(entry)

        if self._log_file:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def filter(
        self,
        *,
        level: LogLevel | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> list[dict]:
        results = list(self._entries)
        if level:
            results = [e for e in results if e["level"] == level.value]
        if after:
            results = [e for e in results if e["timestamp"] >= after.isoformat()]
        if before:
            results = [e for e in results if e["timestamp"] <= before.isoformat()]
        return results

    def clear(self) -> None:
        self._entries.clear()


class RiskAnalyzer:
    """Analyzes transactions for suspicious activity and generates reports."""

    def __init__(
        self,
        audit_log: AuditLog,
        *,
        high_amount_threshold: int | float | Decimal = 500000,
        frequency_limit: int = 5,
        frequency_window_minutes: int = 60,
    ) -> None:
        self._audit_log = audit_log
        self._high_amount_threshold = Decimal(str(high_amount_threshold))
        self._frequency_limit = frequency_limit
        self._frequency_window = timedelta(minutes=frequency_window_minutes)
        self._transaction_history: list[Transaction] = []
        self._known_receivers: dict[str, set[str]] = {}

    def analyze(
        self,
        txn: Transaction,
        *,
        is_night: bool | None = None,
    ) -> RiskResult:
        reasons = []

        if txn.amount >= self._high_amount_threshold:
            reasons.append("high amount")

        if is_night is None:
            is_night = 0 <= datetime.now().hour < 5
        if is_night:
            reasons.append("night operation")

        if txn.sender_account_id:
            recent = [
                t for t in self._transaction_history
                if t.sender_account_id == txn.sender_account_id
                and (datetime.now() - t.created_at) < self._frequency_window
            ]
            if len(recent) >= self._frequency_limit:
                reasons.append("high frequency")

        if (txn.txn_type is TransactionType.TRANSFER
                and txn.receiver_account_id
                and txn.sender_account_id):
            known = self._known_receivers.get(txn.sender_account_id, set())
            if txn.receiver_account_id not in known:
                reasons.append("new receiver")

        if txn not in self._transaction_history:
            self._transaction_history.append(txn)

        if len(reasons) >= 2:
            risk_level = RiskLevel.HIGH
        elif len(reasons) == 1:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        log_level = {
            RiskLevel.LOW: LogLevel.INFO,
            RiskLevel.MEDIUM: LogLevel.WARNING,
            RiskLevel.HIGH: LogLevel.CRITICAL,
        }[risk_level]

        self._audit_log.log(
            log_level,
            f"Risk analysis: {risk_level.value}",
            txn_id=txn.txn_id,
            risk_level=risk_level.value,
            reasons=reasons,
            amount=txn.amount,
            txn_type=txn.txn_type.value,
        )

        return RiskResult(risk_level, reasons)

    def register_completed(self, txn: Transaction) -> None:
        """Register a successfully completed transfer's receiver as known."""
        if txn.txn_type is TransactionType.TRANSFER and txn.sender_account_id:
            if txn.sender_account_id not in self._known_receivers:
                self._known_receivers[txn.sender_account_id] = set()
            if txn.receiver_account_id:
                self._known_receivers[txn.sender_account_id].add(txn.receiver_account_id)

    def get_suspicious_transactions(self) -> list[dict]:
        return self._audit_log.filter(level=LogLevel.WARNING) + \
               self._audit_log.filter(level=LogLevel.CRITICAL)

    def get_client_risk_profile(self, sender_account_id: str) -> dict:
        txns = [
            t for t in self._transaction_history
            if t.sender_account_id == sender_account_id
        ]
        if not txns:
            return {
                "account_id": sender_account_id,
                "total_transactions": 0,
                "risk_summary": {},
            }

        risk_counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0}
        for entry in self._audit_log.entries:
            if entry.get("txn_id") in {t.txn_id for t in txns}:
                level = entry.get("risk_level", "low")
                risk_counts[level] = risk_counts.get(level, 0) + 1

        return {
            "account_id": sender_account_id,
            "total_transactions": len(txns),
            "risk_summary": risk_counts,
        }

    def get_error_stats(self) -> dict:
        failed = [
            t for t in self._transaction_history
            if t.status is TransactionStatus.FAILED
        ]
        reasons: dict[str, int] = {}
        for t in failed:
            reason = t.failure_reason or "unknown"
            reasons[reason] = reasons.get(reason, 0) + 1

        return {
            "total_failed": len(failed),
            "by_reason": reasons,
        }