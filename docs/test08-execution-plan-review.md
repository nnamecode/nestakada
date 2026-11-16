# TEST-08 exact10 execution plan — independent review

Дата: 2026-11-15. First verdict: **CHANGES_REQUESTED**,
P1/P2/P3=`2/4/1`. Reviewer read-only; files/tests/Docker/Playwright/network0.

## Findings и remediation

1. **P1 lifecycle:** один test method не мог напечатать честный post-teardown
   `fixtureAfter==0`. Исправлено на два фиксированно упорядоченных метода по
   существующему fixture pattern; marker печатает только второй, manual flush0.
2. **P1 audit detail:** product имеет только `/manage/audit/`. Несуществующий
   detail удалён, новый endpoint запрещён.
3. **P2 group evidence:** group object расширен closed actor/path,
   expected/actual, before/after и fixtureRunId contract.
4. **P2 independent oracle:** actual-only SHA и DB-as-expected удалены. План
   закрепляет SHA approved route/media registries и exact12 package descriptors,
   строит immutable expected projection до DB writes и фиксирует exact baseline.
5. **P2 reserve capacity:** предположение `/tmp`256MiB удалено. Proposed suite
   сохраняет `/tmp`128MiB и получает отдельный `/test08-reserve`544MiB для двух
   hard-capped256MiB generations; actual/peak bytes сохраняются.
6. **P2 hidden tree:** owner real publication confirmation временно скрывает
   один exact leaf, проверяет blank/noindex/nav exclusion и возвращает before.
7. **P3 PII/network wording:** real PII уточнено как реальные клиентские данные,
   публичные реквизиты не смешиваются; недоказуемый network-attempt counter
   заменён существующим `externalDelivery=0` без interceptor/framework.

Общая no-bloat граница остаётся exact fixture+execution test+wrapper; product
endpoint/model/migration/dependency/template/JS/framework0.

## Следующий gate

Независимый repeat review проверяет только закрытие семи findings и отсутствие
нового противоречия. До final `APPROVED` implementation/run запрещены.

## Repeat review и anti-loop stop

Repeat verdict: **CHANGES_REQUESTED**, P1/P2/P3=`0/2/0`.

Закрыты lifecycle, audit-list, per-group evidence, exact14 pinned inputs и
independent expected oracle, real hide/republish. Остались:

1. **P2 reserve resource bound:** верх плана сохранил stale `/tmp256`, а
   `/test08-reserve`544MiB + media оставляют около181MiB, не заявленные >200MiB.
   Главное: второй build одновременно держит previous на storage, новый payload
   в Python и записываемую generation; two-generation disk cap не доказывает
   peak memory768MiB.
2. **P2 G08 wording:** сценарий сохранил старые `real PII`/`transport attempts0`,
   тогда как receipt уже использует client/application PII rows0 и
   externalDelivery0.

Это второе эквивалентное обнаружение тех же resource/wording gaps после
remediation. Третьей попытки нет; задача **ПРИОСТАНОВЛЕНА ВЛАДЕЛЬЦУ**. Tests,
Docker, network, product files0. Рекомендуемое изменившееся условие для resume:
disk-backed validated per-run reserve bind с `finally` cleanup вместо tmpfs,
отдельный bounded test-only memory cap с учётом одного in-memory generation и
единый G08 oracle. После owner resume — одна документационная remediation и
один final review.

## Owner resume и changed-condition remediation

Владелец разрешил «Почини и Продолжай». Рекомендованное изменившееся условие
применено документально:

- stale `/tmp256` и reserve tmpfs удалены; exact validated per-run host directory
  bind-mount RW, free-space gate1GiB, storage/host cap544MiB и `finally` cleanup;
- только named suite получает memory/swap1536MiB. Worst admitted accounting
  включает reserve page cache544MiB, один Python generation payload256MiB и
  fixture-media45,221,681B, оставляя >690MiB process headroom;
- G08 в scenarios/evidence/bounds использует один contract:
  client/application PII rows0, external delivery0, public company details
  разрешены, network-attempt counter отсутствует.

Product endpoint/model/dependency/framework0; code/tests/Docker/network0.
Следующий и единственный gate — final independent review этих двух P2.

Final review закрыл reserve P2 и вернул один G08 P2: одна старая evidence-строка
ещё запрещала любые реальные email/имена/телефоны. Точечная remediation заменяет
её тем же единым contract: client/application PII rows0, external delivery0,
public company details allowed, private owner recipient not serialized,
network-attempt counter absent. Другие строки/границы не меняются. Следующий
gate — final confirmation этого единственного finding; при эквивалентном повторе
работа снова останавливается без третьей попытки.

## Final confirmation

Verdict: **APPROVED**, P1/P2/P3=`0/0/0`.

G08 scenarios/evidence/marker/bounds используют один contract; public company
details разрешены, private recipient не сериализуется, client/application PII
rows0, externalDelivery0, attempt counter отсутствует. Resource P2 остаётся
закрыт validated disk-backed per-run bind, free1GiB, host cap544MiB, `finally`
cleanup и suite-only memory/swap1536MiB с корректным worst-case accounting.
No-bloat regression0. Reviewer files/tests/Docker/network0.

План утверждён. Следующий gate — отдельное разрешение владельца на exact
three-file implementation и один named wrapper run; approval плана само по себе
не разрешает код или запуск.
