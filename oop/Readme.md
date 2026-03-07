# Базовая модель банковских счетов

**Python >= 3.10** (используется `str | None` синтаксис)

### Архитектура

AbstractAccount
- account_id, owner, balance (Decimal), status
- автогенерация 8-символьного hex UUID
- deposit() - абстрактный
- withdraw() - абстрактный
- get_account_info() - абстрактный

BankAccount(AbstractAccount)
- currency (RUB, USD, EUR, KZT, CNY)
- валидация всех входных данных
- проверка статуса аккаунта
- __str__ с информацией об аккаунте

SavingsAccount(BankAccount)
- min_balance — минимальный остаток (валидируется)
- monthly_rate — месячная ставка (валидируется)
- apply_monthly_interest() — начисление процентов

PremiumAccount(BankAccount)
- withdrawal_limit — лимит на разовое снятие (валидируется)
- overdraft_limit — допустимый овердрафт (валидируется)
- commission — фиксированная комиссия (валидируется)

InvestmentAccount(BankAccount)
- portfolio — словарь {AssetType: сумма}, ключи валидируются
- project_yearly_growth() — прогноз годовой доходности (только прирост)

---
### Типы данных

Все денежные значения хранятся как Decimal. На вход принимаются int, float, Decimal.

get_account_info() возвращает JSON-сериализуемый dict (все Decimal конвертируются в str)

---
### Exceptions

Все наследуются от базового AccountError

В методах BankAccount служат сейчас плейсхолдерами вместо более конкретных ошибок

---
### Demo

Демонстрация производится при старте каждого скрипта:

bank_account.py:
- Создаются два аккаунта (активный и замороженный)
- Проводятся операции со счетами
- Операции по замороженному акку блокируются

bank_account_types.py:
- Создаются счета каждого типа
- Начисляются проценты на SavingsAccount
- Снятие с комиссией и овердрафтом на Premium
- Прогноз доходности по активам InvestmentAccount