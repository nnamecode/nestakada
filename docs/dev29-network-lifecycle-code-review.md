# DEV29-Q024: подготовка и независимое ревью инструмента

2026-11-04. Владелец разрешил DEV29-Q024 (D-474). Native запуск пока не допущен.

## Первый замороженный пакет

План SHA256 4679a968106b0ee2193a74d343893eb67c5351071a654c12864f7f89811ac085. Изолированный namespace work/dev29-network-qualification-20261104-001/ содержит 5 файлов, 49600 байт. Package SHA256 67c31e66d9ca02135190f7c1cd2f7db67a1cc19224505d6f7b59686188858b43; raw manifest e094eeb98c3e9b7d95d8ab358c64b361a4ddc3f06513c0645111b2efd1cdb566.

- spec.mjs: 9dfaae02eb5224037cddc375336ec33be95627e239fb19d4f1d2c7b8cc0e75ca.
- qualify.mjs: 0a416bc27207b842ed1c31be9df6d4b0e5ffbf2136beabfbf5d08e3581715e07.
- qualification-test.mjs: d2e1263a350f79bae52528359c59340723baa5cd2e633bbdce6ff5f4b2eb978a.
- test-summary.json: 7e8755afd3c632e08439159f6bed1130dc6ec6fce4aebecf30e1f4780e9ec757.

Исполнитель сообщил syntax3 PASS и mocked24 PASS/0fail/skip; raw child/native/Docker0. Координатор отдельно сверил все source hashes с manifest и размер. Это ещё не квалификация engine или OS termination. Общий RawBudget ограничивает управляемые raw buffers и явные временные копии, а не весь Node RSS.

На предварительном просмотре координатор нашёл report bindings до manifest gate (null source/package) и отдельный CAP вместо общего для concurrent capture. Исполнитель исправил их до freeze и добавил проверки.

## Независимое ревью

Пакет передан /root/dev29_publication_review. Статус: выполняется; APPROVED пока нет. Рецензент проверяет точные hashes, AC01–06, реальный productionIO/capture, deadlines, cancellation/uncertain create, exact ownership/cleanup, once/source pins и privacy. Допущены только source чтение, node --check и injected qualification-test; qualify Run запрещён до завершения review. Старые пакеты/guard/корпус/ключи не изменяются.

## Итог первого code review

Независимый рецензент: **CHANGES REQUIRED** для package67c31e66…858b43. Все5 SHA совпали, независимо syntax3/3 и mocks24/24 PASS. Два P1 не покрыты исходными тестами:

- NETQUAL-PKG-REV-001: исключение decode/validation после dispatched CREATE и до доказанного ID должно ставить uncertainty; иначе recovery может пропустить созданный ресурс. Исправить весь post-dispatch boundary, negative test и ровно один recovery, без продолжения work.
- NETQUAL-PKG-REV-002: после финального decode/snapshot/finishStream не проверялись фазовые deadlines. Добавить post-processing gates и negatives readiness90/work85/cleanup30; overrun не может быть PASS при total<210.

Одна первая инструментальная ошибка рецензента ENOENT возникла из-за предположенного manifest.json. После actual rg --files подтверждено package-manifest.json, hash check PASS; эквивалентного повтора не было. Native0.

Исполнитель получил ограниченное исправление двух findings с сохранением прежнего source checkpoint, синтаксическими проверками, затем mocks и новым freeze. Повторное code review обязательно до native.

## Второй замороженный пакет

Исполнитель исправил NETQUAL-PKG-REV-001/002; исходные5 файлов сохранены побайтно в work/dev29-network-qualification-20261104-001-review-checkpoint-001/ с checkpoint.json. Сохранённые byte hashes проверены. Новый namespace54972 байта. PackageSHA bf1ddf1a0b0912b5c494e484517e53f098c67771be2d468a9e71d6e07cb96423; manifestSHA c7ee73a8e170a686da7478703f7d44b72b93ffd0e2f6405b3eafe6eaaca00f19; qualifySHA497469fcb5f288772af78fda0b957fb986f23167daab39718c252acd75a05d86; testsSHA4d50fb59c6d87f33ebc2e3b96408e7dac855f7d87a8df8ca87b734fb4d9ddf37; spec без изменений; summarySHA349c8a7e95c3a462094c1ae3829d2fe6e873ce17c65c135dcc6aff16fec80140.

Syntax3 PASS затем mocks31 PASS/0fail/skip; добавлены7 targeted cases для post-dispatch decode/release и финальных readiness/work/cleanup boundaries. Native/actual child0. Повторное независимое ревью выполняется; approval пока нет.

## Повторное независимое ревью и dispatch

**CODE APPROVED** /root/dev29_publication_review на exact package bf1ddf1a0b0912b5c494e484517e53f098c67771be2d468a9e71d6e07cb96423. REV001/002 CLOSED; рецензент самостоятельно проверил все5 SHA, syntax3/3 и mocks31/31 PASS, новых findings/инструментальных ошибок нет. Это не runtime квалификация.

Координатор по уже принятому D-474 допускает максимум один conditional native dispatch Q024 на этом frozen пакете: plan/hash/source/review/once проверены, approved-review.json создан wx. Далее instrument самостоятельно заново проверяет pins, доступ, размер, ready engine/image/no-owned-conflict до ресурсов, а финальный отчёт требует отдельного независимого ревью. PG/SQL/guard/старый сайт/VPS вне допуска.
