"""Шаг 1: выгрузка сырых данных из МойСклад в кеш (JSON).

Запуск:  python3 collect.py [--cache DIR] [--today 2026-10-18]
Выгружает для каждого аккаунта: товары, остатки, продажи (demand + retaildemand,
вся история - для даты последней продажи), приёмки (supply), отчёт прибыли по
товарам за окно 6 мес. Результат: DIR/<account>.json
"""
import argparse
import datetime as dt
import json
import os
import re

from ms_client import ACCOUNTS, MSClient


def pid(meta_href: str) -> str:
    return meta_href.split("/product/")[-1].split("?")[0] if "/product/" in meta_href else \
        meta_href.rstrip("/").split("/")[-1].split("?")[0]


def fetch_docs(c: MSClient, entity: str):
    """Проведённые документы с позициями: [(moment, [(product_id, qty, price)])]."""
    out = []
    for doc in c.paged(f"/entity/{entity}", {"expand": "positions,agent", "order": "moment,desc"}, limit=100):
        if not doc.get("applicable", True):
            continue
        pos = doc.get("positions", {})
        rows = pos.get("rows", [])
        size = pos.get("meta", {}).get("size", len(rows))
        if size > len(rows):  # позиции обрезаны expand-ом - докачиваем
            rows = list(c.paged(f"/entity/{entity}/{doc['id']}/positions"))
        items = []
        for p in rows:
            a = p.get("assortment", {}).get("meta", {})
            if a.get("type") not in ("product", "variant"):
                continue
            items.append([pid(a["href"]), p.get("quantity", 0), p.get("price", 0)])
        out.append({"moment": doc["moment"], "created": doc.get("created"), "name": doc.get("name"),
                    "agent": (doc.get("agent") or {}).get("name"),
                    "description": (doc.get("description") or "")[:120], "items": items})
    return out


def collect(account: str, today: dt.date, cache: str):
    c = MSClient(account)
    start = today - dt.timedelta(days=183)  # ~6 месяцев (2026-04-18 для 2026-10-18)
    data = {"account": account, "today": today.isoformat(), "window_from": start.isoformat()}

    print(f"[{account}] товары...")
    products = {}
    for p in c.paged("/entity/product"):
        products[p["id"]] = {
            "id": p["id"], "name": p.get("name"), "code": p.get("code"),
            "article": p.get("article"), "pathName": p.get("pathName", ""),
            "archived": p.get("archived", False),
            "buyPrice": (p.get("buyPrice") or {}).get("value", 0),
            "salePrice": (p.get("salePrices") or [{}])[0].get("value", 0),
            "minPrice": (p.get("minPrice") or {}).get("value", 0),
            "updated": p.get("updated"),
        }
    data["products"] = products

    print(f"[{account}] остатки...")
    stock = []
    for r in c.paged("/report/stock/all"):
        stock.append({
            "id": pid(r["meta"]["href"]), "name": r.get("name"), "code": r.get("code"),
            "stock": r.get("stock", 0), "reserve": r.get("reserve", 0),
            "inTransit": r.get("inTransit", 0),
            "cost": r.get("price", 0), "salePrice": r.get("salePrice", 0),
            "folder": (r.get("folder") or {}).get("name"), "stockDays": r.get("stockDays"),
        })
    data["stock"] = stock

    print(f"[{account}] отчёт прибыли за окно {start}..{today}...")
    prof = []
    for r in c.paged("/report/profit/byproduct", {
            "momentFrom": f"{start} 00:00:00", "momentTo": f"{today} 23:59:59"}):
        a = r["assortment"]
        prof.append({"id": pid(a["meta"]["href"]), "name": a.get("name"),
                     "sellQuantity": r.get("sellQuantity", 0),
                     "returnQuantity": r.get("returnQuantity", 0),
                     "sellPrice": r.get("sellPrice", 0), "sellCost": r.get("sellCost", 0),
                     "sellSum": r.get("sellSum", 0), "sellCostSum": r.get("sellCostSum", 0),
                     "profit": r.get("profit", 0)})
    data["profit_window"] = prof

    for ent in ("demand", "retaildemand", "supply"):
        print(f"[{account}] {ent} (с позициями)...")
        data[ent] = fetch_docs(c, ent)

    data["requests_made"] = c.requests_made
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, f"{account}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"[{account}] готово: товаров {len(products)}, строк остатка {len(stock)}, "
          f"demand {len(data['demand'])}, retaildemand {len(data['retaildemand'])}, "
          f"supply {len(data['supply'])}, запросов {c.requests_made}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=os.environ.get("MKT_CACHE", "/tmp/mkt_cache"))
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--account", choices=list(ACCOUNTS) + ["all"], default="all")
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.today)
    for acc in (ACCOUNTS if a.account == "all" else [a.account]):
        collect(acc, today, a.cache)
