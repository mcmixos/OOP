# Базовая модель банковских счетов

### Архитектура

AbstractAccount
- account_id, owner, balance, status
- автогенерация 8-символьного hex UUID
- deposit() - абстрактный
- withdraw() - абстрактный
- get_account_info() - абстрактный

BankAccount(AbstractAccount)
- currency (RUB, USD, EUR, KZT, CNY)
- валидация всех входных данных
- проверка статуса аккаунта
- __str__ с ифнормацией об аккаунте

SavingsAccount(BankAccount)
- min_balance — минимальный остаток
- monthly_rate — месячная ставка
- apply_monthly_interest() — начисление процентов

PremiumAccount(BankAccount)
- withdrawal_limit — лимит на разовое снятие
- overdraft_limit — допустимый овердрафт (уход в минус по счету)
- commission — фиксированная комиссия

InvestmentAccount(BankAccount)
- portfolio — пока просто словарь {AssetType: сумма}
- project_yearly_growth() — прогноз годовой доходности на основе имеющихся активов

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