# REBUILD-2: clean Django skeleton plan

Дата: 2026-11-17. Plan ID: `RB2-SKELETON-001`.

Статус: **APPROVED D-1417, P1/P2/P3=0/0/0; version acknowledgement required; product code not started**.

## 1. Цель и граница

Создать новый изолированный `src/` для «Эстакады» с composition root и первыми реальными модулями `audit`, `accounts`, `pages`. Старый `app/` остаётся неизменным и не импортируется. REBUILD-2 не создаёт пустые/placeholder `media`, `gallery`, `requests`, `integrations`, `themes`, `kernel`, `common`, `base`, `utils` или общий service/repository слой: каталог появляется только вместе с первой реальной ответственностью.

В scope входят:

- `src/manage.py`, `src/config/settings/`, `src/config/urls.py`, `src/config/wiring.py` как маленький composition root;
- `src/modules/audit`: `ActorRef`, exact AuditEvent v1 schema/matrix из architecture §7.7 и публичный append API без FK/import к accounts;
- `src/modules/accounts`: custom staff `User` с UUID PK, exact role enum `OWNER|EMPLOYEE`, active flag и monotonic session generation; стандартные Django password/session primitives, без customer account, 2FA, email confirmation или CAPTCHA;
- `src/modules/pages`: `Page`, `Route`, `PageContent(current+previous+generation/provenance plus one bounded last-operation slot)`, `PageGrant`; exact constraints/FK lifecycle из архитектуры;
- одна static dependency fitness-проверка exact subset DAG `accounts→audit`, `pages→accounts,audit`; `config→modules`; private/reverse/cyclic/old-app imports0;
- migration source files и focused tests для созданных моделей/constraints, но **migration execution, PostgreSQL/Docker/runtime отсутствуют до отдельного gate**.

Весь `SiteSettings` singleton, включая `structure_generation`, `settings_generation` и READY `logo_asset` FK, откладывается до реального media module/API. Nullable UUID-заглушка, альтернативное поле tree generation и structural commands до SiteSettings запрещены. Media usages и команды, которым нужен настоящий media public API, также не получают stub. Public renderer/admin/editor/importer не входят в этот план.

## 2. Версии и зависимости — отдельный candidate

Рекомендуется без установки и без нового lock переиспользовать exact уже локально зафиксированный security stack:

- Python `3.14.10`;
- Django `5.2.18`;
- psycopg + psycopg-c `3.3.6`;
- django-csp `4.0`;
- только их текущие pinned transitives `asgiref 3.13.0`, `packaging 26.3`, `sqlparse 0.6.0`.

Authority candidate — существующий `environment/foundation/requirements.lock`; копирование lock в `src/`, загрузка wheel, установка, image build и network access сейчас запрещены. `nh3`, Pillow, Telegram client, task queue, cache, API framework, DI library и test framework не добавляются в REBUILD-2. `nh3` рассматривается только в фактическом content-validation slice, Pillow — только media boundary; для Telegram используется stdlib HTTPS adapter лишь на своём будущем этапе.

Версии требуют owner acknowledgement `RB2-VERS-Q001` после independent plan review. Если текущий lock не принимается, product code не начинается и новый dependency search/install автоматически не выполняется.

## 3. Структура без лишних слоёв

```text
src/
  manage.py
  config/
    __init__.py
    settings/
      __init__.py
      base.py
      test.py
    urls.py
    wiring.py
  modules/
    __init__.py
    audit/
      __init__.py
      apps.py
      models.py
      api.py
      migrations/
      tests/
    accounts/
      __init__.py
      apps.py
      models.py
      migrations/
      tests/
    pages/
      __init__.py
      apps.py
      models.py
      migrations/
      tests/
  fitness/
    test_dependencies.py
```

Файлы `commands.py`, `queries.py`, `policy.py`, `forms.py`, `views.py`, `urls.py` внутри модуля не создаются до первой реальной операции соответствующего типа. `wiring.py` содержит только фактическое composition wiring; пустой registry/service locator запрещён.

## 4. Приёмочные сценарии до кода

