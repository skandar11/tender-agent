#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""finstab.py — финансовая устойчивость по форме портала госзакупок (профиль участника).

Цифры — из 1С (или из налоговых форм): по каждому году доход, уплаченные налоги,
основные средства на конец года (строки баланса 100+150), фонд оплаты труда,
численность. Скрипт считает то же, что портал показывает в кабинете: доход за три
года, предшествующих предыдущему, среднегодовой доход, показатель уплаченных налогов
(ПУН), среднюю стоимость ОС, ФОТ — и до какой суммы лота фирма может подать заявку.
Считает на год подачи: текущий и следующий (у каждого свои три года).

Вход — таблица (CSV «;» или .xlsx): первая строка — «показатель» и годы, дальше строки
с названиями ниже (регистр и порядок не важны). Пустая клетка — нет данных.

  показатель;2022;2023;2024;2025
  доход;394364613;573417672;992917305;2224286875
  налоги;50793314;17256814;60355510;172473881
  ос;8714681;5654503;0;57000000
  фот;72684591;61533037;120000000;70245503
  численность;;;;35

Команды:
  finstab.py calc <таблица> [--year 2026] [--next] [--name "ТОО …"] [--lot 50000000 --kind works [--msb]] [--xlsx файл]
  finstab.py template <файл.csv>   — пустая форма ввода на нужные годы
  finstab.py selftest              — формулы на встроенном примере

Выгрузка 1С ляжет сюда, когда будет образец: её столбцы сводятся к пяти строкам формы
(`from_1c` ниже — место для этого сведения). Формулы — Правила осуществления
государственных закупок (приказ МФ РК № 687), раздел о финансовой устойчивости;
правило в базе — tenders/tenders-vault/rules/pravilo-finustoychivost.md.
"""
import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Условия — одно место. Правила № 687, п. 57 в ред. приказа № 297 (с 12.07.2026), adilet 12.11.2026;
# правило в базе — tenders/tenders-vault/rules/pravilo-finustoychivost.md.
REVENUE_X_SUM = 2      # 1) доход за 3 года ≥ 1/2 суммы лота → лот ≤ доход × 2 (= среднегодовой × 6, как у портала)
PUN_MIN = 3.0          # 2) ПУН ≥ 3 % (ГСМ, промсборка — 1 %, п. 59)
FIXED_ASSETS_X = 15    # 3) ОС ≥ 1/15 суммы лота, но не выше 400 000 МРП → лот ≤ средняя ОС × 15; ОС ≥ 400 000 МРП — без предела
FIXED_ASSETS_CAP_MRP = 400_000
PAYROLL_X = 15         # 4) ФОТ за 3 года ≥ 1/15 суммы лота → лот ≤ ФОТ × 15
MRP = {2025: 3932, 2026: 4325}   # МРП по годам; 2026 — по памяти, сверить с законом о бюджете
# ФУ требуется, если лот больше (п. 53), МРП: товары 4 000 · работы 20 000 · услуги 8 000;
# ТЭО, ПСД, экспертиза, технадзор — при любой сумме (п. 54).
FU_FROM_MRP = {"goods": 4000, "works": 20000, "services": 8000}
# Какие условия по виду (пп. 58, 60, 63, 64): товары 1+2 · услуги 1+2+4 · работы МСБ, ТЭО/ПСД 1+2+4 · прочие работы — все.
CONDITIONS = {"goods": ["доход", "ПУН"], "services": ["доход", "ПУН", "ФОТ"],
              "works-msb": ["доход", "ПУН", "ФОТ"], "works": ["доход", "ПУН", "ОС", "ФОТ"]}

ALIASES = {
    "доход": "доход", "совокупный годовой доход": "доход", "выручка": "доход",
    "налоги": "налоги", "уплаченные налоги": "налоги",
    "ос": "ос", "основные средства": "ос", "основные средства (100+150)": "ос",
    "фот": "фот", "фонд оплаты труда": "фот",
    "численность": "численность", "среднегодовая численность": "численность",
}
KEYS = ["доход", "налоги", "ос", "фот", "численность"]
KIND_RU = {"works": "работы", "services": "услуги", "goods": "товары"}


def years_for(apply_year):
    """Три года, предшествующих предыдущему: заявка в 2026 → 2022, 2023, 2024."""
    return [apply_year - 4, apply_year - 3, apply_year - 2]


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(" ", "").replace(" ", "").replace(",", ".").strip()
    if s in ("", "-", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def read_table(path):
    """CSV («;» или «,») или xlsx → {показатель: {год: число}}."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError:
            sys.exit("для .xlsx нужен openpyxl: pip install openpyxl — или сохраните таблицу как CSV")
        ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
        rows = [[c for c in r] for r in ws.iter_rows(values_only=True)]
    else:
        text = path.read_text(encoding="utf-8-sig")
        delim = ";" if text.count(";") >= text.count(",") else ","
        rows = list(csv.reader(text.splitlines(), delimiter=delim))
    return parse_rows(rows)


