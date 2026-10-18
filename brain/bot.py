#!/usr/bin/env python3
"""
Мозг отдела маркетинга — MAX bot -> Claude Code CLI (2-й этап шлюза).

Сообщение из MAX -> `claude -p` в рабочей папке с памятью проекта
(CLAUDE.md, .claude/agents/, doc_project/marketing/) -> ответ обратно в MAX.
У каждого чата MAX своя сессия Claude Code (--resume), поэтому разговор помнится.

Безопасность/изоляция:
- Long polling: контейнер не слушает ни одного порта.
- Отвечаем ТОЛЬКО пользователям из MAX_ALLOWED_USER_IDS. Остальным — отказ и их ID
  (чтобы владелец мог добавить себя). Пустой список = никого не пускаем.
- Claude Code работает внутри контейнера под непривилегированным пользователем
  и только с явным списком инструментов (ALLOWED_TOOLS ниже).

Команды в чате: /new — начать разговор заново, /id — показать свой ID в MAX.
"""
import asyncio
import json
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
log = logging.getLogger("max-brain")

MAX_API_BASE = os.environ.get("MAX_API_BASE", "https://platform-api2.max.ru")
MAX_BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN", "").strip()
ALLOWED_USER_IDS = {
    s.strip() for s in os.environ.get("MAX_ALLOWED_USER_IDS", "").split(",") if s.strip()
}

WORKSPACE = os.environ.get("WORKSPACE", "/data/workspace")
SESSIONS_FILE = os.environ.get("SESSIONS_FILE", "/data/sessions.json")
HEARTBEAT_FILE = os.environ.get("HEARTBEAT_FILE", "/tmp/gateway_heartbeat")
POLL_TIMEOUT = int(os.environ.get("MAX_POLL_TIMEOUT", "30"))
CLAUDE_TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT", "900"))
CLAUDE_MAX_TURNS = os.environ.get("CLAUDE_MAX_TURNS", "40")
MAX_TEXT_LIMIT = 3900  # у MAX лимит 4000 символов на сообщение

SYSTEM_PROMPT = (
    "Ты общаешься с @boss (Рашидом) через мессенджер MAX. Ты — @director, главный менеджер "
    "по рекламе. Отвечай по-русски, коротко и по делу, как в мессенджере: без таблиц и "
    "длинных markdown-блоков. Команду (Дамир, Алия, Даша, Элина, Ирина, Артём) зови через "
    "субагентов из .claude/agents/. Важные решения записывай в doc_project/marketing/STATE.md "
    "и CHAT.md. Токены и пароли никогда не выводи в ответ."
)

# Явный список того, что Claude Code может делать без спроса. Всё остальное в режиме -p
# автоматически запрещено: чтение — только рабочая папка, запись — только папка маркетинга,
# команды — только наши скрипты. Никакого bypassPermissions.
ALLOWED_TOOLS = [
    "Task",
    "Write(doc_project/marketing/**)",
    "Edit(doc_project/marketing/**)",
    "Bash(python3 doc_project/marketing/scripts/*)",
    "Bash(bash doc_project/marketing/scripts/*)",
]

_chat_locks: dict = {}


def _auth_headers():
    return {"Authorization": MAX_BOT_TOKEN, "Content-Type": "application/json"}


def _touch_heartbeat():
    try:
        with open(HEARTBEAT_FILE, "w") as f:
            f.write(str(int(time.time())))
    except OSError:
        pass


