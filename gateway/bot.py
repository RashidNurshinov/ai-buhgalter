#!/usr/bin/env python3
"""
Шлюз отдела маркетинга — MAX bot (long polling, эхо-режим, 1-й этап).

Безопасность/изоляция:
- Работает ТОЛЬКО через long polling (GET /updates): никаких входящих портов,
  никакого webhook, никакого nginx. Только исходящие HTTPS к platform-api2.max.ru.
- Не знает и не трогает другие сервисы на сервере.

1-й этап: принимает сообщения из MAX и отвечает эхом (проверка связи).
«Мозг» (вызов Claude API, ответы от команды) добавим 2-м этапом.
"""
import asyncio
import logging
import os
import sys
import time

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("max-gateway")

# Официальный хост MAX Bot API (dev.max.ru): использовать platform-api2, не platform-api.
MAX_API_BASE = os.environ.get("MAX_API_BASE", "https://platform-api2.max.ru")
MAX_BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN", "").strip()

# Путь к CA-бандлу (на случай, если MAX отдаёт сертификат от Минцифры РФ,
# которого нет в стандартном наборе). Если переменная задана и файл есть —
# используем его для проверки TLS. Проверку сертификата НЕ отключаем.
MAX_CA_BUNDLE = os.environ.get("MAX_CA_BUNDLE", "").strip()

HEARTBEAT_FILE = os.environ.get("HEARTBEAT_FILE", "/tmp/gateway_heartbeat")
POLL_TIMEOUT = int(os.environ.get("MAX_POLL_TIMEOUT", "30"))  # 0..90


def _verify():
    if MAX_CA_BUNDLE and os.path.exists(MAX_CA_BUNDLE):
        log.info("TLS: использую CA-бандл %s", MAX_CA_BUNDLE)
        return MAX_CA_BUNDLE
    return True


def _auth_headers():
    # MAX: токен передаётся в заголовке Authorization (query-параметр больше не поддерживается).
    return {"Authorization": MAX_BOT_TOKEN, "Content-Type": "application/json"}


def _touch_heartbeat():
    try:
        with open(HEARTBEAT_FILE, "w") as f:
            f.write(str(int(time.time())))
    except OSError:
        pass


def _extract_message(update: dict):
    """
    Достаём из события message_created адресата и текст.
    Делаем это защитно: схему MAX сверяем на первом реальном событии по логам.
    Возвращает (chat_id, user_id, text) — что-то может быть None.
    """
    msg = update.get("message") or {}
    recipient = msg.get("recipient") or {}
    body = msg.get("body") or {}
    sender = msg.get("sender") or {}
    chat_id = recipient.get("chat_id")
    user_id = recipient.get("user_id") or sender.get("user_id")
    text = body.get("text")
    return chat_id, user_id, text


async def send_message(client: httpx.AsyncClient, *, chat_id=None, user_id=None, text: str):
    params = {}
    if chat_id is not None:
        params["chat_id"] = chat_id
    elif user_id is not None:
        params["user_id"] = user_id
    else:
        log.warning("send_message: нет ни chat_id, ни user_id — пропускаю")
        return
    try:
        r = await client.post(
            f"{MAX_API_BASE}/messages",
            params=params,
            json={"text": text},
            headers=_auth_headers(),
            timeout=30,
        )
        if r.status_code != 200:
            log.warning("send_message HTTP %s: %s", r.status_code, r.text[:300])
    except httpx.HTTPError as e:
        log.warning("send_message ошибка сети: %s", e)


async def handle_update(client: httpx.AsyncClient, update: dict):
    utype = update.get("update_type")
    log.info("update: %s", utype)
    if utype != "message_created":
        return
    # На первом сообщении печатаем сырое событие — чтобы @artem сверил схему MAX.
    log.info("raw message_created: %s", str(update)[:1000])
    chat_id, user_id, text = _extract_message(update)
    if not text:
        return
    reply = f"🎯 Шлюз отдела маркетинга на связи. Ты написал: «{text}»"
    await send_message(client, chat_id=chat_id, user_id=user_id, text=reply)


async def poll_loop():
    if not MAX_BOT_TOKEN:
        log.error("MAX_BOT_TOKEN не задан. Контейнер работает, но ждёт токен в .env. "
                  "Добавь токен и перезапусти деплой.")
    marker = None
    async with httpx.AsyncClient(verify=_verify()) as client:
        # Разовая проверка, кто мы (не критично при ошибке).
        if MAX_BOT_TOKEN:
            try:
                me = await client.get(f"{MAX_API_BASE}/me", headers=_auth_headers(), timeout=30)
                log.info("GET /me -> HTTP %s: %s", me.status_code, me.text[:300])
            except httpx.HTTPError as e:
                log.warning("GET /me ошибка (возможно нужен CA Минцифры): %s", e)

        while True:
            _touch_heartbeat()
            if not MAX_BOT_TOKEN:
                await asyncio.sleep(30)
                continue
            params = {"timeout": POLL_TIMEOUT}
            if marker is not None:
                params["marker"] = marker
            try:
                r = await client.get(
                    f"{MAX_API_BASE}/updates",
                    params=params,
                    headers=_auth_headers(),
                    timeout=POLL_TIMEOUT + 15,
                )
                if r.status_code != 200:
                    log.warning("GET /updates HTTP %s: %s", r.status_code, r.text[:300])
                    await asyncio.sleep(5)
                    continue
                data = r.json()
                for upd in data.get("updates", []):
                    await handle_update(client, upd)
                marker = data.get("marker", marker)
            except httpx.HTTPError as e:
                log.warning("GET /updates ошибка сети: %s", e)
                await asyncio.sleep(5)


if __name__ == "__main__":
    log.info("Запуск шлюза MAX (long polling). API=%s", MAX_API_BASE)
    try:
        asyncio.run(poll_loop())
    except KeyboardInterrupt:
        log.info("Остановлен.")
