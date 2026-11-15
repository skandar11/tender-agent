---
title: engine — the code the agent acts with
type: reference
status: active
sensitivity: normal
scope: all
updated: 2026-11-15
related:
  - operations/add-engine
  - ../inventory/executors
---

# engine — description

`../engine/` — Python 3, standard library only (`.xlsx` in `finstab.py` — `openpyxl`, optional). Run
from the root of the base. How to run — `../engine/README.md`; who calls what — `../inventory/executors.md`.

| Script | What | Key |
|---|---|---|
| `scripts/portal.py` | new lots of the one platform zakup.gov.kz (госзакуп, Самрук, Mitwork) and МЭКС by her filter; `--new` | no |
| `scripts/lot.py` | a lot as a folder: documents of any of the four platforms, their text, the customer's contracts, past protocols, `сводка.md` | no (Самрук files — UUID from Chrome) |
| `scripts/ows.py` | the portal API by key: lots, contracts, plans, a participant | her portal key |
| `scripts/firm.py` | a firm by BIN; «протокол итогов»; a table of firms; what commissions gave a firm | her portal key; КГД key — when issued |
| `scripts/finstab.py` | financial stability by the portal's form; the lot limit | no |
| `scripts/extract_docs.py` · `common.py` | text from pdf/docx/xlsx; shared network and files | no |

**Origin:** carried on 2026-11-15 from the previous agent (EASY TENDER instance, Maksi's layer of
2026-11-10…15); `ows.py` is the instance of Maksi's «поиск лотов». Platform facts checked live on
2026-11-15 are in the scripts' headers and in `tenders/tenders-vault/tools/`.
