#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lot.py — собрать лот целиком в одну папку: карточка, все документы, текст, история заказчика.

Первый шаг операции «глубокий анализ лота» (tenders/tenders-vault/operations/glubokiy-analiz-lota.md).
Владельцу ничего нажимать не надо: файлы скачивает скрипт, сразу в папку лота.

  lot.py get <номер объявления | номер лота | ссылка> [--system goszakup|samruk|mitwork|meks]
             [--uuid UUID ...] [--year 2026] [--pages 10] [--protocols 5]

Куда кладёт — tenders/lots/<год>/<площадка>-<номер объявления>/:
  lot.json        — карточка лота и объявления, как отдала площадка
  docs/           — все файлы объявления и лотов (вне git: тяжёлые); docs/_text/ — их текст
  history.csv     — договоры этого заказчика по похожему предмету (единая платформа, без ключа)
  protocols/      — «Протоколы об итогах» прошлых конкурсов заказчика (госзакуп, HTML): участники, скидки, цены
  сводка.md       — снятые факты одной страницей; выводы пишет агент рядом, в анализ.md

Откуда что (проверено 2026-11-15):
  госзакуп  — лот и файлы по ключу госзакупа (ows.py); протоколы итогов — HTML в файлах объявления
  Mitwork   — страница объявления eep.mitwork.kz/ru/publics/buy/<id>: таблица файлов, качаются без входа
  МЭКС      — открытый JSON meks.zakup.sk.kz: у конкурса списки вложений, файл — /api/attachments/<id>/download
  Самрук    — карточка и договоры с единой платформы; список файлов на zakup.sk.kz закрыт защитой от ботов
              (ответ 418), её не обходим. Файлы: агент открывает объявление в Chrome и берёт UUID файлов из
              сетевых запросов (eprocfilestorage/open-api/files/download/<UUID>), передаёт их сюда --uuid —
              скачивает скрипт.
  договоры заказчика — единая платформа zakup.gov.kz/api/core/api/public/contracts/ (все площадки).

  lot.py selftest — разбор номеров, слов и таблицы Mitwork на встроенных примерах, без сети.
