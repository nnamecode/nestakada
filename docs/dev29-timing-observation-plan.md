# DEV29-Q034 — предложение только offline-интеграции телеметрии

Дата: 2026-11-05. Статус: предложение, не решение владельца. Реализация runner и новые runtime-действия этим документом не разрешены.

## Основание

Offline analysis docs/dev29-q033-timing-offline-results.md SHA256 f6c9a19734e0e06f8bc844f11d5c7d94569bc1fcbb7b82ded50834730f1dfaed и manifest work/dev29-q033-timing-offline-001/evidence-manifest.json SHA256 5154fb42ab2a956e59344806d3ce2daef541b1d3b14af1cb8a94933f93a695c6 уточняют старый terminal audit: 4182.4092ms — span adapter с pre/transport/post, не доказанное чистое время Docker. Post-image call-sum54841.2334ms почти исчерпывает55s; winning absolute deadline и распределение guard/native остаются UNPROVEN. Лимиты повышать на основании этих данных нельзя.

Конкретный design: docs/dev29-timing-observation-design.md SHA256 7e2b7fa4d0b8192dddddedd59e89cda46e7a6bb609aa084305cdca20a890053a. Все11 acceptance scenarios из design обязательны до реализации. Прежний Q033 package59 c281f40640f200c71e7ce084a3ded3885f49bb06728b373482c0f91ffdcbee44, его source/validation/operator и reports остаются неизменными.

## Что предлагается согласовать

Разрешить новую публичную source-only копию, observer-only интеграцию по указанному design, offline-проверки и независимое полное code review. Только существующие Node/Python инструменты и локальные публичные артефакты; новых зависимостей/служб/установок нет. До ответа владельца — только design/review, без изменения runner.

Область producer — только qualifyForPg/key qualification и её owned cleanup. Вызовы вне неё не покрываются; это не глобальный timing-proof всего Run. Native spans прикрепляются к тому же call record, без phase-event дублирования.

Observer фиксирует раздельные границы pre-verify, существующего boundDeadline, transport dispatch/completion и post-verify; native timeout записывается из фактически применённого значения. Сравнивать интервалы разрешено только при доказанном одном clock owner. Недостающие значения/победители минимума не восстанавливать догадкой; ties и неполноту обозначать явно.

Порядок/число guard checks, authority, HMAC, return/exception semantics, cancellation, native deadlines, budgets180/90/55/35/30 и все более строгие parents сохраняются. Никаких callback PASS, purpose-веток для обхода production guard, изменений точных8 bind mappings, прав/ACL или relaxed profile. Это локальная диагностическая телеметрия, не продуктовый раздел «Логи».

Буфер ограничен128 записями/64KiB encoded, только allowlisted labels/числа/флаги. Source-derived conservative bound:58 calls +10 noncall spans +4 snapshots =72 records. Предложенная finite schema даёт43,520B целого trace при неизменных65,536B; longest-path/encoder tests обязательны до подтверждения реализации, сейчас это design proof, не выполненные tests. Нельзя сохранять argv/env, пути/значения privateFacts, rawACL, ключи/теги/их content hashes, signing material или opinions. Observer не участвует в admission, не изменяет signed receipt/review schemas и не создаёт разрешений. Сбой/overflow помечает телеметрию UNPROVEN и не ломает исходные safety cleanup/исключения.

Выбранное сохранение: один bounded fixed-prefix NOAUTHORITY trace через уже открытый stdout после существующих terminal attempts/возврата Run, перед неизменным финальным CLI JSON. Внутри lifecycle нет нового FD/FS flush; per-call observer не пишет stdout. Существующая capture обвязка сохраняет/дренирует поток и подавляет trace в model output; offline extractor позднее делает sidecar. Wire protocol и quota1MiB/stream должны проверяться отдельно, без скрытого увеличения лимитов.

## Порядок после ответа владельца

1. Проверить исходные pins, создать только новую public allowlist копию; новый namespace назначить один раз после согласования. Ни private inputs/receipts, ни operational outputs/старыe machine opinions не копировать как authority. Никаких private/stage directories.
2. Новый runtime authority doc path остаётся отсутствующим: этот этап не создаёт KEYPG-CODE-REVIEW APPROVED marker, Prepared state или machine qualification. Прежний Q033 grant израсходован.
3. Реализовать только описанные observer seams/collector/offline extractor. Все11 сценариев design: equivalence порядка/returns/исключений; pre/native/post failures; deadline clips/ties/clock separation; overflow/emitter failure; privacy/schema; existing CLI/capture совместимость. Offline fake IO обязателен: никакого реального production Prepare/Run или signing oracle.
4. Последовательно syntax → новые behavior/boundary tests → релевантные affected suites → static equivalence/delta/dependency proof → exact source freeze. Зависимые шаги только после PASS предыдущего; прежние результаты переиспользовать только с доказанной неизменной closure, не объявлять старые220 результатом нового source. Все child launches только allowlisted Node/Python offline, через штатные права; реальные Docker/PowerShell/PG/SQL не вызываются.
5. Независимое whole-candidate code review, публичный отчёт без runtime activation. На первой реальной ошибке — причина и новое условие; при второй эквивалентной — STOP по AGENTS, без третьей попытки. Штатные CAP/NAV_NOT_FOUND до вывода/чтения не считать автоматически ошибкой.

## Граница результата

Q034 не разрешает Docker/native probes, helper/network/volume/container создание, ACL изменений, чтение настоящих key/tag/privateFacts, Rehearsal/Prepare/Inspect/Readiness/Cancel/Run или PG/SQL. Полный native dummy guard пока UNSUPPORTED: его injectable boundary и весь профиль не доказаны. Нельзя выдавать fake guard за production equivalence. После offline review для любого будущего runtime нужен отдельный конкретный план и решение владельца. Публикация, старый сайт и VPS исключены.
