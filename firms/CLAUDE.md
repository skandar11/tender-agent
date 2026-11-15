# firms — her firms as tender participants (domain door)

The room of Маржан's firms as participants of tenders: what each firm can take on — licences and
categories, experience of similar works, staff and equipment, figures from 1С and financial
stability. The agent is the same as everywhere (`../CLAUDE.md`); this door is the map of the room.

> **Invariant (verbatim, as in every door):** NEVER `AskUserQuestion` /
> popup dialogs — questions to the owner in plain text. Discuss first, write
> after the word: «do X» is an order, «maybe / probably» is thinking aloud.
> Nothing leaves without the owner's word.

## Answers

- «На какую сумму лота мы проходим?», «посчитай финустойчивость», «пройдём ли на лот <сумма>?» →
  [[poschitat-finustoychivost]].
- «Какие лицензии у <фирма>?», «есть ли опыт таких работ?» → the firm's card.

## What is here

- `firms-vault/` — knowledge: start — `HOME.md`, state — `status.md`, questions —
  `questions-MARZHAN.md`, operations — `operations.md`.
- `<firm>/` — a folder per firm: the card `<firm>.md`, the figures for financial stability
  `finstab*.csv` (from 1С or tax forms), `docs/` — licences, certificates, 1С exports, statements
  (outside git). Description — `firms-vault/cards.md`.
- `planning/` — the domain's `backlog.md`.

## Rules

- **Figures with their source and date.** «From 1С, export of <date>» or «from the calculation of
  10.11» — never a bare number.
- **Personal data not in markdown**: IIN, document and account numbers live only in the scans in
  `docs/`; cards hold pointers.
- **A firm's cabinet** on the portal — read only from that firm's Chrome profile and only on her
  request ([[../meta-vault/owner|owner]] §Browser).
- Secrets — only `../secrets/`.

## Links

- The top: `../CLAUDE.md`. Tenders read from here (`../tenders/`); this domain does not write there.
- Session close — `../CLAUDE.md` §Session close.
