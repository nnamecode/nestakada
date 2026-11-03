# DEV-15: независимое ревью локального допуска

2026-11-02, D-380/D-389, AD15-001–008. DEV-15 около 96%, этап 8 около 28%.

## Итог D-390 — APPROVED для первого операторского перехода

Независимый рецензент принял фактические Prepare 80ec2fda → Activate da1018a2 → Retry 52978298. Проверены 9 двухкадровых raw helper outputs, 27 HMAC/связей и 6 архивных raw/v2 proof с прежними OID16387/32563. Одна policy/Head10/epoch2; Activate replay:false, Retry replay:true, внутренняя квитанция одна и retry.before==after. Независимо совпали формула Head digest, полный legacy digest и итоговый state-v2 `60e067e7a8efa143a2d21e3ee31b7bc42e5fc85c34560a53bb3e3b98554c0bc1`.

Сверены все 63 входа, полный состав 30 host/frozen Python-файлов и конфигурации без drift. Максимум завершённого helper среди всех девяти — 150953984 байта/OOM0; ACL395/790 owner/SYSTEM, контейнеров0, manifest inactive, disabled/permit пустой. Предыдущие FAIL сохранены. Итоговый текст результатов проверен и корректен. Это приёмка policy transition, не run lease/HTTP-записи/native RP15-013–019; весь DEV-15 остаётся в работе. Никакой переход к APP/DEV-29/production не разрешён этим результатом. Рецензент файлов не менял и Docker не запускал.

## Возобновление D-390

Владелец снял паузу DEV15-AD-RESUME-001. Именованный preflight подтвердил 193 сохранённые SHA и закрытую запись. Независимый code-gate принят для одного исправленного Prepare: controller `5ba972d21ad1f05347a1a57f1eea86e95fce180adc73bf4620e95dde518f12d4`, guard-test `86380e819df90c2264bbb51e2ba76cdb7025cd2e0b088ec099416def756269cb`; Python operator остаётся `ee36f319b737e0116629217721b018c9d0d841c33a5d0674aaf9eb26e983fcbc`.

Подтверждены полные Docker ID и ownership, отсутствие повторного archiveProof после раннего отказа, отдельный однократный close-only после возможной catalog-мутации, сохранение FAIL и отсутствие повторного отказавшего reap. Сбой записи диагностик не мешает остановить доказанный собственный helper, но не допускает итогового PASS. Фактические 13 VM-проверок и AST четырёх встроенных Python-команд приняты по точным SHA. VM использует подставной Docker без процессов/БД/приватных файлов и не заменяет SQL-сохранность Prepare. Числа в полных именах 13 VM-кейсов — их внутренний порядок; покрытие групп ADG15-001–005 определяется проверяемой границей, а не одним числовым префиксом.

Старый code-gate и два FAIL сохранены. Lease/native не входят в этот gate; реальный Prepare и его result-review фиксируются отдельно. Ниже история предыдущих ревью и исправлений.

Независимое result-review Prepare 80ec2fda — **APPROVED**. Проверены HMAC attempt/prepared-state/intent/трёх pre-send, raw helper outputs, ссылки evidence и точные Head9/epoch2/full-v2/policy0/legacy seal/config/source/schema/CAPS. Оба архивных proof совпали, source/63 inputs без drift, контейнеров0, activation NOT_SENT. ACLPrepared321/642 подтверждены отдельно координатором.

На неизменённых controller 5ba972d2… / Python ee36f319… принято code-review следующих **Activate и точного Retry** по D-380/D-389/D-390: только сохранённый intent, без нового UUID/подгонки expected. После подтверждённого commit ожидаются один policy row, Head10 и exact replay без второго advance. Результаты этих фаз подлежат отдельному итоговому review; lease/HTTP-запись/native этим не допускаются.

План первого инкремента AD15-001–005/008 принят независимым рецензентом: политический переход без run lease и HTTP-записи соответствует согласованному порядку. Обязательны сохранность исходных 63 provenance-входов и отдельная проверка разрешённого Head/policy delta после commit вместо старого MAIN verifier, ожидающего Head9/policy0.

## Замечания до запуска

| ID | Требование | Изменение |
| --- | --- | --- |
| AD-ROOT-001 | Принадлежность ресурсов до первого обращения | До DB start проверяются существующий том/сети; после создания — фактический том БД, сети, mounts и лимиты. Чужой одноимённый ресурс нельзя сначала запустить, затем отвергнуть по OID. |
| AD-ROOT-002 | Очистка частично выполненного запуска | Намерение cleanup фиксируется до compose up, чтобы его ошибка/таймаут не оставили собственную БД вне finally. |
| AD-ROOT-003 | Сохранный повтор после UNKNOWN | Attempts/reports/receipts имеют уникальные runId; сохранённый intent остаётся прежним. Повтор Inspect/Retry не блокируется одноразовым именем отчёта. |
| AD-REV-001 | Exact Retry может впервые закоммитить | После UNKNOWN повтор того же intent принимает доказанный первый commit с replay:false либо прежний receipt с replay:true. В проверке после известного commit отдельно требуется replay:true и отсутствие следующего Head advance. |
| AD-REV-002 | Закрытие архивов после аварии helper | Cleanup обязан охватывать оба известных name/OID, даже если предыдущее прерывание оставило ALLOW_CONNECTIONS true и текущий read loop не начался. Исходная проверка closed не ослабляется; ошибка остаётся FAIL. Чужие сессии не завершаются. |

Операторские инструменты проходят отдельный code-gate по точным SHA до запуска. Фактические результаты Inspect/Prepare/Activate/Retry, сохранности и итоговое result-review дополняются после выполнения; этот документ заранее не объявляет их PASS.

Code-gate принят для Node 0eea877a…/Python ee36f319…, затем узкая independently reviewed правка config tools-profile принята для Node 220befbc…; Python неизменён. Actual Prepare выявил ещё runtime-дефект короткого/полного Docker ID и его повтор в finally. Это не пройденное result-review: работа приостановлена владельцу по DEV15-AD-RESUME-001, новый фикс ещё не реализован. Факты и ограничения — dev15-local-admission-results.md. Старые gate/FAIL сохраняются.

## Код будущих native-проверок

Отдельно принят ограниченный `tools/trust_runtime_fault_probe.py`, SHA `2fa27d057f983750e69336458f613daf26219d4c14776a2148484bf3580e456b`. Исправлено явное закрытие HTTPResponse до SQL-наблюдения, включая Connection: close. Секреты/тела не выводятся; проверяются fixed TLS/SQL identity, intent hash, фазовый advance и private response headers. Partial case свидетельствует о клиентской неполной отправке и конечном окне неизменности; серверная граница и injection этим не доказаны. Host ещё обязан проверить exact replay и остальные строки. Синтаксис Python проверен в прежнем изолированном образе. Исполнение и полный PASS RP15-013–015 не заявляются.
