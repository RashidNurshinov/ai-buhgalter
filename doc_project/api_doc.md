//Документация по настройке Т-банка (бывший Тинькофф)
Для работы с **банковскими выписками** и **операциями по счетам** в T-Bank (бывший Тинькофф) используется **T-API для бизнеса** (Open API для юрлиц и ИП). Это именно то, что вам нужно для расчётных счетов компании.

Основной раздел документации → **https://developer.tbank.ru/docs/api**  
Конкретно по выпискам и операциям → категория **Счета и выписки** (https://developer.tbank.ru/docs/api/scheta-i-vipiski или аналогичный путь).

Главный метод для получения операций / выписки — **GET /api/v1/statement**.

### 1. Регистрация и получение доступа (самое важное для старта)

1. Зайдите в личный кабинет Тинькофф Бизнес → раздел **Интеграции** → **T-API** (или **Открытый API**).
2. Создайте новое приложение / подключите API.
3. Получите **токен авторизации** (Bearer Token).  
   Это строка вида `TinkoffOpenApi...` или `eyJ...`.
   - Для продакшена — реальный токен.
   - Для тестов — используйте **песочницу** (sandbox): https://business.tbank.ru/openapi/sandbox (отдельный тестовый токен и тестовые счета).

4. **Важно**: у токена должны быть выданы права (scopes / доступы):  
   - opensme/inn/[ваш_ИНН]/kpp/[ваш_КПП]/...  
   - Конкретно для выписок: обычно **Информация об операциях компании** или **opensme/.../bank-statements/get**, **account-operations/get** и т.п.  
   Права настраиваются при создании приложения или в кабинете.

Если прав нет → запрос вернёт 403 Forbidden.

### 2. Основной эндпоинт для выписки и операций

**GET https://business.tbank.ru/openapi/api/v1/statement**

- **Базовый URL продакшн**: `https://business.tbank.ru/openapi/api/v1/`  
- **Песочница**: `https://business.tbank.ru/openapi/sandbox/api/v1/`

Параметры (query string, все в URL после ?):

- **accountNumber** (обязательный) — 20-значный номер расчётного счёта (например 40702810510000710417)
- **from** (обязательный) — начало периода в формате ISO 8601 с Z (UTC), например `2025-01-01T00:00:00Z`
- **to** (опционально) — конец периода, по умолчанию — текущий момент
- Другие возможные (зависит от версии):  
  - cursor / lastOperationId — для пагинации (если операций > определённого количества)  
  - operationId — фильтр по конкретной операции

Ограничение: ~20 запросов в секунду (RPS).

**Пример запроса (cURL)**:

```bash
curl --location --request GET 'https://business.tbank.ru/openapi/api/v1/statement?accountNumber=40702810510000710417&from=2025-02-01T00:00:00Z&to=2025-03-01T23:59:59Z' \
--header 'Accept: application/json' \
--header 'Authorization: Bearer ваш_очень_длинный_токен_здесь'
```

**Типичный ответ (JSON)** — массив операций + балансы (с декабря 2023 добавлены балансы):

```json
{
  "operations": [
    {
      "operationId": "abc123-def456",
      "date": "2025-02-15T14:30:00Z",
      "amount": {
        "currency": "RUB",
        "value": "15000.00"
      },
      "type": "DEBIT" | "CREDIT",
      "description": "Оплата по счёту №123 от ООО Ромашка",
      "contragent": { ... },
      "status": "OK",
      ...
    },
    ...
  ],
  "openingBalance": { "value": "500000.00", "currency": "RUB" },
  "closingBalance": { ... },
  "totalDebit": "...",
  "totalCredit": "...",
  "nextCursor": "xyz789"   // если есть следующая страница
}
```

- Данные доступны примерно с июня 2023 (по документации).
- Старый метод `/bank-statement` устарел — не используйте.

### 3. Другие полезные связанные методы

- **Получить список счетов** — GET /api/v1/accounts/v4 (или v3)  
  → чтобы узнать все расчётные счета компании и их accountNumber.

- **Вебхуки** (рекомендуется для реального времени):  
  Настройте вебхук на событие «Операция по счёту» → банк будет слать POST на ваш URL при каждой новой операции.  
  Документация: https://developer.tbank.ru/docs/products/account-info → раздел вебхуки.

- **Баланс по счёту** — часто приходит в той же выписке, отдельного метода может не быть.

### 4. Как настроить программу (пошагово)

**Python пример (requests)**:

```python
import requests

BASE_URL = "https://business.tbank.ru/openapi/api/v1"
TOKEN = "TinkoffOpenApi ваш_токен"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json"
}

params = {
    "accountNumber": "40702810500000000000",  # ваш счёт
    "from": "2025-01-01T00:00:00Z",
    "to": "2025-03-02T23:59:59Z"
}

response = requests.get(f"{BASE_URL}/statement", headers=headers, params=params)

if response.status_code == 200:
    data = response.json()
    print("Операций:", len(data.get("operations", [])))
    print("Входящий остаток:", data.get("openingBalance"))
    for op in data.get("operations", []):
        print(f"{op['date']} | {op['amount']['value']} ₽ | {op['description']}")
else:
    print("Ошибка:", response.status_code, response.text)
```

**Советы по реализации**:
- Обрабатывайте пагинацию (если есть nextCursor — делайте следующий запрос с cursor=...).
- Храните токен безопасно (не в git!).
- Используйте песочницу для отладки.
- Лимиты — 20 rps, не спамьте запросами каждые 5 секунд.
- Если операций очень много (>50 тыс. за период) — старый метод возвращал ошибку, новый может требовать разбивки по периодам.

Сфера 