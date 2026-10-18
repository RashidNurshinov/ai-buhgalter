"""Шаг 2: анализ кеша -> кандидаты на продвижение (залежалые + свежий привоз).

Запуск:  python3 candidates.py --cache DIR --today 2026-10-18 [--out ../output]
Результат: kandidaty_<дата>.md и kandidaty_<дата>.json в --out.

Определения (USTAV.md):
  Залежалый  = остаток > 0 И нет продаж 6 мес (с today-183д) И товар не поступал
               за эти же 6 мес (иначе он ещё "не успел" продаться -> это привоз).
  Свежий привоз = остаток > 0 И последняя приёмка (supply) за последние 60 дней.
Цены в API в копейках, в отчёте переводятся в рубли.
"""
import argparse
import collections
import datetime as dt
import json
import os

STALE_DAYS = 183
FRESH_DAYS = 60
TOP_N = 8                 # размер подборки (запас кандидатов)
PER_CAT_CAP = 2           # не более N кандидатов из одной категории
MIN_RETAIL_RUB = {"furniture": 1500, "gambit": 3000}   # мелочь не продвигаем

# Папки аккаунта Gambit, которые не являются бытовой техникой
GAMBIT_NON_TECH = ("МЕБЕЛЬ", "Гипермаркетмебели.рф", "ПОСУДА", "ТОВАРЫ ДЛЯ ПИКНИКА",
                   "ХОЗЯЙСТВЕННЫЕ ТОВАРЫ", "ДЛЯ СОБСТВЕННЫХ НУЖД")

# Мебель: категория по ключевым словам названия (порядок важен)
FURN_CATS = [
    ("Диваны", ("диван", "угловой диван", "кушетк", "банкетк")),
    ("Кровати/матрасы", ("кроват", "матрас", "матрац", "ортопед")),
    ("Кресла/пуфы/стулья", ("кресл", "пуф", "стул", "табурет")),
    ("Столы", ("стол ", "стол,", "столик", "cтол")),
    ("Шкафы/стенки", ("шкаф-купе", "шкаф ", "стенка", "пенал", "витрин")),
    ("Тумбы/комоды", ("тумб", "комод", "консоль")),
    ("Кухни/кухонные модули", ("кухонн", "кухня", "кухн", "мойка", "уголок")),
    ("Прихожие/вешалки", ("прихож", "вешалк", "обувниц")),
    ("Полки/зеркала", ("полк", "зеркал", "стеллаж")),
    ("Комплектующие/фурнитура", ("ручка", "планка", "угол внеш", "угол внутр", "блок питания",
                                 "фасад", "каркас", "корпус", "коробка", "датчик", "профиль",
                                 "заглушка", "петля", "направляющ", "ножк", "крепеж", "фурнитур",
                                 "светильник", "цоколь", "плинтус")),
]
FURN_ACCESSORY = "Комплектующие/фурнитура"


def rub(kop):
    v = (kop or 0) / 100
    return f"{v:,.2f}".replace(",", " ").replace(".00", "")


def esc(s):
    return str(s).replace("|", "/").replace("\n", " ")


def d10(s):
    return s[:10] if s else "—"


def furn_category(name):
    n = " " + name.lower().replace("ё", "е") + " "
    # комплектующие проверяем первыми по узким словам (каркас шкафа != шкаф)
    for cat, kws in [FURN_CATS[-1]] + FURN_CATS[:-1]:
        if any(k in n for k in kws):
            return cat
    return "Прочее"


def furn_supplier(name, agent):
    first = name.split()[0] if name.split() else ""
    if first == "IMP":
        return "Империал (IMP)"
    if first == "AL":
        return "Прочие (AL)"
    return f"без префикса; приёмка от: {agent}" if agent else "без префикса"