def parse_rows(rows):
    rows = [r for r in rows if r and any(c not in (None, "") for c in r)]
    head = rows[0]
    years = []
    for c in head[1:]:
        n = _num(c)
        years.append(int(n) if n else None)
    data = {k: {} for k in KEYS}
    for r in rows[1:]:
        key = ALIASES.get(str(r[0] or "").strip().lower())
        if not key:
            continue
        for y, v in zip(years, r[1:]):
            if y:
                n = _num(v)
                if n is not None:
                    data[key][y] = n
    return data


def from_1c(path):
    """Выгрузка 1С → форма ввода. Пишется по образцу выгрузки (его ещё нет, 12.11)."""
    sys.exit("образца выгрузки 1С ещё нет: сведите цифры в форму ввода (finstab.py template) и запустите calc")


def calc(data, apply_year):
    ys = years_for(apply_year)
    got = lambda k: [data[k].get(y) for y in ys]   # noqa: E731
    rev, tax, fa, pay = got("доход"), got("налоги"), got("ос"), got("фот")
    r = {"год подачи": apply_year, "годы": ys, "доход": rev, "налоги": tax, "ос": fa, "фот": pay,
         "численность": data["численность"].get(apply_year - 1) or data["численность"].get(apply_year - 2)}
    full = lambda xs: all(x is not None for x in xs)   # noqa: E731
    r["доход за 3 года"] = sum(rev) if full(rev) else None
    r["среднегодовой доход"] = r["доход за 3 года"] / 3 if r["доход за 3 года"] is not None else None
    r["предел по доходу"] = r["доход за 3 года"] * REVENUE_X_SUM if r["доход за 3 года"] else None
    r["налоги за 3 года"] = sum(tax) if full(tax) else None
    r["ПУН, %"] = (r["налоги за 3 года"] / r["доход за 3 года"] * 100
                   if r["налоги за 3 года"] is not None and r["доход за 3 года"] else None)
    r["средняя ОС"] = sum(fa) / 3 if full(fa) else None
    mrp = MRP.get(apply_year) or MRP[max(MRP)]
    r["МРП"] = mrp
    if r["средняя ОС"] and r["средняя ОС"] >= FIXED_ASSETS_CAP_MRP * mrp:
        r["предел по ОС"] = float("inf")          # порог по ОС не выше 400 000 МРП — выполнен при любой сумме
    else:
        r["предел по ОС"] = r["средняя ОС"] * FIXED_ASSETS_X if r["средняя ОС"] else None
    r["ФОТ за 3 года"] = sum(pay) if full(pay) else None
    r["предел по ФОТ"] = r["ФОТ за 3 года"] * PAYROLL_X if r["ФОТ за 3 года"] else None
    return r


def limit_for(r, kind, pun_min=PUN_MIN):
    """Наименьший из пределов по условиям вида закупки. Возвращает (сумма, что режет):
    0 — ПУН ниже порога (подать нельзя ни на какую сумму); None — данных не хватает."""
    conds = CONDITIONS[kind]
    if "ПУН" in conds:
        if r["ПУН, %"] is None:
            return None, ["ПУН"]
        if r["ПУН, %"] < pun_min:
            return 0.0, f"ПУН {r['ПУН, %']:.2f}% < {pun_min:g}%"
    names = {"доход": "предел по доходу", "ОС": "предел по ОС", "ФОТ": "предел по ФОТ"}
    keys = [names[c] for c in conds if c != "ПУН"]
    vals = [(k, r[k]) for k in keys]
    if any(v is None for _, v in vals):
        return None, [k for k, v in vals if v is None]
    k, v = min(vals, key=lambda kv: kv[1])
    return v, k


def fu_needed(lot, kind, mrp):
    """Нужна ли ФУ для лота такой суммы (п. 53); ТЭО/ПСД/технадзор — всегда (п. 54), это решает человек."""
    base = "works" if kind.startswith("works") else kind
    return lot > FU_FROM_MRP[base] * mrp


def money(x):
    if x == float("inf"):
        return "без предела"
    return f"{x:,.2f}".replace(",", " ") if isinstance(x, (int, float)) else "нет данных"


