# KEYPG-TEST-RESUME-001 — предложение ограниченного возобновления Q031

Статус: ПРЕДЛОЖЕНИЕ, требуется независимое ревью и явный ответ владельца. До ответа код и тесты остаются остановленными.

Причина: affected review suite дважды завершился 24 PASS / 1 FAIL, один case R026-AC06 production wiring, expected true / actual false. После первой ошибки мигрировано ожидание owner D493 к строгому D528/Q031 и добавлены CLI dispatch branches; второй запуск выявил ещё не установленный assertion того же case. Исполнитель остановлен без третьей попытки. Последний checkpoint: changed syntax4 PASS, focused23 PASS, stage19 PASS. Host/stageguard/existing dependents не запускались. Private/Prepare/native 0, freeze/code approval нет.

Основание STOP: AGENTS.md — «повтор той же ошибки второй раз при эквивалентном действии без нового свидетельства или изменившегося условия», «Не делать третью однотипную попытку» и «Возобновлять только по решению владельца».

## Конкретный порядок после разрешения

1. Один известный публичный saved TAP: work/dev29-bounded-20261104-resume007/real-host/review-test.mjs.current-failure.tap. Прочитать ограниченный raw-фрагмент со stack/line/assertion, raw≤800 и precheck полного вывода≤1000. Если путь отсутствует — обычный NAV_NOT_FOUND без бесконечных повторов; до точного наличия отчёта новый test run запрещён.
2. Прочитать соответствующий raw-фрагмент известного review-test.mjs, затем только точно названный production source. Установить точный failing assertion; никаких индексов/JSON crop/широкого поиска или слепого повтора suite. При отсутствии stack/line — один bounded raw next fragment; если точный assertion установить невозможно, честно остановиться без rerun.
3. Если отсутствует требуемое реальное wiring — исправить production code и добавить behavioral regression. Если доказано только устаревшее owner/run/plan binding — обновить строго этот binding, сохранив смысл assertion и отрицательные проверки. Не заменять результат на true, не удалять assertion/skip, не ослаблять integrity/review/NOAUTH/direct delivery/readonly/cleanup. Эквивалентный bypass keyState.verify Original-after остаётся запрещённым после automatic approval rejection.
4. После конкретной правки последовательно: changed syntax → focused → stage → affected review. Зависимый шаг запускать только после PASS предыдущего. При первом новом реальном отказе сообщить причину и новое свидетельство; второе эквивалентное действие с тем же отказом — STOP/no3 по AGENTS. Новая серия не является разрешением бесконечно исправлять симптомы.
5. Лишь после PASS affected review продолжить host/stageguard/existing offline, затем freeze exact public package и независимое code review. FS writes/child-launch harness — штатный require_escalated, ACL не менять; auto-review denial не обходить.

Это возобновление того же разрешённого Q031, не новая архитектура и не дополнительный native Run. Final plan df2c00f148f581c6f4113ccfe2febf4c76d385bfd2e36ccca87b3c44be184311, Prepare-time private HMAC tag32B и полный verify, прежние лимиты и шесть actual gates сохраняются. Репетиция/Prepare/native допускаются лишь после всех прежних PASS/review gates; единственный условный Run Q031 пока не использован. Корпус, оригиналы, прежние checkpoints, секреты, старый сайт и VPS не изменять. Исполнитель — q025_builder; независимый code/result reviewer — q026_result_auditor. Координатор ведёт документацию.