def analyse(acc, d, today):
    t_stale = today - dt.timedelta(days=STALE_DAYS)
    t_fresh = today - dt.timedelta(days=FRESH_DAYS)
    P = d["products"]

    last_sale, last_sup, first_sup = {}, {}, {}
    for k in ("demand", "retaildemand"):
        for doc in d[k]:
            for pid, q, _ in doc["items"]:
                if q > 0 and doc["moment"] > last_sale.get(pid, ""):
                    last_sale[pid] = doc["moment"]
    for doc in d["supply"]:
        for pid, q, price in doc["items"]:
            cur = last_sup.get(pid)
            if cur is None or doc["moment"] > cur["moment"]:
                last_sup[pid] = {"moment": doc["moment"], "price": price, "agent": doc.get("agent"),
                                 "doc": doc.get("name")}
            if doc["moment"] < first_sup.get(pid, "9"):
                first_sup[pid] = doc["moment"]
    sold_in_window = {r["id"] for r in d["profit_window"] if r["sellQuantity"] > 0}

    pos = [r for r in d["stock"] if r["stock"] > 0]
    neg = [r for r in d["stock"] if r["stock"] < 0]

    def build(r):
        p = P.get(r["id"], {})
        ls = last_sale.get(r["id"])
        sp = last_sup.get(r["id"])
        path = p.get("pathName") or ""
        if acc == "furniture":
            cat = furn_category(r["name"])
            supplier = furn_supplier(r["name"], sp["agent"] if sp else None)
        else:
            cat = path or (r.get("folder") or "(без категории)")
            supplier = sp["agent"] if sp else "—"
        buy = p.get("buyPrice", 0)
        floor = max(r["cost"], buy, sp["price"] if sp else 0)
        return {
            "id": r["id"], "name": r["name"], "code": r["code"], "article": p.get("article") or "",
            "category": cat, "stock": r["stock"], "cost": r["cost"], "buy_card": buy,
            "last_supply_price": sp["price"] if sp else 0, "retail": r["salePrice"],
            "floor": floor, "last_sale": ls, "last_supply": sp["moment"] if sp else None,
            "first_supply": first_sup.get(r["id"]), "supplier": supplier,
            "sold_in_window": r["id"] in sold_in_window,
            "cost_mismatch": bool(sp and sp["price"] > 0 and r["cost"] > 0
                                  and abs(r["cost"] - sp["price"]) / sp["price"] > 0.3),
        }

    items = [build(r) for r in pos]

    def is_stale(i):
        if i["sold_in_window"]:
            return False
        ls = d10(i["last_sale"]); sp = d10(i["last_supply"])
        return sp < t_stale.isoformat() or sp == "—"

    def is_fresh(i):
        return d10(i["last_supply"]) != "—" and d10(i["last_supply"]) >= t_fresh.isoformat()

    stale = [i for i in items if is_stale(i)]
    fresh = [i for i in items if is_fresh(i)]
    literal_nosale = [i for i in items if not i["sold_in_window"]]
    grey = [i for i in literal_nosale if not is_stale(i)]  # нет продаж, но поступил < 6 мес назад

    def eligible(i):
        if i["retail"] <= 0 or i["retail"] <= i["floor"]:
            return False                      # скидывать нечем / аномалия цены
        if i["retail"] / 100 < MIN_RETAIL_RUB[acc]:
            return False
        if i["stock"] < 1:
            return False
        if acc == "furniture" and i["category"] == FURN_ACCESSORY:
            return False
        if acc == "gambit" and i["category"].split("/")[0] in GAMBIT_NON_TECH:
            return False
        return True

    def pick(lst, key):
        out, cnt = [], collections.Counter()
        for i in sorted([x for x in lst if eligible(x)], key=key, reverse=True):
            if cnt[i["category"]] >= PER_CAT_CAP:
                continue
            cnt[i["category"]] += 1
            out.append(i)
            if len(out) >= TOP_N:
                break
        return out

    # залежалые: чем больше замороженных денег (остаток * себестоимость), тем интереснее
    def key_stale(i):
        return (i["stock"] * max(i["cost"], i["floor"]), i["retail"])
    # привоз: потенциал прибыли (маржа за штуку * до 3 шт.) - для витрины берём "что показать"
    def key_fresh(i):
        return ((i["retail"] - i["floor"]) * min(i["stock"], 3), i["retail"])

    res = {
        "stale_total": len(stale), "fresh_total": len(fresh), "grey_total": len(grey),
        "literal_nosale_total": len(literal_nosale),
        "never_sold_stale": sum(1 for i in stale if not i["last_sale"]),
        "pos_total": len(items), "neg_total": len(neg),
        "stale": pick(stale, key_stale), "fresh": pick(fresh, key_fresh),
        "stale_eligible": sum(1 for i in stale if eligible(i)),
        "fresh_eligible": sum(1 for i in fresh if eligible(i)),
    }
    # "наблюдение": нет продаж, лежит < 6 мес, самые старые приёмки
    grey_sorted = sorted([i for i in grey if i["retail"] > 0], key=lambda i: d10(i["first_supply"]))
    res["watch"] = [i for i in grey_sorted if not is_fresh(i)][:TOP_N]

    # ---- аномалии цен ----
    an = {}
    an["instock_retail_below_cost"] = [i for i in items if 0 < i["retail"] < i["floor"]]
    an["instock_retail_zero"] = [i for i in items if i["retail"] <= 0]
    an["instock_cost_zero"] = [i for i in items if i["floor"] <= 0]
    an["placeholder_150"] = [i for i in items if i["retail"] == 15000]
    cat_below = [p for p in P.values() if p["salePrice"] and p["buyPrice"] and p["salePrice"] < p["buyPrice"]
                 and not p.get("archived")]
    an["catalog_retail_below_buy"] = cat_below
    an["instock_cost_mismatch"] = [i for i in items if i["cost_mismatch"]]
    sold_loss = [r for r in d["profit_window"] if r["sellCostSum"] > 0 and r["sellSum"] < r["sellCostSum"]]
    an["sold_below_cost"] = sorted(sold_loss, key=lambda r: r["sellSum"] - r["sellCostSum"])
    an["negative_stock"] = neg
    res["anomalies"] = an
    res["window"] = {"from": t_stale.isoformat(), "fresh_from": t_fresh.isoformat()}
    res["meta_counts"] = {"products": len(P), "stock_rows": len(d["stock"]),
                          "demand": len(d["demand"]), "retaildemand": len(d["retaildemand"]),
                          "supply": len(d["supply"]), "sold_in_window": len(sold_in_window)}
    return res


