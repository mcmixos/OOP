# Базовая модель банковских счетов

**Python >= 3.10** (используется `str | None` синтаксис)

### Структура

| Файл | Описание |
|---|---|
| `bank_account.py` | AbstractAccount, BankAccount, исключения, enum'ы |
| `bank_account_types.py` | SavingsAccount, PremiumAccount, InvestmentAccount |
| `bank_system.py` | Client, Bank — управление клиентами и безопасность |
| `demo.py` | Демонстрация всей системы |

### Архитектура

AbstractAccount
- account_id, owner, balance (Decimal), status
- автогенерация 8-символьного hex UUID
- deposit(), withdraw(), get_account_info() — абстрактные

BankAccount(AbstractAccount)
- currency (RUB, USD, EUR, KZT, CNY)
- валидация входных данных
- проверка статуса аккаунта

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
- блокировка после 3 неудачных попыток входа

Bank
- add_client, open_account, close_account, freeze_account, unfreeze_account
- authenticate_client — 3 ошибки = блокировка
- transfer — перевод между счетами
- search_accounts — поиск по client_id
- get_total_balance, get_clients_ranking

---
### Безопасность

- Ночные операции (00:00–05:00) блокируются
- Переводы выше порога не-контакту логируются как подозрительные

---
### Типы данных

Все денежные значения — Decimal. На вход принимаются int, float, Decimal.

get_account_info() возвращает JSON-сериализуемый dict (Decimal → str)

---
### Exceptions

Все банковские исключения наследуются от AccountError.

Системные: AuthenticationError, ClientBlockedError, NightOperationError.

---
### Запуск

```bash
python demo.py