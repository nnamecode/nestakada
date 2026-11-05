# Q033-STATIC-RESUME-002 — validation-only продолжение

Дата 2026-11-05. Статус: предложение, execution до ответа владельца запрещён.

Основание: владелец согласовал001 (D-562), однако единственная разрешённая001 static execution завершилась STATIC_REFUSAL INTERNAL_ERROR (exit1/stdout30B/stderr0), без freeze. Доказано ошибочное разрешение registry dependency от корня suite вместо real-host. Underlying exception не записан; ENOENT не выдаётся за факт. Это первая ошибка возобновлённой серии, повтор AGENTS не наступил. Новый ответ нужен из-за количественного лимита001, а не из-за новой архитектуры/ресурсов.

## Конкретное исправление

Все validation inputs находятся в work/dev29-bounded-20261105-resume008/:
- final-static-validator-correction002.mjs SHA256 0d9346698d04534aae7ff440c42300025d7bf1e74c71529e27780df771621bd7;
- static-correction002-launcher.cjs SHA256 7f6be24af596ca96aefc67f92dca415b47cfe65b4a8285b695070a516af5d38e;
- static-correction002-proof.json SHA256 f829d6b78e94bfc4b01b4d46188a793b33324d16ee9470189ba4d3cac0dc343f;
- static-correction002-syntax-summary.json SHA256 fbb5a14f75b03942e033f7baa536a1887b8d0d3ee92b4e84afeb8513c0064ec8.

Сохранённые001 evidence: static-resume001-syntax-summary.json c2e7f0aa76c619526b5166331f10d0ed72ecb3adf8dde3a23827eb71a86012b1; static-resume001-execute-refusal.json ffa6ecb8470ecf50ea7515d85fcc55faa655ada74255a78e33156e039f6b9dee.

Изменён только dependency-base (real-host) и закрытые phase enums диагностики. Expected byte comparisons не менялись. Syntax2 PASS по bounded capture. Source59 и220 distinct PASS неизменны. Нового static execution не было.

## Предлагаемый допуск

После независимого ревью исправления и ответа владельца разрешить довести только локальную статическую валидацию до результата, затем exact freeze и независимое whole-candidate code review. Количественный лимит «один static execution» из001 заменяется этим узким допуском на validation-only работу. Это не добавляет ни одного PG Run/Prepare/actual mode. Никаких автоматических повторов того же отказа: сначала факт, доказанная причина и изменённое условие. При повторе эквивалентной ошибки — немедленный STOP по AGENTS и решение владельца; не делать третью однотипную попытку. Не запускать заново прошедшие220 тестов без изменения соответствующего source.

Сохраняются ВСЕ ограничения001: canonical24 + legacy22 =union30, exact pinned parent/checkpoint maps, все ancestry/identity/dependency/exactpatch checks; registry59 неизменен. Нельзя менять source59/expected/guard ради PASS. Все syntax checks/checker/launcher через bounded external capture, project import failures закрыты, stdout/stderr/source/stack не транслировать. Raw single-file fragment≤800/wholeoutput≤1000. Все публичные validation evidence сохранять/readback/hash отдельно от runtime registry. При непредвиденном требовании изменить source59 — остановить этот план и предъявить причину.

После static PASS/freeze — НОВОЕ независимое fullcandidate CODE review; только после него прежние допуски и gates Q033. Ранее разрешённый единственный PG INIT/C/T остаётся ещё не начатым; ресурсы/таймеры/runner не меняются. Старые partial files сохраняются. Docker/SQL сейчас0, старый сайт/VPS исключены.

## Приёмка

SR33-06: corrected dependency paths относительно real-host; byte comparisons/expected unchanged.
SR33-07: закрытая phase диагностика и bounded syntax output; отсутствие runtime вызовов.
SR33-08: все static checks PASS по факту до freeze, metadata evidence pinned; independent fullcode gate не подменён этим review.

## Активная ревизия correction003 после независимого review

Correction002 не допускается к запуску: independent interim review docs/dev29-q033-static-resume-002-review.md SHA256 2e3278907a4d508a85d3c06f525a0cff7cebc7f2ec7f9090730ff0d3465ece6c установил два SR33-07 blocker (phase/code терялись; regex не finite whitelist). Старые002 файлы сохраняются только как история. Новый execution может использовать ТОЛЬКО следующую003 после independent approval:

- final-static-validator-correction003.mjs SHA256 905c153bca29915167f5afeb87c825a34f898ec8a4df318525b1a4b542b034fb;
- static-correction003-launcher.cjs SHA256 f7c90f832b445b96e0ff927db8b82672db62e6f5a04105ad85391aca08310c83;
- static-correction003-proof.json SHA256 dd8f4617556dcad07661b54b1f4bc9ecadeafccf08b3c9ce85dc0cfb4c183d7e;
- static-correction003-parser-test.cjs SHA256 7542a9a26b3255ca0be70765eb9152181e6a66b171a3005931fd6037e764416c;
- static-correction003-syntax-summary.json SHA256 f4694923e3868456b67b5c58696a4f284fd12ba13e1943fe462d90de1a04a95e;
- static-correction003-parser-summary.json SHA256 42fb4c5ef19fbd13cc174f2e5b531a01dc49c25975812062d54a052544990482.

Пути относительно той же resume008. Syntax3 PASS, isolated parser8 PASS по отчёту исполнителя: только synthetic inputs, без validator/native/packageFiles. Это проверки validation harness, они не добавляются к220 product tests. Статический запуск003 ещё0, freeze отсутствует, source59 unchanged. Strict finite whitelist code/phase; parser сохраняет только распознанные closed enums. Неизвестные/malformed/oversized/extra text → UNKNOWN/UNKNOWN/INVALID_RESPONSE без raw output. Ожидается независимое review003 с закрытием обоих findings; затем ответ владельца по002.