# ---------------------------- Markdown ----------------------------
def table(items, show_last_sale=True):
    h = ("| # | Наименование | Код / арт. | Категория | Остаток | Себест., ₽ | Закуп. (карточка), ₽ "
         "| Закуп. посл. приёмки, ₽ | Розница, ₽ | Посл. продажа | Посл. поступление | Поставщик |\n"
         "|---|---|---|---|---:|---:|---:|---:|---:|---|---|---|\n")
    rows = []
    for n, i in enumerate(items, 1):
        art = esc(i["code"] + (f" / {i['article']}" if i["article"] else ""))
        flag = " ⚠цена" if i.get("cost_mismatch") else ""
        stock = f"{i['stock']:g}"
        rows.append(
            f"| {n} | {esc(i['name'][:90])}{flag} | {art} | {esc(i['category'])} | {stock} | "
            f"{rub(i['cost'])} | {rub(i['buy_card']) if i['buy_card'] else '—'} | "
            f"{rub(i['last_supply_price']) if i['last_supply_price'] else '—'} | {rub(i['retail'])} | "
            f"{d10(i['last_sale']) if i['last_sale'] else 'не продавался'} | {d10(i['last_supply'])} | "
            f"{esc(i['supplier'])} |")
    return h + "\n".join(rows) + "\n" if rows else "_нет кандидатов_\n"


def why(i, kind):
    margin = i["retail"] - i["floor"]
    pct = margin / i["floor"] * 100 if i["floor"] else 0
    frozen = i["stock"] * max(i["cost"], i["floor"])
    if kind == "stale":
        s = ("не продавался вообще" if not i["last_sale"] else f"последняя продажа {d10(i['last_sale'])}")
        return (f"{s}; заморожено {rub(frozen)} ₽; запас на скидку до закупа {rub(margin)} ₽/шт ({pct:.0f}%)")
    return (f"поступил {d10(i['last_supply'])}; потенциал {rub(margin)} ₽/шт ({pct:.0f}% к закупу), "
            f"остаток {i['stock']:g}")


def why_list(items, kind):
    return "\n".join(f"{n}. **{i['name'][:70]}** — {why(i, kind)}" for n, i in enumerate(items, 1)) + "\n"


