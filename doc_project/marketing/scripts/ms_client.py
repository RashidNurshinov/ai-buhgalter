"""Тонкий клиент МойСклад API (remap 1.2) для отдела маркетинга.

Токены читаются ТОЛЬКО из переменных окружения и нигде не печатаются.
"""
import os
import sys
import time

import requests

BASE = "https://api.moysklad.ru/api/remap/1.2"

ACCOUNTS = {
    "furniture": {"env": "MOYSKLAD_FURNITURE_API_TOKEN", "title": "Мебель"},
    "gambit": {"env": "MOYSKLAD_GAMBIT_API_TOKEN", "title": "Техника (Gambit)"},
}


class MSClient:
    def __init__(self, account: str):
        env = ACCOUNTS[account]["env"]
        token = os.environ.get(env)
        if not token:
            sys.exit(f"Не задана переменная окружения {env}")
        self.account = account
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept-Encoding": "gzip",
        })
        self.requests_made = 0

    def get(self, path_or_url: str, params: dict | None = None) -> dict:
        url = path_or_url if path_or_url.startswith("http") else f"{BASE}{path_or_url}"
        for attempt in range(8):
            r = self.s.get(url, params=params, timeout=120)
            self.requests_made += 1
            if r.status_code == 429:  # лимит запросов
                wait = int(r.headers.get("X-Lognex-Retry-TimeInterval", "3000")) / 1000
                time.sleep(max(wait, 1))
                continue
            if r.status_code >= 500:
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code != 200:
                # тело ошибки МойСклада не содержит токена, но печатаем только суть
                raise RuntimeError(f"HTTP {r.status_code} {url.split('?')[0]}: {r.text[:300]}")
            time.sleep(0.08)
            return r.json()
        raise RuntimeError(f"Не удалось получить {url.split('?')[0]} после повторов")

    def paged(self, path: str, params: dict | None = None, limit: int = 1000):
        """Постранично отдаёт rows. limit<=1000 (для expand — <=100)."""
        params = dict(params or {})
        params["limit"] = limit
        offset = 0
        while True:
            params["offset"] = offset
            d = self.get(path, params)
            rows = d.get("rows", [])
            yield from rows
            size = d.get("meta", {}).get("size", 0)
            offset += limit
            if offset >= size or not rows:
                break