def form_lines(r, name=None):
    """Строки в порядке формы портала."""
    ys = r["годы"]
    L = [("Финансовая устойчивость", None)]
    if name:
        L.append((f"{name} · год подачи {r['год подачи']} · данные за {ys[0]}–{ys[-1]}", None))
    L.append(("Доходы потенциального поставщика", None))
    for y, v in zip(ys, r["доход"]):
        L.append((f"Совокупный годовой доход за {y} год", money(v)))
    L += [("Доход в течение трех лет предшествующих предыдущему году", money(r["доход за 3 года"])),
          ("Среднегодовой доход", money(r["среднегодовой доход"])),
          (_can("по доходу", r["предел по доходу"], "доходу"), None),
          ("Показатель уплаченных налогов", None)]
    for y, v in zip(ys, r["налоги"]):
        L.append((f"Уплаченные налоги за {y} год", money(v)))
    L += [("Уплаченные налоги в течение трех лет предшествующих предыдущему году", money(r["налоги за 3 года"])),
          (f"Показатель уплаченных налогов в течение трех лет, предшествующих предыдущему году, составляет "
           f"{r['ПУН, %']:.2f}%." + ("" if r["ПУН, %"] >= PUN_MIN else f" Ниже {PUN_MIN:g}% — условие ПУН не выполнено.")
           if r["ПУН, %"] is not None else "Показатель уплаченных налогов: нет данных", None),
          ("Средняя стоимость основных средств", None)]
    for y, v in zip(ys, r["ос"]):
        L.append((f"Основные средства на конец отчетного периода (100+150) за {y} год", money(v)))
    L += [("Средняя стоимость основных средств в течение трех лет предшествующих предыдущему году", money(r["средняя ОС"])),
          (_can("по ОС", r["предел по ОС"], "средней стоимости основных средств"), None),
          ("Фонд оплаты труда", None)]
    for y, v in zip(ys, r["фот"]):
        L.append((f"Фонд оплаты труда за {y} год", money(v)))
    L += [("Фонд оплаты труда в течение трех лет предшествующих предыдущему году", money(r["ФОТ за 3 года"])),
          (_can("по ФОТ", r["предел по ФОТ"], "фонду оплаты труда"), None),
          ("Среднегодовая численность", None),
          ("Сотрудников в организации", str(int(r["численность"])) if r["численность"] else "нет данных"),
          ("Территориальный признак — код налогового органа", "из КГД (ключ) или из кабинета портала")]
    return L


def _can(_, limit, what):
    if limit is None:
        return f"Вы не можете подать заявку на лот: нет данных по {what}."
    if limit <= 0:
        return f"Вы не можете подать заявку на лот: по {what} предел нулевой."
    if limit == float("inf"):
        return f"Вы можете подать заявку на лот любой суммы: по {what} порог 400 000 МРП выполнен."
    return f"Вы можете подать заявку на лот, сумма которого не превышает - {money(limit)} тг"


def write_xlsx(path, sheets):
    try:
        import openpyxl
        from openpyxl.styles import Font
    except ImportError:
        sys.exit("для .xlsx нужен openpyxl: pip install openpyxl")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, lines in sheets:
        ws = wb.create_sheet(title[:31])
        ws.column_dimensions["A"].width = 95
        ws.column_dimensions["B"].width = 22
        for i, (a, b) in enumerate(lines, 1):
            ws.cell(i, 1, a)
            if b is None:
                ws.cell(i, 1).font = Font(bold=(i == 1 or not a.startswith(("Вы ", "Показатель уплаченных налогов в"))))
            else:
                ws.cell(i, 2, b)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def cmd_calc(a):
    data = read_table(a.table)
    y0 = int(a.year or datetime.now().year)
    years = [y0, y0 + 1] if a.next else [y0]
    sheets = []
    for y in years:
        r = calc(data, y)
        lines = form_lines(r, a.name)
        print("\n".join(f"{x}" + (f"  {v}" if v is not None else "") for x, v in lines))
        if a.lot:
            kind = a.kind + ("-msb" if a.msb and a.kind == "works" else "")
            kru = KIND_RU[a.kind] + (", малое предпринимательство" if kind == "works-msb" else "")
            if not fu_needed(a.lot, kind, r["МРП"]):
                print(f"\nЛот {money(a.lot)} ({kru}): финустойчивость не требуется — сумма не выше порога п. 53 "
                      f"({FU_FROM_MRP['works' if kind.startswith('works') else kind]:,} МРП".replace(",", " ")
                      + f" × {r['МРП']} ₸; кроме ТЭО, ПСД, экспертизы, технадзора)")
            lim, why = limit_for(r, kind, a.pun_min)
            if lim is None:
                print(f"\nЛот {money(a.lot)} ({kru}): не хватает данных — {', '.join(why)}")
            else:
                ok = a.lot <= lim
                print(f"\nЛот {money(a.lot)} ({kru}): {'можно' if ok else 'НЕЛЬЗЯ'} — наименьший предел {money(lim)} ({why}); "
                      f"условия: {' + '.join(CONDITIONS[kind])}")
        print()
        sheets.append((f"{y}", lines))
    if a.xlsx:
        print(f"таблица: {write_xlsx(a.xlsx, sheets)}")
    return 0