def anomalies_md(acc, a):
    out = []
    t = a["instock_retail_below_cost"]
    out.append(f"- Позиций В НАЛИЧИИ с розницей НИЖЕ закупа/себестоимости: **{len(t)}**")
    if t:
        out.append("\n| Наименование | Код | Остаток | Себест., ₽ | Закуп. карт., ₽ | Закуп. посл. приёмки, ₽ | Розница, ₽ |\n|---|---|---:|---:|---:|---:|---:|")
        for i in sorted(t, key=lambda i: i["retail"] - i["floor"])[:25]:
            out.append(f"| {esc(i['name'][:70])} | {i['code']} | {i['stock']:g} | {rub(i['cost'])} | "
                       f"{rub(i['buy_card']) if i['buy_card'] else '—'} | {rub(i['last_supply_price'])} | {rub(i['retail'])} |")
        if len(t) > 25:
            out.append(f"\n_… и ещё {len(t) - 25} (полный список в JSON)_")
    ph = a["placeholder_150"]
    out.append(f"\n- Позиций в наличии с розницей ровно **150 ₽** (похоже на заглушку, а не цену): **{len(ph)}**")
    out.append(f"- Позиций в наличии с розницей 0: **{len(a['instock_retail_zero'])}**; с нулевой себестоимостью/закупом: **{len(a['instock_cost_zero'])}**")
    out.append(f"- Позиций в наличии, где себестоимость отличается от закупа последней приёмки более чем на 30% "
               f"(в таблицах пометка ⚠цена; перед скидкой @aliya сверить): **{len(a['instock_cost_mismatch'])}**")
    c = a["catalog_retail_below_buy"]
    out.append(f"- В КАРТОЧКАХ товаров (весь каталог) розница < закупочной цены карточки: **{len(c)}**")
    for p in c[:10]:
        out.append(f"  - {p['name'][:80]} (код {p['code']}): розница {rub(p['salePrice'])} ₽ < закуп. {rub(p['buyPrice'])} ₽")
    s = a["sold_below_cost"]
    loss = sum(r["sellCostSum"] - r["sellSum"] for r in s)
    out.append(f"- ПРОДАНО за 6 мес ниже себестоимости: **{len(s)}** позиций, суммарный убыток **{rub(loss)} ₽**")
    if s:
        out.append("\n| Наименование | Кол-во | Продано на, ₽ | Себест. продажи, ₽ | Убыток, ₽ |\n|---|---:|---:|---:|---:|")
        for r in s[:12]:
            out.append(f"| {esc(r['name'][:70])} | {r['sellQuantity']:g} | {rub(r['sellSum'])} | {rub(r['sellCostSum'])} | {rub(r['sellCostSum'] - r['sellSum'])} |")
        if len(s) > 12:
            out.append(f"\n_… и ещё {len(s) - 12} (полный список в JSON)_")
    return "\n".join(out) + "\n"


