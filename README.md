# 🧠 ИИ-Бухгалтер

Веб-приложение для автоматизации бухгалтерского и налогового учёта ИП на **УСН «Доходы минус расходы» + НДС 22%** (Россия, 2026 год).

## 🎯 Ключевые возможности

- 📄 **Загрузка документов** — XML, CSV, Excel, PDF, изображения (drag & drop)
- 🤖 **OCR + ИИ-распознавание** — Tesseract, EasyOCR + Claude Sonnet через OpenRouter
- 📊 **Автоклассификация операций** — доходы/расходы/личное через LLM
- 📖 **Книги учёта** — КУДиР, книга покупок, книга продаж (автогенерация)
- 💰 **Расчёт налогов** — УСН 15%, НДС 22%, НДФЛ, страховые взносы
- 📋 **Генерация деклараций** — XML по формату ФНС с XSD-валидацией
- 📅 **Налоговый календарь** — сроки сдачи, напоминания по email
- 🧠 **AI-Агент** — Agent-First архитектура с tool calling (чат, команды, проактивные проверки)
- 📈 **Дашборд** — сводка по доходам/расходам/налогам

## 🛠 Технологический стек

| Компонент | Технология |
|-----------|------------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic |
| **Frontend** | React 18, TypeScript, Vite, Ant Design |
| **ИИ** | OpenRouter API (Claude Sonnet/Haiku), Tesseract OCR, EasyOCR |
| **БД** | PostgreSQL, Redis |
| **Очереди** | Celery + Redis |
| **Инфра** | Docker Compose, nginx |

## 🚀 Быстрый старт

### Предварительные требования

- Docker и Docker Compose
- Python 3.12+ (для локальной разработки)
- Node.js 18+ (для фронтенда)

### 1. Клонирование и настройка

```bash
git clone <repo-url> ai-buhgalter
cd ai-buhgalter

# Создать файл настроек из шаблона
cp .env.example .env
# Отредактировать .env — указать:
#   - OPENROUTER_API_KEY (обязательно для ИИ)
#   - JWT_SECRET_KEY (сменить на production)
#   - SMTP_* (для email-уведомлений)
```

### 2. Запуск через Docker Compose

```bash
cd docker
docker-compose up -d
```

Это запустит:
- **PostgreSQL** — порт 5432
- **Redis** — порт 6379
- **Backend (FastAPI)** — порт 8000
- **Frontend (React)** — порт 3000
- **Celery Worker** — фоновые задачи
- **Celery Beat** — расписание

### 3. Запуск для разработки (без Docker)

#### Backend

```bash
cd backend

# Виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или: venv\Scripts\activate  # Windows

# Зависимости
pip install -r requirements.txt

# Миграции БД
alembic upgrade head

# Запуск сервера
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend

```bash
cd frontend

# Зависимости
npm install

# Dev-сервер
npm run dev
```

#### Celery (фоновые задачи)

```bash
cd backend

# Worker
celery -A app.core.celery_app worker --loglevel=info

# Beat (расписание)
celery -A app.core.celery_app beat --loglevel=info
```

### 4. Проверка работоспособности

- **API Docs:** http://localhost:8000/api/docs
- **Frontend:** http://localhost:3000
- **Health check:** http://localhost:8000/api/health

## 📁 Структура проекта

```
├── backend/
│   ├── app/
│   │   ├── api/v1/          # FastAPI роутеры
│   │   ├── core/            # Конфиг, БД, безопасность, Celery
│   │   ├── models/          # SQLAlchemy модели (20 таблиц)
│   │   ├── schemas/         # Pydantic v2 схемы
│   │   ├── services/        # Бизнес-логика
│   │   ├── tasks/           # Celery задачи
│   │   ├── constants/       # Enum-ы, ставки, календарь
│   │   ├── prompts/         # Системные промпты для ИИ
│   │   └── utils/           # Валидаторы, утилиты
│   ├── alembic/             # Миграции БД
│   └── tests/               # Тесты
├── frontend/
│   └── src/
│       ├── pages/           # Страницы (12 шт.)
│       ├── components/      # React-компоненты
│       ├── api/             # API-клиент (axios)
│       └── store/           # Zustand stores
├── docker/                  # Docker Compose конфиги
├── doc_project/             # Проектная документация
│   ├── ТЗ_обобщённое.md
│   ├── СПРАВОЧНИК_СУЩНОСТЕЙ.md
│   ├── ПЛАН_РЕАЛИЗАЦИИ.md
│   └── АРХИТЕКТУРА_AI_AGENT.md
└── storage/uploads/         # Загруженные файлы
```

## 📊 API Эндпоинты

| Группа | Путь | Описание |
|--------|------|----------|
| Аутентификация | `/api/v1/auth/*` | Регистрация, вход, JWT |
| Пользователь | `/api/v1/users/*` | Профиль, настройки |
| Файлы | `/api/v1/files/*` | Загрузка, статус обработки |
| AI-Агент | `/api/v1/agent/*` | Чат, команды, подтверждения |
| Операции | `/api/v1/operations/*` | Банковские операции |
| КУДиР | `/api/v1/kudir/*` | Книга доходов и расходов |
| Книга покупок | `/api/v1/purchase-book/*` | Входящий НДС |
| Книга продаж | `/api/v1/sales-book/*` | Исходящий НДС |
| Налоги | `/api/v1/taxes/*` | Расчёт налогов |
| Декларации | `/api/v1/declarations/*` | Генерация XML ФНС |
| Календарь | `/api/v1/calendar/*` | Налоговый календарь |
| Дашборд | `/api/v1/dashboard/*` | Сводные данные |

## ⚖️ Налоговые ставки 2026

| Налог | Ставка | Примечание |
|-------|--------|------------|
| НДС | 22% | Основная (с 01.01.2026) |
| УСН | 15% / 20% | Доходы минус расходы |
| Мин. налог УСН | 1% от доходов | ст. 346.18 НК РФ |
| НДФЛ | 13% / 15% | Свыше 5 млн — 15% |
| Взносы ИП | 53 658 ₽ | + 1% свыше 300 000 ₽ |
| Страх. взносы | 30% / 15.1% | За сотрудников |

## 🔧 Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

| Переменная | Описание | Обязательно |
|-----------|----------|-------------|
| `DATABASE_URL` | PostgreSQL URL | ✅ |
| `REDIS_URL` | Redis URL | ✅ |
| `JWT_SECRET_KEY` | Секрет для JWT | ✅ |
| `OPENROUTER_API_KEY` | API-ключ OpenRouter | ✅ (для ИИ) |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | SMTP для email | Для уведомлений |

## 📝 Лицензия

Proprietary. All rights reserved.