def _load_sessions() -> dict:
    try:
        with open(SESSIONS_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_sessions(sessions: dict):
    tmp = SESSIONS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(sessions, f)
    os.replace(tmp, SESSIONS_FILE)


def _extract_message(update: dict):
    """Возвращает (chat_id, sender_id, text) из события message_created."""
    msg = update.get("message") or {}
    recipient = msg.get("recipient") or {}
    body = msg.get("body") or {}
    sender = msg.get("sender") or {}
    return recipient.get("chat_id"), sender.get("user_id"), body.get("text")


def _split(text: str):
    while text:
        if len(text) <= MAX_TEXT_LIMIT:
            yield text
            return
        cut = text.rfind("\n", 0, MAX_TEXT_LIMIT)
        if cut < MAX_TEXT_LIMIT // 2:
            cut = MAX_TEXT_LIMIT
        yield text[:cut]
        text = text[cut:].lstrip("\n")


async def send_message(client: httpx.AsyncClient, *, chat_id=None, user_id=None, text: str):
    params = {"chat_id": chat_id} if chat_id is not None else {"user_id": user_id}
    for part in _split(text or "(пустой ответ)"):
        try:
            r = await client.post(
                f"{MAX_API_BASE}/messages", params=params, json={"text": part},
                headers=_auth_headers(), timeout=30,
            )
            if r.status_code != 200:
                log.warning("send_message HTTP %s: %s", r.status_code, r.text[:300])
        except httpx.HTTPError as e:
            log.warning("send_message ошибка сети: %s", e)


async def ask_claude(text: str, session_id):
    """Запускает claude -p. Возвращает (ответ, session_id)."""
    cmd = [
        "claude", "-p", text,
        "--output-format", "json",
        "--max-turns", CLAUDE_MAX_TURNS,
        "--allowedTools", *ALLOWED_TOOLS,
        "--append-system-prompt", SYSTEM_PROMPT,
    ]
    if session_id:
        cmd += ["--resume", session_id]
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=WORKSPACE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=CLAUDE_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return f"⏱ Не уложился в {CLAUDE_TIMEOUT // 60} мин. Разбей задачу помельче.", session_id
    try:
        data = json.loads(out.decode() or "{}")
    except ValueError:
        log.warning("claude: не JSON. stderr=%s", err.decode()[:500])
        return "⚠️ Claude Code вернул что-то непонятное, глянь логи контейнера.", session_id
    meta = {k: data.get(k) for k in ("subtype", "is_error", "num_turns", "permission_denials")}
    log.info("claude meta: %s stderr=%s", str(meta)[:800], err.decode()[-500:])
    result = data.get("result")
    if not result:
        result = (f"⚠️ Claude Code не дал текста (subtype={meta['subtype']}, "
                  f"шагов={meta['num_turns']}). stderr: {err.decode()[-300:] or '—'}")
    return result, data.get("session_id") or session_id


async def handle_message(client: httpx.AsyncClient, sessions: dict, update: dict):
    chat_id, sender_id, text = _extract_message(update)
    if not text:
        return
    reply_to = {"chat_id": chat_id} if chat_id is not None else {"user_id": sender_id}

    if text.strip() == "/id":
        await send_message(client, **reply_to, text=f"Твой ID в MAX: {sender_id}")
        return
    if str(sender_id) not in ALLOWED_USER_IDS:
        log.info("отказ: user_id=%s не в списке", sender_id)
        await send_message(
            client, **reply_to,
            text=f"Доступ закрыт. Твой ID в MAX: {sender_id}. "
                 "Владелец добавляет его в секрет MAX_ALLOWED_USER_IDS.",
        )
        return

    key = str(chat_id if chat_id is not None else sender_id)
    if text.strip() == "/new":
        sessions.pop(key, None)
        _save_sessions(sessions)
        await send_message(client, **reply_to, text="🧹 Начали разговор заново. Память проекта на месте.")
        return

    lock = _chat_locks.setdefault(key, asyncio.Lock())
    if lock.locked():
        await send_message(client, **reply_to, text="⏳ Ещё работаю над прошлым, это возьму следом.")
    async with lock:
        await send_message(client, **reply_to, text="🎯 Принял, думаю…")
        started = time.time()
        answer, new_session = await ask_claude(text, sessions.get(key))
        log.info("claude ответил за %.0f c (чат %s)", time.time() - started, key)
        if new_session:
            sessions[key] = new_session
            _save_sessions(sessions)
        await send_message(client, **reply_to, text=answer)


async def poll_loop():
    if not MAX_BOT_TOKEN:
        log.error("MAX_BOT_TOKEN не задан — жду токен в .env.")
    if not ALLOWED_USER_IDS:
        log.warning("MAX_ALLOWED_USER_IDS пуст — бот никому не отвечает по делу, только /id.")
    sessions = _load_sessions()
    marker = None
    tasks = set()
    async with httpx.AsyncClient() as client:
        if MAX_BOT_TOKEN:
            try:
                me = await client.get(f"{MAX_API_BASE}/me", headers=_auth_headers(), timeout=30)
                log.info("GET /me -> HTTP %s", me.status_code)
            except httpx.HTTPError as e:
                log.warning("GET /me ошибка: %s", e)

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
                    f"{MAX_API_BASE}/updates", params=params,
                    headers=_auth_headers(), timeout=POLL_TIMEOUT + 15,
                )
                if r.status_code != 200:
                    log.warning("GET /updates HTTP %s: %s", r.status_code, r.text[:300])
                    await asyncio.sleep(5)
                    continue
                data = r.json()
                for upd in data.get("updates", []):
                    if upd.get("update_type") != "message_created":
                        continue
                    # Не блокируем polling, пока Claude думает.
                    t = asyncio.create_task(handle_message(client, sessions, upd))
                    tasks.add(t)
                    t.add_done_callback(tasks.discard)
                marker = data.get("marker", marker)
            except httpx.HTTPError as e:
                log.warning("GET /updates ошибка сети: %s", e)
                await asyncio.sleep(5)


if __name__ == "__main__":
    log.info("Запуск мозга (MAX -> Claude Code). API=%s, workspace=%s", MAX_API_BASE, WORKSPACE)
    try:
        asyncio.run(poll_loop())
    except KeyboardInterrupt:
        log.info("Остановлен.")
