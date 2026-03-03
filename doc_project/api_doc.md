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

///////////////  SFERA_API документация ///////////////////////

SFERA_API документация -  [SFERA_API](https://courier-api.esphere.ru/Help)
Описание API для работы с сервисом "Сфера Документы"
Introduction
В данном разделе приводится актуальное описание методов API для работы с системой Сфера Документы. В связи с обновлением документации и самих методов в данном разделе приводятся только методы версии v2.0. Полный список методов, структур данных, перечислений, а также типовые задачи и примеры описаны в справочном руководстве.

Dispatch
Контроллер для работы с отложенной отправкой.

API	Description
PUT v2.0/delayedDispath	
Добавляет рассылку документа.

CorrelationEvent
Контроллер для организации работы с событиями взаимосвязей.

API	Description
POST v2.0/correlationEvent/create	
Создать подписку на события для компании по взаимосвязям.

GET v2.0/correlationEvent/events?token={token}&count={count}	
Получить события по подписке взаимосвязей.

GET v2.0/correlationEvent/subscriptions	
Получить список подписок на события по взаимосвязям для компании.

DocumentType
Контроллер для работы с типами документов.

API	Description
GET v2.0/documentType/code:{code}	
Возвращает карточку типа документа по заданному коду типа документа.

GET v2.0/documentType/id:{id}	
Возвращает карточку типа документа по заданному идентификатору типа документа.

GET v2.0/documentType/{id}	
Возвращает карточку типа документа по заданному идентификатору типа документа.

GET v2.0/documentType	
Возвращает список всех типов документов для компании.

RelationRequest
Контроллер для организации работы с взаимосвязями.

API	Description
GET v2.0/relation-request	
Возвращает список запросов на создание взаимосвязей.

PUT v2.0/relation-request	
Добавляет запрос на взаимосвязь.

POST v2.0/relation-request/{id}/reject	
Отклоняет запрос на создание взаимосвязи.

POST v2.0/relation-request/{id}/accept	
Меняет статус запроса на взаимосвязь на "Принят".

DELETE v2.0/relation-request/{id}	
Удаляет запрос на создание взаимосвязи.

GET v2.0/relation-request/{relationId}	
Возвращает запрос на создание взаимосвязи.

Verify
Контроллер для служебной функции проверки подписи.

API	Description
POST v2.0/verify/detachedSignature	
Метод проверяет подлинность подписанного содержимого файла. Для вызова данного метода не требуется аутентификация пользователя.

Privilege
Контроллер для организации работы с привилегиями.

API	Description
GET v2.0/privilege/codes?uid={uid}&companyId={companyId}	
Возвращает идентификатор участника ЭДО получателя.

Ticket
Возвращает данные о квитанциях.

API	Description
POST v2.0/ticket/unreplied	
Возвращает список неотвеченных квитанций.

GET v2.0/ticket/documentReply/{id}	
Создает ответную квитанцию по идентификатору документа и данным машиночитаемой доверенности.

POST v2.0/ticket/documentReply/{id}	
Создает ответную квитанцию по идентификатору документа и данным машиночитаемой доверенности.

POST v2.0/ticket/priRasxAdditionalInfo/document/{id}	
Возвращает идентификатор черновик квитанции - дополнительных сведений к документу о расхождениях при приемке для указанного документа о приемке материальных ценностей и (или) расхождениях, выявленных при их приемке.

TransportPackage
Контроллер для работы с методами над транспортными пакетами.

API	Description
GET internal/transportpackage/{id}/replicateinfo	
Получает информацию по идентификатору транспортного пакета.

DocumentInternal
Контроллер для работы с методами над документами.

API	Description
GET internal/document/{documentId}/logicalmessage/list	
Возвращает список логических сообщений по идентификатору документа.

GET internal/document/{documentId}/signatures	
Возвращает список ЭП документа.

Client
Контроллер для организации работы с клиентами.

API	Description
GET v2.0/client	
Возвращает список организаций.

GET v2.0/client/{id}	
Возвращает информацию о клиенте по его идентификатору в системе.

GET v2.0/client/code/{code}	
Возвращает информацию о клиенте по его идентификатору участника ЭДО в системе.

GET v2.0/client/{code}	
Возвращает информацию о клиенте по его идентификатору участника ЭДО в системе.

GET v2.0/client/self	
Возвращает информацию об организации.

POST v2.0/client/discover	
Возвращает список клиентов которые зарегистрированы в Сфера Документы и информацию по взаимосвязи.

GET v2.0/client/ediCode?receiverId={receiverId}&documentTypeId={documentTypeId}	
Возвращает идентификатор участника ЭДО получателя.

GET v2.0/client/ediCode?inn={inn}&documentTypeCode={documentTypeCode}&kpp={kpp}&hasRelation={hasRelation}	
Возвращает идентификатор участника ЭДО получателя.

GET v2.0/client/ediCodes?inn={inn}&kpp={kpp}	
Возвращает список всех ИдУчЭДО контрагента.

ClientAddress
Контроллер для работы с адресами организации.

API	Description
GET v2.0/client/{clientId}/address/legal	
Возвращает юридический адрес организации.

Mchd
Контроллер для методов работы с МЧД.

API	Description
POST v2.0/mchd/validateMchd	
Валидирует данные МЧД.

POST v2.0/mchd/validateMchdByTicket	
Валидирует данные МЧД по идентификатору транспортного документа и идентификатору подписи.

Operator
Контроллер для работы с методами для оператора ЭДО.

API	Description
GET internal/operator/{code}	
Информация об операторе ЭДО по его коду.

User
Контроллер для работы с данными пользователей.

API	Description
GET v2.0/user/{userId}/certificate	
Возвращает список всех действительных сертификатов пользователя.

PUT v2.0/user/{userId}/group	
Добавляет пользователя в группу.

PUT v2.0/user/{userId}/role	
Добавляет роль пользователю.

PUT v2.0/user/{userId}/roles	
Добавляет/назначает роли пользователю.

GET v2.0/user/self	
Получить данные текущего пользователя.

Marking
Контроллер для организации работы с сервисом взаимодействия с ГИСМТ.

API	Description
GET integration/marking/document/{documentId}/transportTicket	
Транспортная квитанция по идентификатору документа в ее составе.

GET integration/marking/document/{documentId}/technologicalTicket	
Технологическая квитанция по идентификатору документа в ее составе.

DzoPublicApi
Контроллер для работы с ДЗО.

API	Description
POST v2.0/dzo/deal/create	
Добавить сделку ДЗО.

PATCH v2.0/dzo/deal/update	
Обновить статус сделки.

PATCH v2.0/dzo/deal/update/batch	
Транзакционно добавить несколько записей в историю смены статусов сделки ДЗО.

GET v2.0/dzo/deal/{dealUid}	
Получить данные сделки ДЗО.

GET v2.0/dzo/deal/{dealUid}/services	
Получить список услуг сделки ДЗО.

InternationalLogistic
Контроллер для организации работы с клиентами.

API	Description
POST integration/internationalLogistic/deliveryStatus/update	
Изменение статуса заявки на доставку.

ExternalService
Контроллер для работы с внешними сервисами.

API	Description
POST v2.0/externalService/save	
Добавляет информацию о работе сервиса.

EmailDocument
Контроллер для работы с документами, отправленными на email.

API	Description
POST internal/emailDocument/createPaymentOrder	
Создание платежного поручения документа, отправленного на email.

GET internal/emailDocument/{documentUid}/paymentOrdersStatus	
Получает информацию по статусам платежных поручений для документа, отправленного на email.

PUT internal/emailDocument/addAndSend	
Создает документ на основе сведений из указанного черновика.

GET internal/emailDocument/{documentUid}/print	
Получить печатную форму почтового документа.

Package
Контроллер для организации работы с клиентами.

API	Description
POST v2.0/package	
Метод для объединения существующих документов в пакет.

GET v2.0/package/{id}	
Возвращает сведения о составе пакета документов.

PUT v2.0/package/{id}/documents	
Метод для добавления документов в существующий пакет.

DELETE v2.0/package/{id}/documents	
Метод для исключения документов из пакета.

Relation
Контроллер для организации работы с взаимосвязями.

API	Description
PUT v2.0/relation/{id}/documentType/{documentTypeId}	
Добавляет тип документа в существующую взаимосвязь между контрагентами.

DELETE v2.0/relation/{id}/documentType/{documentTypeId}	
Удаляет тип документа из существующей взаимосвязи.

POST v2.0/relation/client/assert	
Создать взаимосвязь.

PATCH v2.0/relation/{id}/setActive?isActive={isActive}	
Изменяет признак активности взаимосвязи.

PATCH v2.0/relation/{id}/setRelationSendPossibilityStatus	
Установка признака возможности отправки документа через 1С:Хаб.

POST v2.0/relation/getActiveRelations	
Возвращает список активных взаимосвязей.

GET v2.0/relation/getActiveRelationsForSystemAdmin?relationId={relationId}&clientId={clientId}	
Возвращает данные о взаимосвязи (системный администратор).

GET v2.0/relation/getRelationVerificationStatus?senderEdiCode={senderEdiCode}&receiverEdiCode={receiverEdiCode}	
Возвращает статус проверки запроса/взаимосвязи и её идентификатор по ИдУчЭДО.

POST v2.0/relation/correlated	
Получить список взаимосвязей по параметрам.

Certificate
Контроллер для работы с сертификатами пользователей.

API	Description
GET v2.0/certificate/{id}	
Возвращает сертификат пользователя по его идентификатору.

Document
Контроллер для организации работы с документами.

API	Description
GET v2.0/document/{id}/createFixationCancelContent	
Создает документ с данными по отмене фиксации, передаваемый в ГИСМТ.

POST v2.0/document/{id}/fixationCancel	
Отправка отмены фиксации в ГИСМТ.

GET v2.0/document/{id}	
Получение карточки документа (без содержимого документа).

GET v2.0/document/{parentId}/ref/{id}	
Получение карточки документа (без содержимого документа).

GET v2.0/document/{id}/auditCard	
Возвращает карточку документа для аудита.

GET v2.0/document/{parentId}/ref/{id}/pdf	
Печать в pdf.

GET v2.0/document/{id}/comment	
Получение списка комментариев к документу.

GET v2.0/document/{id}/comments	
Получение списка комментариев к документу.

PUT v2.0/document/{id}/comment	
Добавляет комментарий к документу.

PATCH v2.0/document/{documentId}/signer	
Метод API для редактирования подписанта в документе.

GET v2.0/document/{id}/content	
Получение содержимого файла.

PUT v2.0/document/{id}/content	
Обновление содержимого файла.

GET v2.0/document/{id}/history	
Получить историю действий с документом.

GET v2.0/document/{documentId}/client/{clientId}/history	
Получить историю действий с документом.

POST v2.0/document/{id}/acceptTitle	
Создает новую форму для выбранного типа документа.

POST v2.0/document/cards	
Детальные данные по документам.

GET v2.0/document/{id}/externalServices?serviceCode={serviceCode}	
Получает информацию о данных внешних сервисов.

POST v2.0/document/changeDocumentUser	
Назначить документ на указанного пользователя.

GET v2.0/document/{id}/roamingInfo	
Получение информации о статусе отправки документа в роуминг.

GET v2.0/document/{documentId}/print?isPdfWithStamp={isPdfWithStamp}	
Отправляет документ на печать.

GET v2.0/document/pdfByTaskId/{taskId}	
Возвращает pdf документ после печати.

GET v2.0/document/getIncompletePrintTaskInfoList	
Возвращает идентификаторы незавершенных задач по печати документов.

PUT v2.0/document/cancelPrintTasks	
Отменяет задачи печати документов.

POST v2.0/document/{id}/attributes	
Возвращает список атрибутов документа.

GET v2.0/document/{id}/property	
Получение списка дополнительных свойств документа.

GET v2.0/document/{id}/property/{key}	
Возвращает значение дополнительного свойства документа по заданному ключу.

PUT v2.0/document/{id}/property	
Добавляет дополнительные свойства документа.

GET v2.0/document/{id}/createAvoidanceRequest?reason={reason}	
Формирует запрос на предложение об аннулировании документа.

POST v2.0/document/{id}/createAvoidanceRequest	
Формирует запрос на предложение об аннулировании документа.

POST v2.0/document/{id}/avoidanceRequest	
Отправляет запрос на предложение об аннулировании документа.

GET v2.0/document/{id}/createAvoidanceRequestClarificationNotice?reason={reason}	
Формирует ответную квитанцию отказ от предложения на аннулирование документа (УОУ).

POST v2.0/document/{id}/createAvoidanceRequestClarificationNotice?reason={reason}	
Формирует ответную квитанцию отказ от предложения на аннулирование документа (УОУ).

POST v2.0/document/{id}/acceptAvoidanceRequest	
Принятие документа на аннулирование.

POST v2.0/document/{id}/rejectAvoidanceRequest	
Отказ принятия документа на аннулирование.

GET v2.0/document/{id}/getAvoidanceRequest	
Возвращает входящий запрос на предложение об аннулировании документа.

AddressRule
Контроллер для работы с правилами адресования.

API	Description
POST v2.0/addressRule/find	
Поиск абонента по параметрам правила адресования.

Subscription
Контроллер для работы с подписками и событиями.

API	Description
GET v2.0/subscription	
Возвращает список подписок на события.

GET v2.0/subscription/{token}	
Возвращает информацию о подписке пользователя.

PUT v2.0/subscription?isRestricted={isRestricted}	
Добавляет новую подписку. Максимальное количество подписок на одну компанию ограничено 5. При превышении данного лимита будет возвращена ошибка с кодом ER-20005.

DELETE v2.0/subscription/{token}	
Удаляет подписку и все события в ней.

GET v2.0/subscription/{token}/event?count={count}	
Возвращает события по заданной подписке.

GET v2.0/subscription/{token}/event/totals?count={count}	
Возвращает события по заданной подписке с количеством событий.

DELETE v2.0/subscription/{token}/event/{eventId}	
Удаляет событие из очереди событий подписки.

DELETE v2.0/subscription/{token}/event	
Удаляет события из очереди событий подписки.