"""
import argparse
import csv
import html
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
BASE = HERE.parent.parent
UNI = "https://zakup.gov.kz/api/core/api/public"
MEKS = "https://meks.zakup.sk.kz/api"
MITWORK = "https://eep.mitwork.kz/ru"
SAMRUK_FILE = "https://zakup.sk.kz/eprocfilestorage/open-api/files/download/"
UA = "Mozilla/5.0 (tender agent; lot.py)"
SYSTEMS = {1: "goszakup", 2: "mitwork", 3: "samruk", 4: "fsms"}
PAUSE = 0.7
_last = 0.0
LAST_ERROR = ""


# ---------- сеть ----------

def _wait():
    global _last
    w = PAUSE - (time.time() - _last)
    if w > 0:
        time.sleep(w)
    _last = time.time()


def get_json(url, tries=3):
    for attempt in range(tries):
        _wait()
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404, 418):
                return None
            err = e
        except Exception as e:  # сеть, 502 у МЭКС — ещё раз
            err = e
        time.sleep(2 + attempt * 3)
    print(f"  площадка не ответила: {url} — {err}", file=sys.stderr)
    return None


def get_text(url):
    _wait()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def safe_name(name):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name).strip(" ._")
    return name[:150] or "file"


def download(url, folder, name=None):
    """Файл в папку. Имя — заданное или из Content-Disposition. Уже скачанное не трогаем."""
    folder.mkdir(parents=True, exist_ok=True)
    if name and (folder / safe_name(name)).exists() and (folder / safe_name(name)).stat().st_size:
        return folder / safe_name(name)
    _wait()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
            cd = r.headers.get("Content-Disposition") or ""
    except Exception as e:
        global LAST_ERROR
        LAST_ERROR = "закрыт без входа (401)" if "401" in str(e) or "403" in str(e) else str(e)
        print(f"  - не скачалось: {name or url} — {e}", file=sys.stderr)
        return None
    if not name:
        m = re.search(r"filename\*=UTF-8''([^;]+)", cd) or re.search(r'filename="?([^";]+)"?', cd)
        name = urllib.parse.unquote(m.group(1)) if m else url.rstrip("/").split("/")[-1]
        if "=?" in name:  # Самрук отдаёт имя в MIME-кодировке: =?UTF-8?Q?...?=
            from email.header import decode_header, make_header
            try:
                name = str(make_header(decode_header(name)))
            except Exception:
                pass
    dest = folder / safe_name(name)
    if dest.exists() and dest.stat().st_size and dest.read_bytes() != data:
        dest = dest.with_name(f"{dest.stem}_{len(list(folder.iterdir()))}{dest.suffix}")
    dest.write_bytes(data)
    return dest


# ---------- что за лот ----------

def parse_ref(ref):
    """Ссылка или номер → (площадка | None, номер). Площадку по номеру без ссылки угадать нельзя —
    тогда ищем по единой платформе."""
    ref = ref.strip()
    m = re.search(r"goszakup\.gov\.kz/\w+/announce/index/(\d+)", ref)
    if m:
        return "goszakup", m.group(1)
    m = re.search(r"mitwork\.kz/\w+/publics/buy/(\d+)", ref)
    if m:
        return "mitwork", m.group(1)
    m = re.search(r"zakup\.sk\.kz/.*?item/(\d+)", ref)
    if m:
        return "samruk", m.group(1)
    m = re.search(r"(\d{8}[A-ZА-Я]{2,4}-\d+)", ref)
    if m and ("meks" in ref or ref == m.group(1)):
        return "meks", m.group(1)
    return None, ref


def find_unified(number, system=None):
    """Лоты единой платформы по номеру объявления или лота."""
    q = urllib.parse.urlencode({"q": number, "limit": 100})
    d = get_json(f"{UNI}/lots/?{q}") or {}
    out, seen = [], set()
    for r in d.get("results") or []:
        if r["id"] in seen:
            continue
        sysname = SYSTEMS.get((r.get("system") or {}).get("id"))
        if system and sysname != system:
            continue
        if number not in (r.get("announcement_number"), r.get("lot_number"), str(r.get("announcement_external_id"))):
            continue
        seen.add(r["id"])
        out.append(r)
    if out:  # по номеру лота — все лоты того же объявления
        anno = out[0]["announcement_number"]
        if anno != number:
            return find_unified(anno, SYSTEMS.get(out[0]["system"]["id"]))
    return out


def meks_find(number):
    page = 0
    while True:
        d = get_json(f"{MEKS}/pub/application-announcement-311/list?page={page}&size=100")
        if not d:
            return None
        rows = d.get("content") if isinstance(d, dict) else d
        for r in rows or []:
            if number in (r.get("concursNum"), r.get("projectNum"), r.get("id")):
                return r
        if not rows or (isinstance(d, dict) and d.get("last")) or page > 30:
            return None
        page += 1


def meks_attachments(o, path=""):
    """Все вложения конкурса МЭКС: любые списки с id и filename, где бы ни лежали."""
    if isinstance(o, dict):
        if o.get("id") and o.get("filename"):
            yield path, o
        for k, v in o.items():
            yield from meks_attachments(v, f"{path}.{k}" if path else k)
    elif isinstance(o, list):
        for v in o:
            yield from meks_attachments(v, path)


def mitwork_files(page):
    """Таблица файлов на странице объявления Mitwork → [(раздел, имя файла, ссылка)]."""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        link = re.search(r'href="(https?://eep\.mitwork\.kz/\w+/files/download/[0-9a-f]+/\?buyId=\d+)"', row)
        if not link:
            continue
        cells = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        cells = [c for c in cells if c]
        section = cells[0] if cells else ""
        name = cells[1] if len(cells) > 1 else ""
        out.append((section, name, html.unescape(link.group(1))))
    return out


SKIP_SECTIONS = ("ключ",)  # Mitwork выкладывает ключи шифрования заявок — для анализа не нужны


# ---------- слова предмета ----------

STOP = {"работы", "работ", "услуги", "услуг", "товары", "по", "для", "и", "в", "на", "с", "из", "к", "от",
        "других", "прочих", "включенные", "включённые", "другие", "группировки", "не", "под", "ключ",
        "года", "год", "объекта", "объектов", "области", "района", "города", "выполнение", "оказание",
        "приобретение", "закуп", "закупка", "повторно", "лот", "лоты"}


def stems(text):
    words = re.findall(r"[а-яёәғқңөұүһіa-z]{4,}", (text or "").lower())
    out = []
    for w in words:
        if w in STOP or w.isdigit():
            continue
        s = w[:7]  # «автомаш» ≠ «автомат»: шести букв мало
        if s not in out:
            out.append(s)
    return out[:8]


def similar(name, keys):
    if not keys:
        return False
    have = set(stems(name))
    hit = sum(1 for k in keys if k in have)
    return hit >= min(max(2, (len(keys) + 1) // 2), len(keys))


# ---------- шаги ----------

def lot_folder(system, number, year):
    d = BASE / "tenders" / "lots" / str(year) / f"{system}-{safe_name(number)}"
    (d / "docs").mkdir(parents=True, exist_ok=True)
    return d


def docs_goszakup(anno_id, folder):
    sys.path.insert(0, str(HERE))
    import ows
    got = []
    tbs, _ = ows.gql_all("TrdBuy", ows.Q_TB_FILES, {"filter": {"id": [int(anno_id)]}}, limit=1)
    lots, _ = ows.gql_all("Lots", ows.Q_LOT, {"filter": {"trdBuyId": [int(anno_id)]}}, limit=50)
    files = []
    for tb in tbs:
        files += tb.get("Files") or []
    for l in lots:
        files += l.get("Files") or []
    seen = set()
    for f in files:
        name = Path(f.get("originalName") or Path(f.get("filePath") or "").name).name
        if not f.get("filePath") or name in seen:
            continue
        seen.add(name)
        p = download(f["filePath"], folder, name)
        got.append((f.get("nameRu") or "", p))
    return got, {"TrdBuy": tbs, "Lots": lots}


GZ_SITE = "https://old.goszakup.gov.kz/ru/announce"


def goszakup_groups(page):
    """Вкладка «Документы» объявления → [(название группы, номер группы)]."""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        m = re.search(r"actionModalShowFiles\((\d+),\s*(\d+)\)", row)
        if m:
            cells = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            out.append(((cells[0] if cells else "")[:120], m.group(2)))
    return out


def goszakup_links(page):
    return [(m.group(1), " ".join(html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).split()))
            for m in re.finditer(r'<a[^>]+href="([^"]*download_file[^"]*)"[^>]*>(.*?)</a>', page, re.S)]


def docs_goszakup_site(anno_id, folder):
    """Документы объявления с публичного сайта портала — ключ не нужен (проверено 2026-11-15)."""
    got = []
    for title, group in goszakup_groups(get_text(f"{GZ_SITE}/index/{anno_id}?tab=documents")):
        for url, name in goszakup_links(get_text(f"{GZ_SITE}/actionAjaxModalShowFiles/{anno_id}/{group}")):
            p = download(url, folder, name or None)
            got.append((title if p else f"{title} — {name}: {LAST_ERROR}", p))
    return got


def docs_mitwork(buy_id, folder):
    page = get_text(f"{MITWORK}/publics/buy/{buy_id}")
    got = []
    for section, name, url in mitwork_files(page):
        if any(s in section.lower() for s in SKIP_SECTIONS):
            continue
        p = download(url, folder, name or None)
        got.append((section if p else f"{section} — {name}: {LAST_ERROR}", p))
    return got


def docs_meks(rec, folder):
    got, seen = [], set()
    for path, a in meks_attachments(rec):
        if a["id"] in seen:
            continue
        seen.add(a["id"])
        got.append((path.split(".")[-1], download(f"{MEKS}/attachments/{a['id']}/download", folder, a["filename"])))
    return got


def docs_samruk(uuids, folder):
    return [("Самрук", download(SAMRUK_FILE + u.strip(), folder)) for u in uuids if u.strip()]


def extract_text(docs_dir):
    r = subprocess.run([sys.executable, str(HERE / "extract_docs.py"), str(docs_dir)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout + r.stderr).strip().splitlines()[-3:]


def customer_history(system_id, org_id, keys, enstru, pages):
    """Договоры заказчика по похожему предмету: сначала по коду ЕНС ТРУ (сервер), затем по словам
    названия на последних страницах реестра (код у Самрука пуст)."""
    rows, seen = [], set()
    base = {"system_id": system_id, "customer_organization_id": org_id, "limit": 100}
    queries = []
    for code in enstru or []:
        queries.append(dict(base, enstru_code=code))
    queries.append(base)
    for qi, q in enumerate(queries):
        by_code = qi < len(enstru or [])
        for page in range(pages if not by_code else 5):
            d = get_json(f"{UNI}/contracts/?" + urllib.parse.urlencode(dict(q, offset=page * 100)))
            res = (d or {}).get("results") or []
            for c in res:
                key = c.get("id")
                if key in seen:
                    continue
                if by_code or similar(c.get("announcement_name"), keys):
                    seen.add(key)
                    rows.append(c)
            if not d or not d.get("next"):
                break
    rows.sort(key=lambda c: c.get("sign_date") or (c.get("created") or "")[:10], reverse=True)
    return rows


HIST_COLS = ["sign_date", "announcement_number", "announcement_name", "supplier_organization_name",
             "contract_price_with_vat", "status_name", "purchase_method_name", "contract_type_name"]


def write_history(folder, rows):
    p = folder / "history.csv"
    with p.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=HIST_COLS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


def past_protocols(rows, folder, limit):
    """Протоколы итогов прошлых конкурсов заказчика (госзакуп). Разбор — firm.py."""
    sys.path.insert(0, str(HERE))
    import firm
    out, done = [], set()
    for c in rows:
        num = c.get("announcement_number") or ""
        method = (c.get("purchase_method_name") or "").lower()
        if not re.match(r"^\d+-\d+$", num) or num in done or "конкурс" not in method:
            continue
        done.add(num)
        try:
            buy = firm.find_buy(num)
            f = firm.protocol_file(buy) if buy else None
            if not f:
                continue
            dest = download(f["filePath"], folder / "protocols", f"{num}.html")
            if not dest or dest.suffix.lower() not in (".html", ".htm"):
                continue
            pr = firm.parse_protocol(dest.read_text(encoding="utf-8", errors="replace"))
        except (Exception, SystemExit):  # SystemExit от firm.py или API госзакупа недоступен
            continue
        for lt in pr["лоты"]:
            out.append({"объявление": num, "лот": lt["лот"], "название": lt["название"],
                        "заявок": len(lt["заявки"]), "отклонено": len(lt["отклонены"]),
                        "отклонены": lt["отклонены"], "цены": lt["цены"], "победитель": lt["победитель"]})
        if len(done) >= limit:
            break
    (folder / "protocols").mkdir(exist_ok=True)
    (folder / "protocols" / "protocols.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def money(x):
    try:
        return f"{float(x):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def write_summary(folder, card, docs, texts, hist, prots, note):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    L = [f"# Сводка лота — {card['площадка']} {card['объявление']}", "",
         f"Снято скриптом `engine/scripts/lot.py` {now}. Здесь только снятые факты; выводы — в `анализ.md`.", ""]
    L += ["## Карточка", "", "| Поле | Значение |", "|---|---|"]
    for k in ("площадка", "объявление", "название", "способ", "статус", "сумма", "заказчик", "БИН заказчика",
              "приём заявок", "ЕНС ТРУ", "ссылка"):
        if card.get(k):
            L.append(f"| {k} | {card[k]} |")
    if card.get("лоты"):
        L += ["", "| Лот | Название | Сумма, ₸ |", "|---|---|---|"]
        for l in card["лоты"]:
            L.append(f"| {l[0]} | {l[1][:90]} | {money(l[2])} |")
    L += ["", f"## Документы — {sum(1 for _, p in docs if p)} из {len(docs)}", "",
          "Папка `docs/` (вне git), текст — `docs/_text/`.", ""]
    for sec, p in docs:
        L.append(f"- {sec}: {p.name if p else 'НЕ СКАЧАЛСЯ'}")
    if note:
        L += ["", f"**{note}**"]
    if texts:
        L += ["", "Текст: " + " · ".join(texts)]
        if any(re.match(r"^\s*0\s", t) for t in " · ".join(texts).split(" · ")):
            L += ["", "**Файлы с нулём знаков — сканы: текста в них нет, читать сами PDF постранично.**"]
    L += ["", f"## История заказчика — договоров по похожему предмету: {len(hist)}", "",
          "Полностью — `history.csv`.", "", "| Подписан | Объявление | Предмет | Поставщик | Сумма, ₸ | Статус |",
          "|---|---|---|---|---|---|"]
    for c in hist[:20]:
        L.append(f"| {c.get('sign_date') or (c.get('created') or '')[:10]} | {c.get('announcement_number')} | "
                 f"{(c.get('announcement_name') or '')[:60]} | {(c.get('supplier_organization_name') or '—')[:40]} | "
                 f"{money(c.get('contract_price_with_vat'))} | {c.get('status_name') or ''} |")
    if prots:
        L += ["", f"## Протоколы итогов прошлых конкурсов — {len(prots)} лотов", "",
              "Разбор — `protocols/protocols.json` (участники, скидки, условные цены).", ""]
        for p in prots:
            win = (p.get("победитель") or {}).get("наименование") or "—"
            L.append(f"- {p['объявление']} · {p['название'][:70]} — заявок {p['заявок']}, отклонено {p['отклонено']}, "
                     f"победитель: {win}")
            for r in p["цены"][:6]:
                L.append(f"    - {r.get('наименование', '')[:45]} ({r.get('БИН', '')}): цена {r.get('цена поставщика', '')}, "
                         f"скидка {r.get('условная скидка, %', '')} %, ФУ {r.get('финустойчивость', '')}")
    (folder / "сводка.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------- команда ----------

def cmd_get(a):
    system, number = parse_ref(a.ref)
    system = a.system or system
    uni, card, docs, note, raw, info = [], {}, [], "", {}, ""
    year = a.year or datetime.now().year

    if system == "meks":
        rec = meks_find(number)
        if not rec:
            sys.exit(f"на МЭКС конкурс {number} не найден")
        d = rec.get("data") or {}
        card = {"площадка": "МЭКС", "объявление": rec.get("concursNum"), "название": rec.get("concursName"),
                "статус": rec.get("status"), "сумма": f"{money(d.get('totalSumWithoutNDS'))} ₸ без НДС",
                "заказчик": rec.get("customerName"), "БИН заказчика": rec.get("customerBin"),
                "приём заявок": f"{d.get('startDate') or '—'} → {d.get('endDate') or '—'}",
                "ЕНС ТРУ": f"{d.get('enstruCode') or ''} {d.get('enstruName') or ''}".strip(),
                "ссылка": "https://meks.zakup.sk.kz"}
        folder = lot_folder("meks", card["объявление"], year)
        raw = rec
        docs = docs_meks(rec, folder / "docs")
    else:
        if system == "mitwork" and re.fullmatch(r"\d+", number):  # id страницы → номер объявления «209591-3»
            m = re.search(r"Объявление\s+(\d+-\d+)", re.sub(r"<[^>]+>", " ", get_text(f"{MITWORK}/publics/buy/{number}")))
            mitwork_id, number = number, (m.group(1) if m else number)
        uni = find_unified(number, system)
        if not uni and system != "goszakup":
            sys.exit(f"лот {number} на единой платформе не найден; укажите ссылку на объявление")
        u0 = uni[0] if uni else {}
        system = system or SYSTEMS.get((u0.get("system") or {}).get("id"))
        anno = u0.get("announcement_number") or number
        cust = (u0.get("customers") or [{}])[0]
        card = {"площадка": {"goszakup": "госзакуп", "samruk": "Самрук-Қазына", "mitwork": "Mitwork",
                             "fsms": "ФСМС"}.get(system, system),
                "объявление": anno, "название": u0.get("announcement_name_ru"),
                "способ": u0.get("purchase_method_name"), "статус": u0.get("status_name"),
                "сумма": f"{money(sum(l.get('total_price') or 0 for l in uni))} ₸" if uni else "",
                "заказчик": cust.get("name_ru"), "БИН заказчика": cust.get("bin"),
                "приём заявок": f"{(u0.get('offer_start_date') or '')[:16]} → {(u0.get('offer_end_date') or '')[:16]}",
                "ЕНС ТРУ": ", ".join(sorted({l.get('enstru_key') for l in uni if l.get('enstru_key')})),
                "лоты": [(l.get("lot_number"), l.get("name_ru") or l.get("description_ru") or "", l.get("total_price"))
                         for l in uni]}
        folder = lot_folder(system, anno, year)
        raw = {"unified": uni}
        if system == "goszakup":
            anno_id = re.match(r"^(\d+)", anno).group(1)
            card["ссылка"] = f"https://goszakup.gov.kz/ru/announce/index/{anno_id}"
            try:
                docs = docs_goszakup_site(anno_id, folder / "docs")
            except Exception as e:
                docs = []
            if not docs:  # сайт не отдал — по ключу (API)
                try:
                    docs, raw["ows"] = docs_goszakup(anno_id, folder / "docs")
                except Exception as e:  # API госзакупа лежит (500) или ключ не принят (403)
                    note = (f"Госзакуп: документы не скачаны — ни сайт, ни API по ключу ({e}). Повторить позже той же "
                            "командой; 403 — ключ выпущен на другой адрес машины.")
            raw.setdefault("ows", {"TrdBuy": [], "Lots": []})
            if raw["ows"]["TrdBuy"] and not card.get("название"):
                card["название"] = raw["ows"]["TrdBuy"][0].get("nameRu")
        elif system == "mitwork":
            buy_id = u0.get("announcement_external_id") or locals().get("mitwork_id") or number
            card["ссылка"] = f"{MITWORK}/publics/buy/{buy_id}"
            docs = docs_mitwork(buy_id, folder / "docs")
        elif system == "samruk":
            card["ссылка"] = f"https://zakup.sk.kz/#/ext(popup:item/{anno}/advert)"
            if a.uuid:
                docs = docs_samruk(a.uuid, folder / "docs")
            else:
                note = ("Самрук: файлы не скачаны — список файлов закрыт защитой площадки. Открыть объявление в Chrome "
                        f"({card['ссылка']}), вкладка «Документы» у объявления и у лотов, взять UUID из сетевых запросов "
                        "eprocfilestorage/open-api/files/download/<UUID> и повторить: lot.py get "
                        f"{anno} --uuid <UUID> <UUID> …")
    (folder / "lot.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"папка: {folder}")
    for sec, p in docs:
        print(f"  {'+' if p else '-'} {sec}: {p.name if p else 'не скачался'}")
    texts = extract_text(folder / "docs") if any(p for _, p in docs) else []
    texts = [t.replace(str(folder) + "/", "").replace(str(folder) + "\\", "").replace(str(folder), ".") for t in texts]

    hist, prots = [], []
    if uni and (uni[0].get("customers") or [{}])[0].get("id"):
        keys = stems(card.get("название") or "") or stems(" ".join(l[1] for l in card.get("лоты", [])))
        enstru = [c for c in (card.get("ЕНС ТРУ") or "").split(", ") if c]
        hist = customer_history(uni[0]["system"]["id"], uni[0]["customers"][0]["id"], keys, enstru, a.pages)
        hist = [c for c in hist if c.get("announcement_number") != card["объявление"]]
        write_history(folder, hist)
        if system == "goszakup" and a.protocols:
            prots = past_protocols(hist, folder, a.protocols)
    elif system == "meks":
        info = "История заказчика МЭКС: договоров платформы в единой базе нет — не собрана."
    write_summary(folder, card, docs, texts, hist, prots, " ".join(x for x in (note, info) if x))
    print(f"история заказчика: {len(hist)} договоров · протоколов итогов: {len({p['объявление'] for p in prots})}")
    print(f"сводка: {folder / 'сводка.md'}")
    if note or info:
        print(note or info)
    if note:
        return 2
    return 0 if docs and all(p for _, p in docs) else 1


def cmd_selftest(a):
    assert parse_ref("https://goszakup.gov.kz/ru/announce/index/17954409") == ("goszakup", "17954409")
    assert parse_ref("https://eep.mitwork.kz/ru/publics/buy/211487") == ("mitwork", "211487")
    assert parse_ref("https://zakup.sk.kz/#/ext(popup:item/1267602/advert)") == ("samruk", "1267602")
    assert parse_ref("26000766KR-3") == ("meks", "26000766KR-3")
    assert parse_ref("17954409-1") == (None, "17954409-1")
    k = stems("Работы по капитальному ремонту канализационных сетей")
    assert k[:3] == ["капитал", "ремонту", "канализ"], k
    assert similar("Капитальный ремонт канализационной сети в г. Шахтинск", k)
    assert not similar("Поставка бетона М350", k)
    t = stems("Услуги по транспортному обслуживанию автомашинами класса F")
    assert similar("Услуги по транспортному обслуживанию автомашинами класса Е", t)
    assert not similar("Услуги по техническому обслуживанию оборудования автоматизированных систем", t)
    page = ('<tr><td>Протоколы итогов</td><td><a href="x">result_211487.pdf</a></td><td>78 КБ</td>'
            '<td><a href="https://eep.mitwork.kz/ru/files/download/a789adca40d69fa64708fb095fa7a608/?buyId=211487">'
            '</a></td></tr><tr><td>Открытые ключи</td><td>k.key</td><td><a href="https://eep.mitwork.kz/ru/files/'
            'download/62558ea82c6ec3ea62e9314a0fd1f054/?buyId=211487"></a></td></tr>')
    f = mitwork_files(page)
    assert f[0][:2] == ("Протоколы итогов", "result_211487.pdf") and len(f) == 2, f
    rec = {"data": {"appendixTSAttachments": [{"id": "1", "filename": "ТС.pdf"}], "x": {"yAttachments": [{"id": "2", "filename": "a.docx"}]}}}
    assert [a["filename"] for _, a in meks_attachments(rec)] == ["ТС.pdf", "a.docx"]
    assert safe_name('a/b:c?.pdf') == "a_b_c_.pdf"
    from email.header import decode_header, make_header
    assert str(make_header(decode_header("=?UTF-8?Q?=D0=9F=D1=80=D0=B8?= =?UTF-8?Q?_RU=2Epdf?="))) == "При RU.pdf"
    g = ('<tr><td>Конкурсная документация</td><td>Нет</td><td><button onclick="actionModalShowFiles(17954409,1)">'
         'Перейти</button></td></tr>')
    assert goszakup_groups(g) == [("Конкурсная документация", "1")]
    assert goszakup_links('<a href="https://v3bl.goszakup.gov.kz/files/download_file/1/2/"> konkurs.pdf</a>') == \
        [("https://v3bl.goszakup.gov.kz/files/download_file/1/2/", "konkurs.pdf")]
    print("selftest: ок")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("get")
    p.add_argument("ref")
    p.add_argument("--system", choices=["goszakup", "samruk", "mitwork", "meks", "fsms"])
    p.add_argument("--uuid", nargs="*", help="Самрук: UUID файлов из сетевых запросов страницы")
    p.add_argument("--year", type=int, help="год папки (по умолчанию текущий)")
    p.add_argument("--pages", type=int, default=10, help="страниц реестра договоров заказчика по 100 (поиск по словам)")
    p.add_argument("--protocols", type=int, default=5, help="сколько прошлых протоколов итогов разобрать (госзакуп)")
    sub.add_parser("selftest")
    a = ap.parse_args()
    return {"get": cmd_get, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
