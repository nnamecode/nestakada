# DEV-15: ревью учёта прежних записей

2026-11-02, D-386, LG15-001–006/RP15-008. DEV-15 около95%, этап8 около28%.

План принят для подготовки кода без новых архитектурных согласований. ОтдельныеPythonhelper получили APPROVED: export `cb66d9ef38dee4e932e75a7c69f148b7d10dcd7bc200cc92fa7cc106fb797b85`; probe `567462df0923b8076d06fac7fa261c7ad1be5bbcf236b8d62bb7af9b55026cfe`. Реальнаяnetwork-noneAST проверка подтвердила непустые16/20top-levelnodes и обаSHA.

Рецензент проверил readonlyMAIN/OID16384/v2/schema, настоящиеpayloadrefs, actualUNIT52766/роль/marker/config, импорт7journalмоделей безmigrations, реальныеB/Sподписи/caps/counts,995syntheticfixtures с другимиceilings ниже лимитов, триrollbackветки/completion/replayepoch2 и неизменностьlegacyepoch1. Проверкаseq/rawвсех8таблиц вprobe использует новое соединение.

Первый controllerSHA c66894f9… получил один блокер LG-REV-001: при kill/отсутствииprobeJSON недостаточно внутреннегоraw и архивнойchain, которая дляUNIT проверяетлишьidentity. Требуется независимый bootstrapreadonly UNITraw/sequence до/после scopedreap, также приFAIL, hashbefore связан сintent. Остальнаячастьcreate/actualID/privateARG/HMAC/ownedcaps/no-overlap/MAINarchivefinal дополнительных блокеров не получила. Точный старыйcontroller сохранён сSHA передисправлением; runtimeещё не запускался.

Codegate не означает фактическийPASS. Продукт/source30/014efc…, MAIN, архивы, старыйсайт/VPS и рабочийwriter не изменены.

Узкий повторный controller-review положительный: SHA `e6211911d00ea2fa7892b5888cf1392139a4c863887cb88184108568bc2656de`, обаPythonhelper прежние. LG-REV-001 закрыт: независимыйreadonlyaudit доprobe и послеreap вfinally, включаяFAIL, проверяет all8raw/sequence/actualOID/marker/empty+3migrations; baselineSHA связан с signedintent. UNITpreserved выводится из внешнего сравнения, self-report остаётся отдельным. Неизмеримость/различие даютFAIL. **APPROVED** для одного LG-прогона; source продукта неизменён, итоговый runtimeещё предстоит.

Фактический originalhostFAIL/exit2, несмотрянаsemantic3groupsPASS82.235451с и сохранность. Рецензент проверилточнуюпричину поConfig.Cmd/stderr: Compose заменил shell-переменные пустымистроками после выполненияprobe/post. Бизнесassertions по этой причине не отклоняются, но общийFAIL не переименовывается.

Узкий wrapperfix9030bcd8… принят: literalcallback удваивает`$` только вComposeJSON, actualCmdguard доintent/start. Дваnetwork-nonesmoke0/7 сactualComposecreate/start/logs/inspect приняты: точныйexit/postframe/command/limits, mounts0/OOM0. Полный82сLGповтор не нужен; end-to-endcontroller послеfixNOTRUN.

Итоговый составной result-gate RP008 положительный: semanticPASS/max+next/UNKNOWN/final/replay/3branchrollback; preservationPASS/HMAC/actualID/privateARG/independent8raw+sequence/MAIN+архивы/source/schema; wrapper smokePASS. OriginalFAIL SHA961a38…6b3ae иsmokeSHA21dc96…6da1 сохранены. PS5.1ACL283/566/0owned+smoke/inactive/disabled/permit{} подтверждены. Рецензент ничегонеисполнял/неменял. DEV-15 около96%, этап8 около28%; manifests/MAINactivation/native/DEV-29 ещё не выполнены.
