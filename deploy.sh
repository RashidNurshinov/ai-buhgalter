#!/bin/bash
# ============================================
# Скрипт деплоя ИИ-Бухгалтер на сервер
# ============================================
set -e

SERVER="root@138.124.108.144"
REMOTE_DIR="/opt/ai-buhgalter"
SSH_OPTS="-o StrictHostKeyChecking=no"

echo "=========================================="
echo "  Деплой ИИ-Бухгалтер"
echo "=========================================="

# 1. Подготовка сервера
echo ""
echo ">>> [1/5] Подготовка сервера..."
ssh $SSH_OPTS $SERVER << 'REMOTE_SETUP'
# Обновляем систему
apt-get update -qq

# Устанавливаем Docker если нет
if ! command -v docker &> /dev/null; then
    echo "Устанавливаем Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Устанавливаем Docker Compose plugin если нет
if ! docker compose version &> /dev/null; then
    echo "Устанавливаем Docker Compose plugin..."
    apt-get install -y -qq docker-compose-plugin
fi

# Создаём директорию проекта
mkdir -p /opt/ai-buhgalter

echo "Сервер готов!"
docker --version
docker compose version
REMOTE_SETUP

# 2. Синхронизация файлов
echo ""
echo ">>> [2/5] Синхронизация файлов на сервер..."

# Используем rsync если доступен, иначе scp
if command -v rsync &> /dev/null; then
    rsync -avz --progress \
        --exclude 'node_modules' \
        --exclude '__pycache__' \
        --exclude '.git' \
        --exclude '*.pyc' \
        --exclude '.env' \
        --exclude 'venv' \
        --exclude '.venv' \
        --exclude 'postgres_data' \
        --exclude 'test_storage' \
        --exclude '.mypy_cache' \
        --exclude '.pytest_cache' \
        --exclude '.ruff_cache' \
        --exclude 'dist' \
        --exclude 'build' \
        -e "ssh $SSH_OPTS" \
        ./ $SERVER:$REMOTE_DIR/
else
    echo "rsync не найден, используем scp..."
    scp -r $SSH_OPTS \
        backend docker frontend storage .env.example \
        docker/docker-compose.prod.yml \
        $SERVER:$REMOTE_DIR/
fi

# 3. Настройка .env
echo ""
echo ">>> [3/5] Настройка .env на сервере..."
ssh $SSH_OPTS $SERVER << 'REMOTE_ENV'
cd /opt/ai-buhgalter

if [ ! -f .env ]; then
    echo "Создаём .env из .env.example..."
    cp .env.example .env

    # Генерируем безопасные ключи
    APP_SECRET=$(openssl rand -hex 32)
    JWT_SECRET=$(openssl rand -hex 32)
    PG_PASSWORD=$(openssl rand -hex 16)

    # Подставляем значения для production
    sed -i "s|APP_ENV=development|APP_ENV=production|g" .env
    sed -i "s|APP_DEBUG=true|APP_DEBUG=false|g" .env
    sed -i "s|change-me-in-production-use-openssl-rand-hex-32|${APP_SECRET}|g" .env
    sed -i "s|change-me-jwt-secret-use-openssl-rand-hex-32|${JWT_SECRET}|g" .env

    # Обновляем URL-ы для Docker-сети
    sed -i "s|postgresql+asyncpg://postgres:postgres@localhost:5432/ai_buhgalter|postgresql+asyncpg://postgres:postgres@postgres:5432/ai_buhgalter|g" .env
    sed -i "s|redis://localhost:6379/0|redis://redis:6379/0|g" .env
    sed -i "s|redis://localhost:6379/1|redis://redis:6379/1|g" .env
    sed -i "s|redis://localhost:6379/2|redis://redis:6379/2|g" .env

    echo ".env создан с production-настройками"
else
    echo ".env уже существует, пропускаем"
fi
REMOTE_ENV

# 4. Сборка и запуск
echo ""
echo ">>> [4/5] Сборка и запуск Docker контейнеров..."
ssh $SSH_OPTS $SERVER << 'REMOTE_BUILD'
cd /opt/ai-buhgalter/docker

# Останавливаем старые контейнеры если есть
docker compose -f docker-compose.prod.yml down 2>/dev/null || true

# Собираем и запускаем
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

# Ждём пока всё поднимется
echo "Ожидаем запуска сервисов..."
sleep 10

# Показываем статус
docker compose -f docker-compose.prod.yml ps
REMOTE_BUILD

# 5. Миграции БД
echo ""
echo ">>> [5/5] Применение миграций БД..."
ssh $SSH_OPTS $SERVER << 'REMOTE_MIGRATE'
cd /opt/ai-buhgalter

# Запускаем миграции внутри контейнера backend
docker exec ai_buhgalter_backend alembic upgrade head

echo ""
echo "=========================================="
echo "  ✅ Деплой завершён!"
echo "  🌐 http://138.124.108.144"
echo "  📡 API: http://138.124.108.144/api/health"
echo "=========================================="
REMOTE_MIGRATE