- `RB2-SKEL-AC-001`: новый source root exact `src/`; import/file reference из `src/` к старому `app/` отсутствует; old tree не меняется.
- `RB2-SKEL-AC-002`: присутствуют только config + audit/accounts/pages; placeholder packages/kernel/common/base/utils/repository/UoW/event bus/plugin registry0.
- `RB2-SKEL-AC-003`: static fitness принимает exact subset DAG и отклоняет private, reverse, cyclic, config-from-module и old-app import fixtures.
- `RB2-SKEL-AC-004`: settings используют custom User до первой migration; secret/database/config values не имеют unsafe source defaults, test settings не становятся production fallback; public URL surface пока только closed healthless root/404, без debug endpoints.
- `RB2-SKEL-AC-005`: `AuditEvent` реализует exact v1 architecture §7.7: UUID `id`, UTC `occurred_at`, closed `action`; `actor_kind=USER|SYSTEM|ANONYMOUS` with nullable UUID+OWNER|EMPLOYEE snapshot; closed target type/UUID/secondary UUID; canonical detail≤2,048 bytes/depth1/≤8 exact allowlisted keys. DB constraints plus one validator enforce the full closed action→actor/target/detail matrix and caps; forbidden raw exception/body/name/URL/credential/IP/path/Telegram/PII fields0. Model/API не импортируют accounts. Future module actions remain enum/matrix values only, not placeholder modules or implementations.
- `RB2-SKEL-AC-006`: DB enforces User UUID, role `OWNER|EMPLOYEE`, positive generation, role/username consistency (`OWNER→nesadmin`, employee cannot use it) and at-most-one active OWNER. Bootstrap and every owner-sensitive command must establish/recheck **exactly one** active OWNER under lock; row CHECK/partial unique are not claimed to prove existence. Standard Django auth remains; customer/email-verification/2FA/CAPTCHA fields0. Bootstrap/command implementation tests belong to their actual slices rather than a fake database constraint.
- `RB2-SKEL-AC-007`: Page parent/position/kind/publication and Route exact target/outcome constraints implement approved ownership; Page parent PROTECT, Route aggregate lifecycle and PRIMARY uniqueness fail closed.
- `RB2-SKEL-AC-008`: PageContent has exactly current+nullable previous, hashes/provenance, positive generation and one nullable all-or-none bounded slot `last_operation_id/action/result_generation/result_hash` with closed `SAVE|UNDO` action and coherent generation/hash. The slot supports immediate lost-response retry only; arbitrary history/drafts/stable/manual or receipt table0. DB constraints cover all-or-none slot/current-previous coherence expressible without duplicating the content validator.
- `RB2-SKEL-AC-009`: DB enforces PageGrant unique `(staff,page)`, PROTECT/CASCADE FK lifecycle and canonical sorted non-empty closed groups subset `{text,prices}`. Cross-table rules are service invariants: only active EMPLOYEE receives a grant, OWNER never needs one, and owner/grant-sensitive commands recheck actor/target role+active+generation under lock. PostgreSQL CHECK is not claimed to inspect User rows; command/concurrency tests are deferred to their actual command slice. Arbitrary fields/permissions JSON0.
- `RB2-SKEL-AC-010`: migration files are deterministic source artifacts for only these models; migration/runtime/database execution0 until separate approval.
- `RB2-SKEL-AC-011`: tests are focused on constraints/boundaries and dependency rules, not string copies; no external network/filesystem/media/Telegram/Docker.
- `RB2-SKEL-AC-012`: no-bloat diff proves new dependency0, placeholder0, compatibility wrapper0, second settings/config system0.

## 5. Предлагаемые slices

1. `RB2-IMP-001`: accepted version/dependency boundary + static source/DAG tests.
2. `RB2-IMP-002`: minimal config and exact AuditEvent v1 model/validator/append API.
3. `RB2-IMP-003`: accounts custom User, DB constraints and explicit service/bootstrap invariant boundary.
4. `RB2-IMP-004`: pages/route/current+previous+last-operation/grants schema; no SiteSettings/structural commands yet.
5. `RB2-IMP-005`: focused tests, migration-source review and whole-slice independent code review.

Каждый slice остаётся локальным source change. До отдельного runtime gate нельзя запускать Docker, PostgreSQL, migrations, Django test runner или устанавливать зависимости. Code review может потребовать исправления внутри утверждённой границы, но не добавляет module/framework/dependency.

## 6. Ворота

1. independent plan review;
2. owner acknowledgement exact versions/dependency reuse `RB2-VERS-Q001`;
3. product code slices по D-1363 внутри уже открытого code-only Q002;
4. independent code review;
5. отдельное owner/runtime gate для существующего pinned environment и migration/test execution;
6. никакой target/import/freeze/live authority не наследуется.