def render(today, R):
    L = []
    w = R["furniture"]["window"]
    L.append(f"# Подборка кандидатов на продвижение — {today}\n")
    L.append(f"Автор: @damir. Источник: МойСклад API (два аккаунта), данные на {today}. "
             f"Окно «нет продаж»: {w['from']} … {today}; «свежий привоз»: приёмки с {w['fresh_from']}.\n")
    L.append("> Цены в рекламе НЕ показываем — рубли ниже только для @boss и @aliya. "
             "Скидка не ниже закупа: колонки закупа даны все три (карточка / себестоимость / последняя приёмка), "
             "ориентир для @aliya — самое большое из них.\n")
    L.append("## Сводка\n")
    L.append("| Раздел | Всего подходит под определение | Из них годны в подборку* | В подборке |\n|---|---:|---:|---:|")
    for acc, title in (("furniture", "Мебель"), ("gambit", "Техника (Gambit)")):
        r = R[acc]
        L.append(f"| {title} — залежалые | {r['stale_total']} | {r['stale_eligible']} | {len(r['stale'])} |")
        L.append(f"| {title} — свежий привоз | {r['fresh_total']} | {r['fresh_eligible']} | {len(r['fresh'])} |")
    L.append("\n\\* годны = розница выше закупа, остаток ≥ 1, розница не мелочь "
             f"(мебель ≥ {MIN_RETAIL_RUB['furniture']} ₽, техника ≥ {MIN_RETAIL_RUB['gambit']} ₽), "
             "не комплектующие/не посуда/не мебель в аккаунте Gambit. "
             f"В подборке — не более {PER_CAT_CAP} из одной категории.\n")
    for acc in ("furniture", "gambit"):
        r = R[acc]
        L.append(f"- {'Мебель' if acc == 'furniture' else 'Gambit'}: позиций с остатком > 0: {r['pos_total']}, "
                 f"с отрицательным остатком: {r['neg_total']}; "
                 f"«нет продаж за 6 мес» буквально: {r['literal_nosale_total']}, из них «поступили < 6 мес назад» "
                 f"(серая зона, не залежалые): {r['grey_total']}.")
    L.append("")

    sections = [("furniture", "stale", "Мебель — залежалые"), ("furniture", "fresh", "Мебель — свежий привоз"),
                ("gambit", "stale", "Техника — залежалые"), ("gambit", "fresh", "Техника — свежий привоз")]
    for acc, kind, title in sections:
        r = R[acc]
        L.append(f"## {title}\n")
        if acc == "gambit":
            L.append("⚠ Остатки Gambit не выверены — перед запуском проверить наличие физически; "
                     "поэтому дан запас кандидатов.\n")
        items = r[kind]
        if kind == "stale" and acc == "furniture" and r["stale_total"] == 0:
            L.append("**Залежалой мебели по определению (нет продаж > 6 мес + остаток) НЕ НАЙДЕНО.** "
                     "Почти весь остаток мебели оприходован 2026-10-17 (две приёмки: «по счёту № УРЛ_ОП00447 от 13.10» "
                     "и «по сводной ведомости ИП Максимов»), остальное — июнь/сентябрь 2026. "
                     "Аккаунт мебели начал работать в 2026 году; всё, что приходило раньше, продано.\n")
            if r["watch"]:
                L.append("Для справки — самые «старые» непроданные позиции (на складе МЕНЬШЕ 6 мес, под определение "
                         "не подходят; решение за @boss):\n")
                L.append(table(r["watch"]))
            continue
        L.append(table(items))
        if items:
            L.append("**Почему эти:**\n")
            L.append(why_list(items, kind))
    L.append("## Аномалии цен\n")
    L.append("### Мебель\n")
    L.append(anomalies_md("furniture", R["furniture"]["anomalies"]))
    L.append("### Техника (Gambit)\n")
    L.append(anomalies_md("gambit", R["gambit"]["anomalies"]))
    L.append("## Проблемы с данными\n")
    for acc, t in (("furniture", "Мебель"), ("gambit", "Gambit")):
        a = R[acc]["anomalies"]; neg = a["negative_stock"]
        L.append(f"- {t}: **{len(neg)}** позиций с ОТРИЦАТЕЛЬНЫМ остатком (суммарно {sum(x['stock'] for x in neg):g} шт) — "
                 f"продано/списано больше, чем оприходовано; у таких себестоимость в отчёте 0, их в подборку не берём.")
    L.append("- Папки (категории) в мебельном аккаунте не заданы — категория выведена по ключевым словам названия.")
    L.append("- Отчёты /report/stock/all отдают «price» = себестоимость (средняя), «salePrice» = розница (тип «Цена продажи»). "
             "Закупочная цена из карточки заполнена не у всех товаров мебели (см. прочерки).")
    return "\n".join(L) + "\n"


def to_jsonable(R):
    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items()}
        if isinstance(o, list):
            return [strip(x) for x in o]
        return o
    return strip(R)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=os.environ.get("MKT_CACHE", "/tmp/mkt_cache"))
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "output"))
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.today)
    R = {}
    for acc in ("furniture", "gambit"):
        with open(os.path.join(a.cache, f"{acc}.json"), encoding="utf-8") as f:
            R[acc] = analyse(acc, json.load(f), today)
    os.makedirs(a.out, exist_ok=True)
    md = os.path.join(a.out, f"kandidaty_{today}.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write(render(today, R))
    with open(os.path.join(a.out, f"kandidaty_{today}.json"), "w", encoding="utf-8") as f:
        json.dump(to_jsonable(R), f, ensure_ascii=False, indent=1)
    print("OK", md)
