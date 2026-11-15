# tenders — large tenders: works and services (domain door)

The room of Маржан's main work: large competitions in Kazakhstan for **works and services** —
finding them, analysing a lot to a verdict, keeping what was learned about customers and
competitors. The side is the supplier. The agent is the same as everywhere (`../CLAUDE.md`); this
door is the map of the room.

> **Invariant (verbatim, as in every door):** NEVER `AskUserQuestion` /
> popup dialogs — questions to the owner in plain text. Discuss first, write
> after the word: «do X» is an order, «maybe / probably» is thinking aloud.
> Nothing leaves without the owner's word.

## Answers

- «Что нового?» — new competitions over 20 million ₸, works and services, acceptance open, on
  госзакуп, Самрук, Mitwork, МЭКС → [[tenders/tenders-vault/operations/chto-novogo|что нового]].
- «Глубокий анализ лота <номер>» — the whole run, documents into the lot's folder, verdict →
  [[glubokiy-analiz-lota]].
- «Кто это такие?», «сколько у них договоров в этом году?», «были в недобросовестных?», «разбери
  протокол итогов» → [[proverit-firmu]].
- «Запиши этот лот», «мы подали», «чем кончилось» → [[zavesti-kartochku-lota]].

## What is here

- `tenders-vault/` — knowledge: start — `HOME.md`, state — `status.md`, questions —
  `questions-MARZHAN.md`, operations — `operations.md`, the rules of procurement — `rules/`, how to
  read each platform — `tools/`.
- `lots/<year>/<platform>-<announcement>/` — a lot as a folder (`lot.py` builds it): `docs/` with
  the platform's files and their text (outside git), `сводка.md`, `history.csv`, `анализ.md`; the
  card `lots/<year>/<platform>-<announcement>.md` beside it. Description — `tenders-vault/lots.md`.
- `planning/` — the domain's `backlog.md`.
- `docs/` · `inbox/` — other tender files (outside git). Description — `tenders-vault/docs.md`.

## Rules

- **The order of an analysis is hard:** admission (the method of procurement) → requirements from
  the documentation → can her firm pass → only then prices and competitors.
- **Platforms are kept apart** — a lot says where it is from; lists are not merged without a column
  «площадка».
- **«From one source by failed procurements»** — the supplier is already invited; not analysed, shown
  apart.
- **Filing is hers.** The agent brings a lot to a verdict and stops at `⏸ owner`.
- **An empty field is not zero** — not taken means not looked at, and is written so.
- Sums in tenge (₸); Самрук's sums are without VAT — said every time.
- Secrets — only `../secrets/`; files hold pointers.

## Links

- The top: `../CLAUDE.md`, `../meta-vault/HOME.md`. A blocker that gates the top — a line in
  `../planning/plan.md` §Caution.
- Her firms — `../firms/` (read, never write from here).
- Session close — `../CLAUDE.md` §Session close.
