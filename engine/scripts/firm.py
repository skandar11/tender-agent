#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""firm.py — проверка фирмы по БИН и таблица «как протокол итогов» конкурса госзакупа.

Что спрашивает конкурсная комиссия о каждом участнике, видно в «Протоколе об итогах»
конкурса: условные скидки (уплаченные налоги, территориальность, аудированная
отчётность в депозитарии, отрицательные значения по договорам и по РНУ, реестр
отечественных товаропроизводителей), финансовая устойчивость, сумма и число договоров
по предмету закупки за текущий год (Правила № 687: пп. 217, 254–271-1, 275; правило в базе —
tenders/tenders-vault/rules/pravilo-uslovnye-skidki.md). Этот скрипт собирает то же самое из двух мест:

  - из API портала по токену (ows.py): регистрация и место, договоры за год без
    дублей, расторжения, реестр недобросовестных (РНУ);
  - из самих протоколов итогов: что комиссия уже поставила фирме в прошлых конкурсах.

Команды (запуск из любого места; токен — secrets/goszakup-token, как у ows.py):

  firm.py check <БИН> [--year 2026] [--word слово] [--years 5]
        — фирма одной командой: кто, где, договоры за финансовый год (по последней
          редакции, допсоглашения не двоят), действующие, расторжения и «не заключён»
          за 5 лет, РНУ сейчас (API) и все прошлые включения (сайт портала);
          налоговый орган — если положен ключ КГД.
  firm.py protocol <номер объявления | id | файл.html> [--csv папка]
        — «Протокол об итогах» конкурса: участники, условные скидки по критериям,
          условные цены, финустойчивость, договоры за год, победитель. Таблицы — CSV.
  firm.py table <БИН> [<БИН> ...] [--year 2026] [--word слово] [--region 35] [--csv файл]
        — таблица по фирмам в столбцах протокола итогов: то, что видно из API.
  firm.py history <БИН> [--year 2026] [--max 10]
        — что комиссии ставили этой фирме: протоколы итогов конкурсов, по которым у неё
          договор в этом году; её строки из таблиц скидок и условных цен.
  firm.py selftest  — разбор протокола и сведение договоров на встроенном примере, без сети.