def cmd_template(a):
    y = datetime.now().year
    ys = list(range(y - 4, y))
    with open(a.file, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["показатель"] + ys)
        for k in ["доход", "налоги", "ос", "фот", "численность"]:
            w.writerow([k] + [""] * len(ys))
    print(f"форма ввода: {a.file} (годы {ys[0]}–{ys[-1]}: хватает на подачу в {y} и {y + 1})")
    return 0


def cmd_selftest(a):
    # Цифры — вымышленная фирма; круглые, чтобы проверка читалась глазами.
    rows = [["показатель", 2022, 2023, 2024, 2025],
            ["Совокупный годовой доход", "100 000 000", 200000000, 300000000, 600000000],
            ["налоги", 6000000, 6000000, 6000000, 30000000],
            ["ОС", 3000000, 6000000, 0, 9000000],
            ["ФОТ", 10000000, 10000000, 10000000, 20000000],
            ["численность", None, None, 20, 25],
            ["лишняя строка", 1, 2, 3, 4]]
    d = parse_rows(rows)
    assert d["доход"][2022] == 100000000 and "лишняя строка" not in d
    r = calc(d, 2026)
    assert r["годы"] == [2022, 2023, 2024]
    assert r["доход за 3 года"] == 600000000 and r["среднегодовой доход"] == 200000000
    assert r["предел по доходу"] == 1200000000
    assert abs(r["ПУН, %"] - 3.0) < 1e-9
    assert r["средняя ОС"] == 3000000 and r["предел по ОС"] == 45000000
    assert r["ФОТ за 3 года"] == 30000000 and r["предел по ФОТ"] == 450000000
    assert r["численность"] == 25
    assert r["предел по доходу"] == 1200000000          # 600 млн × 2 = среднегодовой 200 млн × 6
    assert limit_for(r, "works") == (45000000, "предел по ОС")
    assert limit_for(r, "works-msb") == (450000000, "предел по ФОТ")
    assert limit_for(r, "services") == (450000000, "предел по ФОТ")
    assert limit_for(r, "goods") == (1200000000, "предел по доходу")
    low = calc(parse_rows([["показатель", 2022, 2023, 2024], ["доход", 100, 100, 100], ["налоги", 1, 1, 1]]), 2026)
    assert limit_for(low, "goods")[0] == 0.0 and limit_for(low, "goods", pun_min=1)[0] == 600   # ПУН 1 %: не проходит при 3 %, проходит для ГСМ
    big = calc(parse_rows([["показатель", 2022, 2023, 2024], ["ос", 2e9, 2e9, 2e9]]), 2026)      # 2 млрд ≥ 400 000 × 4 325
    assert big["предел по ОС"] == float("inf") and money(big["предел по ОС"]) == "без предела"
    assert fu_needed(80_000_000, "works", 4325) is False and fu_needed(90_000_000, "works", 4325) is True
    assert fu_needed(20_000_000, "goods", 4325) is True
    r27 = calc(d, 2027)
    assert r27["годы"] == [2023, 2024, 2025] and r27["доход за 3 года"] == 1100000000
    r28 = calc(d, 2028)                       # 2026 нет — неполные данные, не ноль
    assert r28["доход за 3 года"] is None and limit_for(r28, "goods") == (None, ["ПУН"])
    lines = form_lines(r, "ТОО «Пример»")
    assert ("Среднегодовой доход", "200 000 000.00") in lines
    assert any(x.startswith("Вы можете подать заявку на лот, сумма которого не превышает - 45 000 000.00") for x, _ in lines)
    assert any("3.00%" in x for x, _ in lines)
    zero = calc(parse_rows([["показатель", 2022, 2023, 2024], ["ос", 0, 0, 0]]), 2026)
    assert "нет данных" in _can("", zero["предел по ОС"], "ОС")
    print("\n".join(f"{x}" + (f"  {v}" if v is not None else "") for x, v in lines))
    print("\nselftest: годы подачи, доход ×2, ПУН как условие допуска, ОС с потолком 400 000 МРП, ФОТ, условия по видам "
          "(товары, услуги, работы, работы МСБ), порог ФУ по п. 53, неполные данные — ок")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("calc"); p.add_argument("table"); p.add_argument("--year")
    p.add_argument("--next", action="store_true", help="и на следующий год")
    p.add_argument("--name"); p.add_argument("--lot", type=float)
    p.add_argument("--kind", choices=["works", "services", "goods"], default="works"); p.add_argument("--xlsx")
    p.add_argument("--msb", action="store_true", help="работы субъекта малого предпринимательства: без условия по ОС (п. 63)")
    p.add_argument("--pun-min", type=float, default=PUN_MIN, help="порог ПУН; ГСМ и промсборка — 1 (п. 59)")
    p = sub.add_parser("template"); p.add_argument("file")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    return {"calc": cmd_calc, "template": cmd_template, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
