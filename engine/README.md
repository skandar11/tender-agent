# engine — how to run

From the root of the base. macOS: `python3 engine/scripts/<script>.py …`; Windows: `py engine\scripts\<script>.py …`.

| Phrase | Command |
|---|---|
| что нового | `portal.py lots --subject works,services --min 20000000 --method contest --limit 300 --new tenders/lots/seen.json` · `portal.py meks --subject works,services --min 20000000 --new tenders/lots/seen-meks.json` |
| глубокий анализ лота | `lot.py get <номер | ссылка>` (Самрук: `--system samruk --uuid …`) → then the operation |
| проверить фирму | `firm.py check <БИН>` · `firm.py table <БИН> …` · `firm.py protocol <объявление>` · `firm.py history <БИН>` |
| финустойчивость | `finstab.py calc firms/<фирма>/finstab.csv --year 2026 --next [--lot <сумма> --kind works]` |
| доступ к порталу | `ows.py check` |

Selftests without network: `lot.py selftest` · `firm.py selftest` · `finstab.py selftest` · `ows.py selftest`.

Keys: `secrets/goszakup-token` (her portal key, tied to her machine's address), `secrets/kgd-token`
(when issued). PDF text needs `pdftotext` or `pip install pypdf`.

Known: the portal API sometimes answers 500 for a while — `lot.py` takes documents from the portal's
site without a key; МЭКС sometimes 502 — repeat.
