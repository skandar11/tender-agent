#!/usr/bin/env python3
"""Единая платформа закупок zakup.gov.kz и платформа МЭКС — новые тендеры без ключа.

Единая платформа отдаёт лоты сразу четырёх площадок: госзакуп, Самрук-Қазына, Mitwork, ФСМС.
Открытый API, токен не нужен (проверено 2026-11-11). МЭКС (нацпроект модернизации
энергетического и коммунального секторов) — свой открытый API на meks.zakup.sk.kz.

Примеры (из папки engine/):
  python scripts/portal.py lots --subject works,services --min 20000000 --method contest
  python scripts/portal.py lots --q водопровод --region "Карагандинская область" --system samruk
  python scripts/portal.py lots --new monitor.json          # только то, чего ещё не показывали
  python scripts/portal.py meks --subject works --min 20000000
  python scripts/portal.py dicts statuses|methods

Ключ госзакупа (ows.py) здесь не нужен: он нужен для договоров, участников и РНП.
Памятка — tenders/tenders-vault/tools/zakup-gov-kz.md.
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HOST = "https://zakup.gov.kz/api/core/api"
MEKS = "https://meks.zakup.sk.kz/api/pub/application-announcement-311/list"
UA = "Mozilla/5.0 (tender agent)"

SYSTEMS = {"goszakup": 1, "mitwork": 2, "samruk": 3, "fsms": 4}
SUBJECTS = {"goods": 1, "works": 2, "services": 3}
SUBJECT_RU = {"goods": "товары", "works": "работы", "services": "услуги"}
# Статусы «приём заявок открыт» по словарю платформы (dicts/lot-statuses, 2026-11-11):
# 6 Опубликован · 7 Опубликован (приём заявок) · 8 Опубликован (дополнение заявок) ·
# 9 Опубликован (приём ценовых предложений) · 63 Опубликовано. Торги (Самрук)
OPEN_STATUSES = [6, 7, 8, 9, 63]
MEKS_OPEN = {"PUBLISHED", "ACCEPTING_APPLICATIONS", "APPLICATION_PERIOD_EXTENDED", "ACCEPTING_COMMENTS_REQUESTS"}

_last = 0.0


def get(url):
    """GET с паузой между запросами — площадка общая, не долбим."""
    global _last
    wait = 0.7 - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                _last = time.time()
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # сеть или пустой ответ — ещё раз
            if attempt == 2:
                sys.exit(f"площадка не ответила: {url}\n{e}")
            time.sleep(2 + attempt * 3)


def dict_list(name):
    return get(f"{HOST}/dicts/{name}/")


def contest_methods():
    """Способы «конкурс / тендер» по словарю платформы (кроме этапов рамочных и спецпорядков питания)."""
    out = []
    for m in dict_list("purchase-methods"):
        n = m["name"].lower()
        if ("конкурс" in n or "тендер" in n) and "питани" not in n and "этап" not in n:
            out.append(m["id"])
    return out


def region_id(name):
    r = get(f"{HOST}/dicts/katos/?" + urllib.parse.urlencode({"q": name}))
    res = r.get("result") or []
    exact = [x for x in res if x["name_ru"].lower() == name.lower()]
    if not (exact or res):
        sys.exit(f"место «{name}» не найдено в справочнике КАТО платформы")
    return (exact or res)[0]["id"]


def money(x):
    return f"{x:,.0f}".replace(",", " ") if isinstance(x, (int, float)) else "—"


def load_seen(path):
    p = Path(path)
    return set(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else set()


def save_seen(path, seen):
    Path(path).write_text(json.dumps(sorted(seen), ensure_ascii=False), encoding="utf-8")


# Самрук и Mitwork размечены на платформе не полностью (проверено 2026-11-15): у лотов Самрука пустое место
# поставки, у Mitwork — пустой вид предмета. Серверный фильтр по ним выбрасывает площадку целиком, поэтому
# для них место и вид отбираются по тексту лота на нашей стороне.
SERVER_SUBJECT = {1, 3, 4}   # госзакуп, Самрук, ФСМС — вид предмета размечен
SERVER_REGION = {1, 4}       # госзакуп, ФСМС — место поставки размечено
TEXT_PAGES = 15              # страниц по 100 на площадку при отборе по тексту


def lot_text(x):
    parts = [x.get("name_ru"), x.get("description_ru"), x.get("announcement_name_ru")]
    parts += [e.get("name_ru") for e in x.get("enstrus") or []]
    parts += [c.get("name_ru") for c in x.get("customers") or []]
    return " ".join(p for p in parts if p).lower()


def subject_by_text(x, subjects):
    """Mitwork: вид предмета по названию — «Услуги …», «Работы …»; остальное считаем товаром."""
    t = (x.get("name_ru") or x.get("description_ru") or "").strip().lower()
    kind = "services" if t.startswith("услуг") else "works" if t.startswith("работ") else "goods"
    return kind in subjects


def region_words(name):
    w = name.lower().replace("область", "").replace("обл.", "").strip()
    stem = w[:6]
    extra = {"караган": ["қарағанд", "темиртау", "балхаш", "шахтинск", "сарань", "абай", "приозерск"],
             "улытау": ["ұлытау", "жезказган", "жезқазған", "сатпаев", "сәтбаев", "каражал"]}
    out = [stem]
    for k, v in extra.items():
        if stem.startswith(k[:6]):
            out += v
    return out


def cmd_lots(a):
    systems = [SYSTEMS[s] for s in a.system.split(",") if s != "all"] or list(SYSTEMS.values())
    subjects = [s for s in a.subject.split(",") if s != "all"]
    base = []
    if a.q:
        base.append(("q", a.q))
    if a.status == "open":
        base += [("status_id", str(i)) for i in OPEN_STATUSES]
    if a.min:
        base.append(("total_price__gte", str(int(a.min))))
    if a.max:
        base.append(("total_price__lte", str(int(a.max))))
    if a.method == "contest":
        base += [("purchase_method_id", str(i)) for i in contest_methods()]
    reg_id = region_id(a.region) if a.region else None
    words = region_words(a.region) if a.region else []

    rows, total, notes = [], 0, []
    for sid in systems:
        params = base + [("system_id", str(sid))]
        by_text = False
        if subjects and sid in SERVER_SUBJECT:
            params += [("purchase_subject_id", str(SUBJECTS[s])) for s in subjects]
        elif subjects:
            by_text = True
        if reg_id and sid in SERVER_REGION:
            params.append(("delivery_address_id__in", str(reg_id)))
        elif reg_id:
            by_text = True
        want = a.limit if not by_text else TEXT_PAGES * 100
        got, offset = [], 0
        while len(got) < want:
            r = get(f"{HOST}/public/lots/?" + urllib.parse.urlencode(params + [("limit", "100"), ("offset", str(offset))]))
            batch = r.get("results") or []
            if offset == 0:
                cnt = r.get("count", 0)
            got += batch
            offset += len(batch)
            if not batch or offset >= cnt:
                break
        if by_text:
            if subjects and sid not in SERVER_SUBJECT:
                got = [x for x in got if subject_by_text(x, subjects)]
            if reg_id and sid not in SERVER_REGION:
                got = [x for x in got if any(w in lot_text(x) for w in words)]
            name = {v: k for k, v in SYSTEMS.items()}[sid]
            notes.append(f"{name}: отбор по тексту лота (вид или место на платформе не размечены), "
                         f"просмотрено {min(offset, cnt)} из {cnt}")
            cnt = len(got)
        total += cnt
        rows += got
    rows.sort(key=lambda x: x.get("offer_end_date") or "")
    rows = rows[: a.limit]
    for n in notes:
        print("· " + n)

    seen = load_seen(a.new) if a.new else set()
    fresh = [x for x in rows if str(x["id"]) not in seen]
    if a.new:
        save_seen(a.new, seen | {str(x["id"]) for x in rows})

    show = fresh if a.new else rows
    if a.json:
        print(json.dumps(show, ensure_ascii=False, indent=1))
        return
    print(f"найдено по фильтру: {total} · показано: {len(show)}" + (f" (новых из {len(rows)})" if a.new else ""))
    print(f"{'площадка':9} {'сумма ₸':>15}  {'приём до':10}  {'способ':24}  лот · заказчик")
    for x in show:
        sysn = (x.get("system") or {}).get("name", "")
        cust = (x.get("customers") or [{}])[0]
        end = (x.get("offer_end_date") or x.get("offer_start_date") or "")[:10]
        print(f"{sysn:9} {money(x.get('total_price')):>15}  {end:10}  {(x.get('purchase_method_name') or '')[:24]:24}  "
              f"{x.get('announcement_number')} · {(x.get('name_ru') or x.get('announcement_name_ru') or '')[:60]} · {(cust.get('name_ru') or x.get('organization_name') or '')[:40]} ({cust.get('bin') or ''})")


def cmd_meks(a):
    rows, page = [], 0
    while True:
        r = get(f"{MEKS}?page={page}&size=50")
        rows += r.get("content") or []
        if r.get("last") or not r.get("content") or page > 40:
            break
        page += 1
    out = []
    for x in rows:
        d = x.get("data") or {}
        if a.status == "open" and x.get("status") not in MEKS_OPEN:
            continue
        if a.subject != "all" and d.get("procurementTypeCode") not in a.subject.split(","):
            continue
        s = d.get("totalSumWithoutNDS") or d.get("marginCost") or 0
        if a.min and s < a.min:
            continue
        if a.q and a.q.lower() not in (x.get("concursName") or "").lower():
            continue
        out.append(x)
    seen = load_seen(a.new) if a.new else set()
    fresh = [x for x in out if x["id"] not in seen]
    if a.new:
        save_seen(a.new, seen | {x["id"] for x in out})
    show = fresh if a.new else out
    if a.json:
        print(json.dumps(show, ensure_ascii=False, indent=1))
        return
    print(f"МЭКС: всего {len(rows)} · по фильтру {len(out)} · показано {len(show)}")
    for x in show:
        d = x.get("data") or {}
        print(f"{money(d.get('totalSumWithoutNDS')):>15} без НДС  до {(d.get('endDate') or '')[:10]}  "
              f"{SUBJECT_RU.get(d.get('procurementTypeCode'), d.get('procurementTypeCode'))}  {x.get('concursNum')} · "
              f"{(x.get('concursName') or '')[:70]} · {(x.get('customerName') or '')[:40]} ({x.get('customerBin')}) · "
              f"{x.get('placeProjectImplementationName', '')}")


def cmd_dicts(a):
    name = {"statuses": "lot-statuses", "methods": "purchase-methods"}[a.which]
    for x in dict_list(name):
        print(x["id"], x["name"])


def main():
    p = argparse.ArgumentParser(description="Единая платформа закупок и МЭКС — без ключа")
    sp = p.add_subparsers(dest="cmd", required=True)

    l = sp.add_parser("lots", help="лоты единой платформы (госзакуп, Самрук, Mitwork, ФСМС)")
    l.add_argument("--q", help="слово или номер")
    l.add_argument("--system", default="all", help="goszakup,samruk,mitwork,fsms или all")
    l.add_argument("--subject", default="all", help="works,services,goods или all")
    l.add_argument("--status", default="open", choices=["open", "any"], help="open — идёт приём заявок")
    l.add_argument("--min", type=float, help="сумма от, ₸")
    l.add_argument("--max", type=float, help="сумма до, ₸")
    l.add_argument("--method", choices=["contest", "any"], default="any", help="contest — конкурсы и тендеры")
    l.add_argument("--region", help="место поставки по справочнику, напр. «Карагандинская область»")
    l.add_argument("--limit", type=int, default=50)
    l.add_argument("--new", metavar="ФАЙЛ", help="показать только новые; файл помнит показанное")
    l.add_argument("--json", action="store_true")
    l.set_defaults(fn=cmd_lots)

    m = sp.add_parser("meks", help="конкурсы платформы МЭКС (meks.zakup.sk.kz)")
    m.add_argument("--q")
    m.add_argument("--subject", default="all", help="works,services или all")
    m.add_argument("--status", default="open", choices=["open", "any"])
    m.add_argument("--min", type=float)
    m.add_argument("--new", metavar="ФАЙЛ")
    m.add_argument("--json", action="store_true")
    m.set_defaults(fn=cmd_meks)

    d = sp.add_parser("dicts", help="словари платформы")
    d.add_argument("which", choices=["statuses", "methods"])
    d.set_defaults(fn=cmd_dicts)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
