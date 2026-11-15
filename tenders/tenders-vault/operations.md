---
title: operations — registry of the tenders domain
type: registry
status: active
sensitivity: normal
scope: work
updated: 2026-11-15
related:
  - HOME
---

# Operations — tenders

The agent acts **by an operation, not from memory**. There is no operation until there is a line
here. Status `live` — only after a run on her live case.

| Operation | Trigger | Kind | Status |
|---|---|---|---|
| [[operations/chto-novogo\|что нового]] | «что нового», «есть новые конкурсы?» | read | possible |
| [[glubokiy-analiz-lota\|глубокий анализ лота]] | «глубокий анализ лота …», «разбери лот …» | read + write | possible |
| [[proverit-firmu\|проверить фирму]] | «проверь фирму <БИН>», «разбери протокол итогов» | read | possible |
| [[zavesti-kartochku-lota\|завести карточку лота]] | «запиши этот лот», «мы подали», «чем кончилось» | write | possible |
