# Шлюз отдела маркетинга (MAX bot)

Always-on шлюз: принимает сообщения из мессенджера **MAX** и отвечает.
1-й этап — эхо-режим (проверка связи). 2-й этап — «мозг» (вызов Claude API,
ответы от команды субагентов) и крон 9:00.

## Почему это безопасно для других проектов на сервере
- **Long polling**, а не webhook: контейнер **не открывает ни одного порта**,
  только сам ходит исходящими HTTPS в `platform-api2.max.ru`. nginx трогать не надо.
- Отдельная папка `/opt/ai-marketing-gateway`, отдельный compose-проект
  `marketing-gateway`, отдельный контейнер `marketing_gateway`, своя docker-сеть.
- Деплой командует **только своим** проектом. Никаких `docker system prune`,
  остановки чужих контейнеров или глобальных команд.

## Деплой через GitHub Actions (основной способ)
1. На GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
   Добавь (значения вводишь сам, в код/чат они не попадают):
   - `SERVER_HOST` = `82.117.87.252`
   - `SERVER_USER` = `root` (или отдельный пользователь)
   - `SERVER_SSH_PASSWORD` = пароль  *(или `SERVER_SSH_KEY` = приватный ключ)*
   - `MAX_BOT_TOKEN` = токен бота MAX
   - `SERVER_SSH_PORT` — только если SSH не на 22
2. Любой push в ветку (в папку `gateway/`) запускает workflow
   **Deploy marketing gateway**, либо запусти его вручную (Actions → Run workflow).
3. Workflow копирует файлы на сервер и поднимает только наш контейнер.

## Ручной деплой на сервере (запасной)
```bash
cd /opt/ai-marketing-gateway/gateway
MAX_BOT_TOKEN=xxxx ./deploy.sh
```

## Проверка / управление (только наш проект)
```bash
cd /opt/ai-marketing-gateway/gateway
docker compose ps
docker compose logs -f
docker compose down      # останавливает ТОЛЬКО наш контейнер
```

## Если TLS к MAX не проходит (сертификат Минцифры РФ)
Положи корневой сертификат рядом и укажи путь:
```
MAX_CA_BUNDLE=/app/russian_trusted_root_ca.pem
```
Проверку TLS мы НЕ отключаем — только добавляем доверенный корень.
