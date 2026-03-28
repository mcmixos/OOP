# Базовая модель банковских счетов

**Python >= 3.10** (используется `str | None` синтаксис)

**Зависимости:** matplotlib

### Структура

| Файл | Описание |
|---|---|
| `bank_account.py` | AbstractAccount, BankAccount, исключения, enum'ы |
| `bank_account_types.py` | SavingsAccount, PremiumAccount, InvestmentAccount |
| `bank_system.py` | Client, Bank — управление клиентами и безопасность |
| `transaction.py` | Transaction, TransactionQueue, TransactionProcessor |
| `audit.py` | AuditLog, RiskAnalyzer — аудит и анализ рисков |
| `report.py` | ReportBuilder — отчёты, экспорт, графики |
| `demo.py` | Демонстрация всей системы |

### Архитектура

AbstractAccount
- account_id, owner, balance (Decimal), status
- автогенерация 8-символьного hex UUID

BankAccount(AbstractAccount)
- currency (RUB, USD, EUR, KZT, CNY)
- валидация входных данных
- проверка статуса аккаунта
- set_status() — публичный метод смены статуса

SavingsAccount(BankAccount)
- min_balance, monthly_rate (валидируются)
- apply_monthly_interest()

PremiumAccount(BankAccount)
- withdrawal_limit, overdraft_limit, commission (валидируются)

InvestmentAccount(BankAccount)
- portfolio {AssetType: сумма}, ключи валидируются
- project_yearly_growth() — только прирост

Client
- ФИО, ID, дата рождения (>= 18 лет), PIN (4 цифры)
- список счетов, контакты
- status — property: "active" / "blocked"
- блокировка после 3 неудачных попыток входа

Bank
- add_client, open_account, close_account, freeze_account, unfreeze_account
- authenticate_client — 3 ошибки = блокировка
- transfer — проверка владельца счета, атомарный откат при ошибке
- search_accounts — поиск по client_id
- get_total_balance, get_clients_ranking

Transaction
- ID, тип (transfer/deposit/withdrawal), сумма, валюта, комиссия
- отправитель, получатель, is_external
- статус (pending/completed/failed/cancelled), причина отказа
- приоритет (high/normal/low), scheduled_at, timestamps

TransactionQueue
- добавление, приоритет, отложенные операции, отмена
- release_delayed() — перевод готовых в основную очередь

TransactionProcessor
- конвертация валют (кросс-курс через USD)
- комиссия 2% за внешние переводы, внутренние бесплатно
- повторные попытки (max_retries=3), error_log
- запрет минуса для обычных счетов (Premium — можно)
- интеграция с RiskAnalyzer — блокировка HIGH-риск операций

AuditLog
- уровни: INFO, WARNING, CRITICAL
- хранение в памяти + опциональный JSON-lines файл
- фильтрация по уровню и времени

RiskAnalyzer
- крупная сумма, частые операции, новый получатель, ночные операции
- комбинация 2+ факторов = HIGH → блокировка
- отчёты: подозрительные операции, риск-профиль клиента, статистика ошибок

ReportBuilder
- отчёты: по клиенту, по банку, по рискам
- форматы: текст, JSON, CSV
- графики: pie (по типу), bar (балансы), line (движение баланса)

---
### Безопасность

- Ночные операции (00:00–05:00) блокируются
- Переводы выше порога не-контакту логируются как подозрительные
- HIGH-риск транзакции автоматически отклоняются процессором

---
### Типы данных

Все денежные значения — Decimal. На вход принимаются int, float, Decimal.

get_account_info() возвращает JSON-сериализуемый dict (Decimal → str)

---
### Exceptions

Все банковские исключения наследуются от AccountError.

Системные: AuthenticationError, ClientBlockedError, NightOperationError, RiskBlockedError.

---
### Запуск

```bash
python demo.py
```