Налоговый орган (территориальность по месту учёта) отдаёт только API КГД — ключ
`X-Portal-Token` выдаёт КГД по обращению фирмы. Положить одной строкой в
secrets/kgd-token; без него проверка идёт по месту регистрации (КАТО) из госзакупа.
"""
import argparse
import csv
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ows  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Области по первым двум цифрам КАТО (справочник ref_kato портала, снят 2026-11-12).
REGIONS = {
    "10": "область Абай", "11": "Акмолинская", "15": "Актюбинская", "19": "Алматинская",
    "23": "Атырауская", "27": "Западно-Казахстанская", "31": "Жамбылская", "33": "область Жетісу",
    "35": "Карагандинская", "39": "Костанайская", "43": "Кызылординская", "47": "Мангистауская",
    "55": "Павлодарская", "59": "Северо-Казахстанская", "61": "Туркестанская", "62": "область Ұлытау",
    "63": "Восточно-Казахстанская", "71": "г. Астана", "75": "г. Алматы", "79": "г. Шымкент",
}

# Статусы договора (ref_contract_status) — как их читает поставщик.
ST_ACTIVE = {130, 131, 135, 160, 165, 185, 190, 460, 310, 315}   # подписание … действует
ST_DONE = {390, 464, 375, 465, 470}                              # исполнен, частично, срок истёк
ST_TERMINATED = {340, 462}                                       # расторгнут в одностороннем порядке
ST_AGREED = {350, 463, 345}                                      # по соглашению сторон
ST_NOT_SIGNED = {330, 461, 430}                                  # не заключён, отказ
ST_COURT = {480}                                                 # недействительный по решению суда
SUBJECT_TYPES = {1: "товары", 2: "работы", 3: "услуги"}

Q_CONTRACTS = """query($limit:Int,$after:Int,$filter:ContractFiltersInput){ Contract(limit:$limit, after:$after, filter:$filter){
  id parentId rootId refContractTypeId refContractStatusId deleted trdBuyId trdBuyNumberAnno trdBuyNameRu
  contractNumberSys signDate crdate finYear contractSumWnds faktSumWnds refSubjectTypeId faktTradeMethodsId
  customerBin descriptionRu
  RefContractStatus { nameRu }
} }"""
Q_RNU = """query($limit:Int,$after:Int,$filter:RnuFiltersInput){ Rnu(limit:$limit, after:$after, filter:$filter){
  id supplierBiin supplierNameRu startDate endDate
} }"""
Q_BUY_FILES = """query($limit:Int,$after:Int,$filter:TrdBuyFiltersInput){ TrdBuy(limit:$limit, after:$after, filter:$filter){
  id numberAnno nameRu refTradeMethodsId refBuyStatusId itogiDatePublic totalSum
  Files { nameRu filePath originalName }
} }"""


# ---------- договоры: сведение редакций ----------

def latest_versions(contracts):
    """Один договор — одна строка. Допсоглашение (parentId ≠ 0) — новая редакция того же
    договора (rootId общий); берём последнюю редакцию, удалённые записи выбрасываем."""
    by_root = {}
    for c in contracts:
        if c.get("deleted"):
            continue
        root = c.get("rootId") or c.get("id")
        cur = by_root.get(root)
        if cur is None or (c.get("id") or 0) > (cur.get("id") or 0):
            by_root[root] = c
    return list(by_root.values())


def contract_kind(c):
    s = c.get("refContractStatusId")
    for name, group in (("действует", ST_ACTIVE), ("исполнен", ST_DONE), ("расторгнут в одностороннем", ST_TERMINATED),
                        ("расторгнут по соглашению", ST_AGREED), ("не заключён", ST_NOT_SIGNED),
                        ("недействителен по суду", ST_COURT)):
        if s in group:
            return name
    return "прочее"


def summarize(contracts, word=None):
    """Сводка по договорам года: всего, сумма, действующих, по видам, по предмету (слово)."""
    rows = latest_versions(contracts)
    signed = [c for c in rows if c.get("refContractStatusId") not in ST_NOT_SIGNED]
    out = {
        "записей": len(contracts),
        "договоров": len(signed),
        "сумма": sum(float(c.get("contractSumWnds") or 0) for c in signed),
        "действующих": sum(1 for c in signed if c.get("refContractStatusId") in ST_ACTIVE),
        "по_статусу": Counter(contract_kind(c) for c in rows),
        "по_виду": Counter(SUBJECT_TYPES.get(c.get("refSubjectTypeId"), "—") for c in signed),
    }
    if word:
        stems = ows.stems_of(word)
        hit = [c for c in signed if all(s in ((c.get("trdBuyNameRu") or "") + " " + (c.get("descriptionRu") or "")).lower()
                                        for s in stems)]
        out["по_предмету"] = {"договоров": len(hit), "сумма": sum(float(c.get("contractSumWnds") or 0) for c in hit),
                              "действующих": sum(1 for c in hit if c.get("refContractStatusId") in ST_ACTIVE)}
    return out, rows


def fetch_contracts(bin_, year):
    items, _ = ows.gql_all("Contract", Q_CONTRACTS, {"filter": {"supplierBiin": bin_, "finYear": int(year)}})
    return items


NEG_STEP = 0.2   # Правила № 687: −0,2 % за каждый действующий договор по предмету текущего года (п. 265), за РНУ за 5 лет — разово (п. 266-1)


def neg_contracts(active_by_subject):
    """Отрицательное значение по договорам, п. 265: −0,2 × действующие договоры по предмету, заключённые в текущем
    финансовом году. Только работы и услуги приложения 9 (СМР, ПСД, экспертиза, ремонт дорог, технадзор, текущий
    ремонт зданий, питание, госсоцзаказ). Квазисектор — то же, договоры до 1,5 млн МРП (п. 140-2 Правил № 1253)."""
    return round(-NEG_STEP * active_by_subject, 2) if active_by_subject else 0.0


def neg_rnu(in_rnu_now, history, since):
    """Отрицательное значение по РНУ, п. 266-1: −0,2 один раз, если был в РНУ за 5 лет до приёма заявок."""
    return -NEG_STEP if in_rnu_now or any((h["включён"] or h["дата решения"]) >= since for h in history or []) else 0.0


def negatives(rows):
    """Факты реестра, не путать с «отрицательными значениями» Правил: расторжение в одностороннем
    порядке, «не заключён», недействителен по суду — сигнал о надёжности фирмы."""
    return [c for c in rows if c.get("refContractStatusId") in ST_TERMINATED | ST_NOT_SIGNED | ST_COURT]


# ---------- РНУ и участник ----------

def rnu(bin_):
    items, _ = ows.gql_all("Rnu", Q_RNU, {"filter": {"supplierBiin": bin_}})
    return items


def subject(bin_):
    """Участник по БИН, а если не нашёлся — по ИИН (у ИП 12 цифр те же)."""
    for f in ({"bin": bin_}, {"iin": bin_}):
        try:
            items, _ = ows.gql_all("Subjects", ows.Q_SUBJECT, {"filter": f}, limit=1)
        except ows.AccessError as e:
            if "Address" not in str(e):
                raise
            items, _ = ows.gql_all("Subjects", ows.Q_SUBJECT_PLAIN, {"filter": f}, limit=1)
        if items:
            return items[0]
    return None


def regions_of(subj):
    katos = []
    for k in (subj or {}).get("katoList") or []:
        katos.append(str(k))
    for a in (subj or {}).get("Address") or []:
        if a.get("katoCode"):
            katos.append(str(a["katoCode"]))
    return sorted({REGIONS.get(k[:2], k[:2]) for k in katos if k and k != "0"})


RNU_SITE = "https://old.goszakup.gov.kz/ru/registry/rnu/1/"   # страница поставщика: все включения, и прошлые (12.11)


def parse_rnu_page(text):
    """Страница поставщика в реестре недобросовестных → [{номер, заказчик, решение, дата решения, включён}]."""
    i = text.find("Номер решения суда")
    if i < 0:
        return []
    p = _Tables()
    p.feed(text[text.rfind("<table", 0, i):])
    p.close()
    out = []
    for kind, rows in p.events:
        if kind != "table":
            continue
        for r in rows:
            if len(r) >= 10 and re.match(r"^\d+-\d+$", r[0]):
                out.append({"номер": r[0], "заказчик": r[1], "БИН заказчика": r[2], "решение": r[6],
                            "дата решения": r[7][:10], "включён": r[9][:10]})
        break
    return out


def rnu_history(bin_):
    """Все включения в РНУ с сайта портала (API отдаёт только действующие). None — сайт не ответил."""
    req = urllib.request.Request(RNU_SITE + bin_, headers={"User-Agent": "Mozilla/5.0 (tender agent)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return parse_rnu_page(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError):
        return None


# ---------- КГД (по ключу, когда он будет) ----------

KGD_HOST = "https://portal.kgd.gov.kz"   # адрес сервисов — из списка API КГД (11.11); вживую с ключом не проверен


def kgd_token():
    f = ows.base_dir() / "secrets" / "kgd-token"
    return f.read_text(encoding="utf-8").strip() if f.exists() else None


def kgd_taxpayer(bin_):
    """Налоговый орган и регистрация из КГД. None — ключа нет; иначе dict или текст ошибки."""
    t = kgd_token()
    if not t:
        return None
    url = KGD_HOST + "/services/isnaportalsync/public/taxpayer-data?" + urllib.parse.urlencode(
        {"taxpayerCode": bin_, "taxpayerType": "UL" if len(bin_) == 12 and bin_[4] in "456" else "IP"})
    req = urllib.request.Request(url, headers={"X-Portal-Token": t, "User-Agent": "tender-agent/firm.py"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return f"КГД ответил {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return f"КГД недоступен: {e}"


# ---------- протокол итогов ----------

class _Tables(HTMLParser):
    """HTML → поток событий: ('text', строка) и ('table', [[ячейки]]). Вложенных таблиц в протоколе нет."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events, self._rows, self._row, self._cell, self._text = [], None, None, None, []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "table":
            self._flush()
            self._rows = []
        elif tag == "tr" and self._rows is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "br":
            self._data(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append(_norm("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self._rows.append(self._row)
            self._row = None
        elif tag == "table" and self._rows is not None:
            self.events.append(("table", self._rows))
            self._rows = None
        elif tag in ("p", "div", "h1", "h2", "h3", "h4", "li"):
            self._data("\n")

    def handle_data(self, d):
        if not self._skip:
            self._data(d)

    def _data(self, d):
        if self._cell is not None:
            self._cell.append(d)
        elif self._rows is None:
            self._text.append(d)

    def _flush(self):
        t = _norm("".join(self._text))
        if t:
            self.events.append(("text", t))
        self._text = []

    def close(self):
        super().close()
        self._flush()


def _norm(s):
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()


def _is_numbering(row):
    nums = [c for c in row if c]
    return bool(nums) and all(c.isdigit() for c in nums) and [int(c) for c in nums] == list(range(1, len(nums) + 1))


def _num(s):
    s = (s or "").replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


DISCOUNT_COLS = ["№", "наименование", "БИН", "налоги", "функц.", "техн.", "качеств.",
                 "эксплуат.", "территориальность", "аудит в депозитарии", "отриц. по договорам", "отриц. по РНУ",
                 "реестр КТП", "общая скидка, %"]
PRICE_COLS = ["№", "наименование", "БИН", "выделенная сумма", "цена поставщика", "сумма по ст. 13",
              "условная скидка, %", "условная цена", "финустойчивость", "договоров за год по предмету, ₸",
              "действующих договоров по предмету", "подача заявки"]


def parse_protocol(text):
    """Русская часть «Протокола об итогах» конкурса → {номер, название, лоты: [...]}."""
    i = text.find("Протокол об итогах")
    if i < 0:
        i = 0
    p = _Tables()
    p.feed(text[i:])
    p.close()
    out = {"номер": None, "название": None, "лоты": []}
    lot, last_text = None, ""
    for kind, val in p.events:
        if kind == "text":
            last_text = val
            if out["номер"] is None:
                m = re.search(r"№ конкурса\s+(\S+)", val)
                if m:
                    out["номер"] = m.group(1)
                m = re.search(r"Наименование конкурса\s+(.+?)(?:\s+Наименование организатора|$)", val)
                if m:
                    out["название"] = m.group(1).strip()
            for m in re.finditer(r"№ лота\s+(\S+)(?:\s+Наименование лота\s+(.+?))?(?=\s+Информация|\s*$)", val):
                lot = {"лот": m.group(1), "название": (m.group(2) or "").strip(), "заявки": [], "отклонены": [],
                       "скидки": [], "цены": [], "победитель": None, "второй": None}
                out["лоты"].append(lot)
            continue
        rows = val
        if not rows or lot is None:
            continue
        head = " ".join(rows[0]).lower()
        # строки участников: третья ячейка — БИН/ИИН; шапка бывает в две строки, нумерация столбцов — строкой цифр
        body = [r for r in rows[1:] if len(r) >= 3 and re.fullmatch(r"\d{9,12}", r[2])]
        if "дата и время" in head and "представлени" in head:
            lot["заявки"] = [{"наименование": r[1], "БИН": r[2], "подана": r[3] if len(r) > 3 else ""}
                             for r in body if len(r) >= 3 and r[2]]
        elif "условные скидки" in head:
            lot["скидки"] = [dict(zip(DISCOUNT_COLS, r)) for r in body if len(r) >= 3 and r[2]]
        elif "цена поставщика" in head:
            lot["цены"] = [dict(zip(PRICE_COLS, r)) for r in body if len(r) >= 3 and r[2]]
        elif "причина отклонения" in head and "отклоненные" in last_text.lower():
            lot["отклонены"] = [{"наименование": r[1], "БИН": r[2], "причина": " ".join(r[3:])}
                                for r in body if len(r) >= 3 and r[2]]
        elif "бенефициар" in head and "победител" in last_text.lower() and body:
            lot["победитель"] = {"наименование": body[0][1], "БИН": body[0][2]}
        elif "второе место" in last_text.lower() and body and len(body[0]) >= 3:
            lot["второй"] = {"наименование": body[0][1], "БИН": body[0][2]}
    return out


def find_buy(ref):
    """Номер объявления «17239595-1», id «17239595» → запись TrdBuy с файлами."""
    m = re.match(r"^(\d+)", ref)
    if not m:
        sys.exit(f"не понял номер объявления: {ref}")
    items, _ = ows.gql_all("TrdBuy", Q_BUY_FILES, {"filter": {"id": [int(m.group(1))]}}, limit=1)
    return items[0] if items else None


def protocol_file(buy):
    for f in buy.get("Files") or []:
        if (f.get("nameRu") or "").strip().lower().startswith("протокол итогов") and f.get("filePath"):
            return f
    return None


def load_protocol(ref):
    """Файл .html, номер объявления или id → (текст протокола, подпись источника)."""
    p = Path(ref)
    if p.suffix.lower() in (".html", ".htm") and p.exists():
        return p.read_text(encoding="utf-8", errors="replace"), str(p)
    buy = find_buy(ref)
    if not buy:
        sys.exit(f"объявление {ref} не найдено")
    f = protocol_file(buy)
    if not f:
        sys.exit(f"у объявления {buy.get('numberAnno')} нет «Протокола итогов» в файлах "
                 f"(итоги: {buy.get('itogiDatePublic') or 'не подведены'})")
    import tempfile
    d = Path(tempfile.gettempdir()) / "tender-agent" / "protocols"
    d.mkdir(parents=True, exist_ok=True)
    dest = d / Path(f.get("originalName") or f"{buy['id']}.html").name
    if not (dest.exists() and dest.stat().st_size):
        if not ows._download(f["filePath"], dest):
            sys.exit("протокол не скачался")
    if dest.suffix.lower() not in (".html", ".htm"):
        sys.exit(f"протокол лежит не в HTML ({dest.name}) — разбор PDF не написан: {dest}")
    return dest.read_text(encoding="utf-8", errors="replace"), f"{buy.get('numberAnno')} · {dest}"


def print_protocol(pr):
    print(f"Протокол об итогах {pr.get('номер') or '—'} · {pr.get('название') or ''}")
    for lot in pr["лоты"]:
        print(f"\nлот {lot['лот']} · {lot['название']}")
        print(f"  заявок {len(lot['заявки'])} · отклонено {len(lot['отклонены'])}")
        for r in lot["отклонены"]:
            print(f"    отклонён: {r['наименование'][:50]} ({r['БИН']}) — {r['причина'][:120]}")
        if lot["скидки"]:
            print("  условные скидки, %:")
            print(f"    {'БИН':<13} {'налоги':>6} {'терр.':>6} {'аудит':>6} {'дог.−':>6} {'РНУ−':>6} {'КТП':>5} {'всего':>6}  наименование")
            for r in lot["скидки"]:
                print(f"    {r.get('БИН',''):<13} {r.get('налоги',''):>6} {r.get('территориальность',''):>6} "
                      f"{r.get('аудит в депозитарии',''):>6} {r.get('отриц. по договорам',''):>6} {r.get('отриц. по РНУ',''):>6} "
                      f"{r.get('реестр КТП',''):>5} {r.get('общая скидка, %',''):>6}  {r.get('наименование','')[:50]}")
        if lot["цены"]:
            print("  условные цены (место — по порядку протокола):")
            print(f"    {'БИН':<13} {'цена':>14} {'скидка':>6} {'усл. цена':>14} {'ФУ':>7} {'дог. за год, ₸':>16} {'действ.':>7}  наименование")
            for r in lot["цены"]:
                print(f"    {r.get('БИН',''):<13} {ows.money(_num(r.get('цена поставщика'))):>14} {r.get('условная скидка, %',''):>6} "
                      f"{ows.money(_num(r.get('условная цена'))):>14} {r.get('финустойчивость',''):>7} "
                      f"{ows.money(_num(r.get('договоров за год по предмету, ₸'))):>16} {r.get('действующих договоров по предмету',''):>7}  "
                      f"{r.get('наименование','')[:45]}")
        if lot["победитель"]:
            print(f"  победитель: {lot['победитель']['наименование']} ({lot['победитель']['БИН']})")
        if lot["второй"]:
            print(f"  второе место: {lot['второй']['наименование']} ({lot['второй']['БИН']})")


def write_csv(path, rows, cols):
    """CSV для Excel: UTF-8 с BOM, разделитель «;»."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


# ---------- команды ----------

def cmd_check(a):
    year = int(a.year or datetime.now().year)
    s = subject(a.bin)
    if not s:
        print(f"{a.bin}: участник в реестре портала не найден")
    else:
        print(f"{s.get('nameRu')} · БИН {s.get('bin') or s.get('iin')}")
        print(f"  запись участника на портале от {ows.date_short(s.get('regdate'))[:10]} · место: {', '.join(regions_of(s)) or '—'}")
        for ad in s.get("Address") or []:
            print(f"  адрес: {ad.get('address')}")
    kg = kgd_taxpayer(a.bin)
    if kg is None:
        print("  налоговый орган: ключа КГД нет (secrets/kgd-token) — территориальность по месту регистрации выше")
    elif isinstance(kg, str):
        print("  налоговый орган: " + kg)
    else:
        print("  КГД: " + json.dumps(kg, ensure_ascii=False)[:400])

    cur = fetch_contracts(a.bin, year)
    sm, rows = summarize(cur, a.word)
    print(f"\nдоговоры {year} финансового года (поставщик): {sm['договоров']} на {ows.money(sm['сумма'])} ₸ "
          f"(записей в реестре {sm['записей']}, без допсоглашений и «не заключён»); действующих {sm['действующих']}")
    print("  по виду: " + (", ".join(f"{k} {v}" for k, v in sm["по_виду"].most_common()) or "—"))
    print("  по статусу: " + (", ".join(f"{k} {v}" for k, v in sm["по_статусу"].most_common()) or "—"))
    if a.word:
        pp = sm["по_предмету"]
        print(f"  по предмету «{a.word}»: {pp['договоров']} на {ows.money(pp['сумма'])} ₸, действующих {pp['действующих']}")
        print(f"  отрицательное значение по договорам (п. 265 Правил № 687): {neg_contracts(pp['действующих'])}% "
              f"— если предмет из приложения 9 (СМР, ПСД, ремонт дорог, технадзор…)")

    print("  расторжения и срывы (факты реестра, не «отрицательные значения» Правил):")
    neg_all = []
    for y in range(year - a.years + 1, year + 1):
        yr_rows = rows if y == year else latest_versions(fetch_contracts(a.bin, y))
        n = negatives(yr_rows)
        neg_all += n
        print(f"  {y}: расторгнуто в одностороннем {sum(1 for c in n if c['refContractStatusId'] in ST_TERMINATED)} · "
              f"не заключено {sum(1 for c in n if c['refContractStatusId'] in ST_NOT_SIGNED)} · "
              f"по суду {sum(1 for c in n if c['refContractStatusId'] in ST_COURT)}")
    for c in sorted(neg_all, key=lambda c: c.get("signDate") or c.get("crdate") or "", reverse=True)[:10]:
        print(f"    {(c.get('signDate') or c.get('crdate') or '—')[:10]} {(c.get('RefContractStatus') or {}).get('nameRu') or contract_kind(c):<34} "
              f"{ows.money(c.get('contractSumWnds')):>13} ₸  {c.get('trdBuyNumberAnno') or c.get('contractNumberSys')} · {(c.get('trdBuyNameRu') or '')[:50]}")

    r = rnu(a.bin)
    if r:
        for x in r:
            print(f"\nРНУ: СЕЙЧАС В РЕЕСТРЕ — с {x['startDate'][:10]} по {(x.get('endDate') or '—')[:10]}")
    else:
        print("\nРНУ: сейчас не числится")
    hist = rnu_history(a.bin)
    since = f"{year - 5}-{datetime.now():%m-%d}"
    if hist is None:
        print("  история РНУ: сайт портала не ответил — открыть вручную " + RNU_SITE + a.bin)
    else:
        recent = [h for h in hist if (h["включён"] or h["дата решения"]) >= since]
        print(f"  история РНУ (сайт портала): включений всего {len(hist)}, за 5 лет {len(recent)}")
        print(f"  отрицательное значение по РНУ (п. 266-1 Правил № 687): {neg_rnu(bool(r), hist, since)}%")
        for h in hist[:10]:
            print(f"    включён {h['включён']} · решение {h['решение']} от {h['дата решения']} · заказчик {h['заказчик'][:60]}")
    f_out = ows.cache_write(f"firm_{a.bin}_{year}", {"subject": s, "contracts": rows, "negatives": neg_all, "rnu": r,
                                                     "rnu_history": hist})
    print(f"\nданные: {f_out}")
    return 0


def firm_row(bin_, year, word=None, region=None):
    s = subject(bin_)
    sm, rows = summarize(fetch_contracts(bin_, year), word)
    regs = regions_of(s)
    neg = negatives(rows)
    r = rnu(bin_)
    hist = rnu_history(bin_) or []
    pp = sm.get("по_предмету") or {}
    row = {
        "наименование": (s or {}).get("nameRu") or (r[0].get("supplierNameRu") if r else None)
                        or "не найден в реестре участников",
        "БИН": bin_,
        "место (КАТО)": ", ".join(regs) or "—",
        "территориальность": ("да" if REGIONS.get(region) in regs else "нет") if region else "—",
        "аудит в депозитарии": "нет данных (dfo.kz)",
        "налоги / налоговый орган": "нет данных (ключ КГД)",
        "отриц. по договорам, %": neg_contracts(pp["действующих"]) if pp else "нужно --word (предмет)",
        "отриц. по РНУ, %": neg_rnu(bool(r), hist, f"{year - 5}-{datetime.now():%m-%d}"),
        "РНУ": (("в реестре до " + r[0]["endDate"][:10]) if r else "нет")
               + (f"; за 5 лет включений {sum(1 for h in hist if h['включён'] >= f'{year - 5}-{datetime.now():%m-%d}')}" if hist else ""),
        "расторжения и срывы за год": f"{len(neg)} (одностор. {sum(1 for c in neg if c['refContractStatusId'] in ST_TERMINATED)})",
        "договоров за год": sm["договоров"],
        "сумма за год, ₸": round(sm["сумма"], 2),
        "действующих": sm["действующих"],
        "по предмету за год, ₸": round(pp["сумма"], 2) if pp else "—",
        "действующих по предмету": pp.get("действующих", "—") if pp else "—",
    }
    return row


TABLE_COLS = ["наименование", "БИН", "место (КАТО)", "территориальность", "аудит в депозитарии",
              "налоги / налоговый орган", "отриц. по договорам, %", "отриц. по РНУ, %", "РНУ",
              "расторжения и срывы за год", "договоров за год", "сумма за год, ₸", "действующих",
              "по предмету за год, ₸", "действующих по предмету"]


def cmd_table(a):
    year = int(a.year or datetime.now().year)
    rows = [firm_row(b, year, a.word, a.region) for b in a.bins]
    print(f"Фирмы в столбцах протокола итогов · {year} финансовый год"
          + (f" · предмет «{a.word}»" if a.word else "") + (f" · регион работ {REGIONS.get(a.region, a.region)}" if a.region else ""))
    for r in rows:
        print("\n" + r["наименование"] + f" ({r['БИН']})")
        for k in TABLE_COLS[2:]:
            v = r[k]
            print(f"  {k}: {ows.money(v) if isinstance(v, float) and '₸' in k else (f'{v:g}' if isinstance(v, float) else v)}")
    if a.csv:
        print(f"\nтаблица: {write_csv(a.csv, rows, TABLE_COLS)}")
    return 0


def cmd_protocol(a):
    text, src = load_protocol(a.ref)
    pr = parse_protocol(text)
    print(f"источник: {src}")
    print_protocol(pr)
    if a.csv:
        d = Path(a.csv)
        for lot in pr["лоты"]:
            tag = re.sub(r"[^\w-]+", "_", lot["лот"])
            if lot["скидки"]:
                print("скидки: " + str(write_csv(d / f"{tag}_скидки.csv", lot["скидки"], DISCOUNT_COLS)))
            if lot["цены"]:
                print("цены: " + str(write_csv(d / f"{tag}_цены.csv", lot["цены"], PRICE_COLS)))
    return 0


def cmd_history(a):
    year = int(a.year or datetime.now().year)
    rows = latest_versions(fetch_contracts(a.bin, year))
    buys = []
    for c in sorted(rows, key=lambda c: c.get("signDate") or "", reverse=True):
        if c.get("trdBuyId") and c["trdBuyId"] not in buys and c.get("faktTradeMethodsId") == 2:   # 2 — открытый конкурс
            buys.append(c["trdBuyId"])
    print(f"конкурсов с договором {year}: {len(buys)}; разбираю до {a.max}")
    found = []
    for bid in buys[: a.max]:
        try:
            text, src = load_protocol(str(bid))
        except SystemExit as e:
            print(f"  {bid}: {e}")
            continue
        pr = parse_protocol(text)
        for lot in pr["лоты"]:
            d = next((r for r in lot["скидки"] if r.get("БИН") == a.bin), None)
            p = next((r for r in lot["цены"] if r.get("БИН") == a.bin), None)
            if d or p:
                found.append((pr.get("номер"), lot["лот"], d or {}, p or {}))
    print(f"{'конкурс':<14} {'лот':<16} {'налоги':>6} {'терр.':>5} {'аудит':>5} {'дог.−':>5} {'РНУ−':>5} {'скидка':>6} {'ФУ':>7} {'дог. за год, ₸':>16}")
    for num, lot, d, p in found:
        print(f"{num or '—':<14} {lot:<16} {d.get('налоги',''):>6} {d.get('территориальность',''):>5} {d.get('аудит в депозитарии',''):>5} "
              f"{d.get('отриц. по договорам',''):>5} {d.get('отриц. по РНУ',''):>5} {d.get('общая скидка, %',''):>6} "
              f"{p.get('финустойчивость',''):>7} {ows.money(_num(p.get('договоров за год по предмету, ₸'))):>16}")
    return 0


# ---------- офлайн-проверка ----------

SAMPLE_PROTOCOL = """<html><body>
<p>Протокол об итогах государственных закупок способом конкурса № 100-ОК1</p>
<p>№ конкурса 100-ОК1</p><p>Наименование конкурса Ремонт дамбы Наименование организатора ГУ Пример</p>
<p>№ лота 200-ОК1</p><p>Наименование лота Ремонт дамбы</p>
<p>Информация о представленных заявках на участие в конкурсе (лоте): 3</p>
<table><tr><td>№</td><td>Наименование потенциального поставщика</td><td>БИН (ИИН)/ИНН/УНП</td><td>Дата и время представления заявки (по хронологии)</td></tr>
<tr><td>1</td><td>ТОО &quot;Альфа&quot;</td><td>111111111111</td><td>01.07.2026 10:00:00</td></tr>
<tr><td>2</td><td>ТОО &quot;Бета&quot;</td><td>222222222222</td><td>02.07.2026 11:00:00</td></tr>
<tr><td>3</td><td>ТОО &quot;Гамма&quot;</td><td>333333333333</td><td>03.07.2026 12:00:00</td></tr></table>
<p>Отклоненные заявки на участие в конкурсе: 1</p>
<table><tr><td>№</td><td>Наименование потенциального поставщика</td><td>БИН (ИИН)/ИНН/УНП</td><td>Причина отклонения 1</td></tr>
<tr><td>1</td><td>ТОО "Гамма"</td><td>333333333333</td><td>несоответствие квалификационным требованиям</td></tr></table>
<p>Информация о результатах применения относительного значения критериев</p>
<table><tr><td rowspan="2">№</td><td rowspan="2">Наименование</td><td rowspan="2">БИН (ИИН)/ ИНН/НП</td><td colspan="11">Условные скидки, %</td></tr>
<tr><td>Показатель уплаченных налогов</td><td>Ф</td><td>Т</td><td>К</td><td>Э</td>
<td>Нахождение</td><td>Размещение аудированной</td><td>Отрицательные значения по договорам</td><td>Отрицательные значения по РНУ</td><td>КТП</td><td>Общая условная скидка, %</td></tr>
<tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td>9</td><td>10</td><td>11</td><td>12</td><td>13</td><td>14</td></tr>
<tr><td>1</td><td>ТОО "Альфа"</td><td>111111111111</td><td>1</td><td>0</td><td>0</td><td>0</td><td>0</td><td>1</td><td>1</td><td>0</td><td>0</td><td>0</td><td>3</td></tr>
<tr><td>2</td><td>ТОО "Бета"</td><td>222222222222</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>-1</td><td>0</td><td>0</td><td>-0.5</td></tr></table>
<p>Расчет условных цен участников конкурса:</p>
<table><tr><td>№</td><td>Наименование</td><td>БИН</td><td>Выделенная сумма</td><td>Цена поставщика</td><td>Сумма в соответствии со статьей 13</td><td>Размер условной скидки</td><td>Цена с учетом условной скидки</td><td>Показатель финансовой устойчивости</td><td>Общая сумма договоров</td><td>Количество действующих договоров</td><td>Дата и время подачи заявки</td></tr>
<tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td>9</td><td>10</td><td>11</td><td>12</td></tr>
<tr><td>1</td><td>ТОО "Альфа"</td><td>111111111111</td><td>50000000</td><td>45000000</td><td>0</td><td>3</td><td>43650000</td><td>12.5</td><td>150000000.5</td><td>4</td><td>01.07.2026 10:00:00</td></tr></table>
<p>Решение конкурсной комиссии 1. Определить победителем по лоту №200-ОК1:</p>
<table><tr><td>№</td><td>Наименование</td><td>БИН</td><td>Ф.И.О. бенефициарного владельца</td></tr><tr><td>1</td><td>2</td><td>3</td><td>4</td></tr>
<tr><td>1</td><td>ТОО "Альфа"</td><td>111111111111</td><td>—</td></tr></table>
<p>Потенциальный поставщик, занявший второе место:</p>
<table><tr><td>№</td><td>Наименование</td><td>БИН</td></tr><tr><td>1</td><td>2</td><td>3</td></tr><tr><td>1</td><td>ТОО "Бета"</td><td>222222222222</td></tr></table>
</body></html>"""


def cmd_selftest(a):
    pr = parse_protocol("<p>Қорытындылар туралы хаттама</p>" + SAMPLE_PROTOCOL)
    assert pr["номер"] == "100-ОК1", pr
    assert pr["название"] == "Ремонт дамбы", pr
    assert len(pr["лоты"]) == 1
    lot = pr["лоты"][0]
    assert lot["лот"] == "200-ОК1" and lot["название"] == "Ремонт дамбы", lot
    assert [r["БИН"] for r in lot["заявки"]] == ["111111111111", "222222222222", "333333333333"]
    assert lot["заявки"][0]["наименование"] == 'ТОО "Альфа"'
    assert lot["отклонены"][0]["БИН"] == "333333333333" and "квалификац" in lot["отклонены"][0]["причина"]
    assert len(lot["скидки"]) == 2 and lot["скидки"][1]["отриц. по договорам"] == "-1"
    assert lot["скидки"][0]["территориальность"] == "1" and lot["скидки"][1]["общая скидка, %"] == "-0.5"
    assert lot["скидки"][0]["налоги"] == "1" and lot["скидки"][0]["аудит в депозитарии"] == "1"
    assert lot["цены"][0]["финустойчивость"] == "12.5" and _num(lot["цены"][0]["условная цена"]) == 43650000
    assert lot["победитель"]["БИН"] == "111111111111" and lot["второй"]["БИН"] == "222222222222"
    print_protocol(pr)

    cs = [
        {"id": 1, "rootId": 1, "parentId": 0, "refContractStatusId": 455, "contractSumWnds": 100, "refSubjectTypeId": 2,
         "trdBuyNameRu": "Ремонт дамбы", "deleted": 0},
        {"id": 5, "rootId": 1, "parentId": 1, "refContractStatusId": 190, "contractSumWnds": 120, "refSubjectTypeId": 2,
         "trdBuyNameRu": "Ремонт дамбы", "deleted": 0},
        {"id": 2, "rootId": 2, "parentId": 0, "refContractStatusId": 390, "contractSumWnds": 50, "refSubjectTypeId": 3,
         "trdBuyNameRu": "Технадзор", "deleted": 0},
        {"id": 3, "rootId": 3, "parentId": 0, "refContractStatusId": 330, "contractSumWnds": 70, "refSubjectTypeId": 2,
         "trdBuyNameRu": "Ремонт дамбы", "deleted": 0},
        {"id": 4, "rootId": 4, "parentId": 0, "refContractStatusId": 340, "contractSumWnds": 30, "refSubjectTypeId": 2,
         "trdBuyNameRu": "Ремонт моста", "deleted": 0},
        {"id": 6, "rootId": 6, "parentId": 0, "refContractStatusId": 190, "contractSumWnds": 999, "deleted": 1},
    ]
    sm, rows = summarize(cs, "ремонт дамбы")
    assert len(rows) == 4, rows                    # редакции сведены, удалённый выброшен
    assert sm["договоров"] == 3 and sm["сумма"] == 200, sm     # 120 (последняя редакция) + 50 + 30; «не заключён» не считается
    assert sm["действующих"] == 1
    assert sm["по_предмету"] == {"договоров": 1, "сумма": 120, "действующих": 1}, sm
    assert sorted(c["id"] for c in negatives(rows)) == [3, 4]
    assert sm["по_виду"]["работы"] == 2 and sm["по_виду"]["услуги"] == 1
    assert regions_of({"katoList": [351010000], "Address": [{"katoCode": "354400000"}]}) == ["Карагандинская"]
    page = ('<table><tr><th>№</th><th>Наименование заказчика</th><th>БИН заказчика</th><th>Наименование поставщика</th>'
            '<th>БИН/ИИН поставщика</th><th>ИНН/УНП</th><th>Номер решения суда/уполномоченного органа</th><th>Дата решения</th>'
            '<th>Отправлено</th><th>Включено</th></tr><tr><td>1-290841</td><td>КГУ Школа</td><td>111140005356</td><td>ТОО Пример</td>'
            '<td>720202303191</td><td></td><td>№4712</td><td>2026-10-08 00:00:00</td><td>2026-11-11 17:56:02</td>'
            '<td>2026-11-12 08:42:50</td></tr></table>')
    h = parse_rnu_page(page)
    assert h == [{"номер": "1-290841", "заказчик": "КГУ Школа", "БИН заказчика": "111140005356", "решение": "№4712",
                  "дата решения": "2026-10-08", "включён": "2026-11-12"}], h
    assert parse_rnu_page("<table><tr><th>Номер решения суда</th></tr></table>") == []
    assert neg_contracts(4) == -0.8 and neg_contracts(0) == 0
    assert neg_rnu(False, h, "2021-11-12") == -0.2 and neg_rnu(False, h, "2026-12-01") == 0.0 and neg_rnu(True, [], "x") == -0.2
    assert _is_numbering(["1", "2", "3"]) and not _is_numbering(["1", "ТОО", "3"])
    print("\nselftest: разбор протокола (заявки, отклонённые, скидки, условные цены, победитель, второе место), "
          "сведение редакций договоров, сумма и счёт по предмету, отрицательные, регион по КАТО, страница РНУ, отрицательные значения п. 265 и п. 266-1 — ок")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check"); p.add_argument("bin"); p.add_argument("--year"); p.add_argument("--word")
    p.add_argument("--years", type=int, default=5, help="за сколько лет смотреть расторжения")
    p = sub.add_parser("table"); p.add_argument("bins", nargs="+"); p.add_argument("--year"); p.add_argument("--word")
    p.add_argument("--region", help="две цифры КАТО области работ, 35 — Карагандинская"); p.add_argument("--csv")
    p = sub.add_parser("protocol"); p.add_argument("ref"); p.add_argument("--csv", help="папка для CSV")
    p = sub.add_parser("history"); p.add_argument("bin"); p.add_argument("--year"); p.add_argument("--max", type=int, default=10)
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    fn = {"check": cmd_check, "table": cmd_table, "protocol": cmd_protocol, "history": cmd_history,
          "selftest": cmd_selftest}[a.cmd]
    try:
        return fn(a)
    except ows.AccessError as e:
        sys.exit(f"портал: {e}")


if __name__ == "__main__":
    sys.exit(main())
