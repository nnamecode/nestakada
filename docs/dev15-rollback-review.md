# DEV-15: независимое ревью UNIT rollback

2026-11-03, D-398. Независимые plan/code/result-review — **APPROVED в ограниченной UNIT rollback области**. Рецензент `/root/tls_review` не редактировал исходные артефакты и не повторял native/SQL/Docker. Сверены8late-DMLветвей, actual22012/ENOSPCinjection, rollback/retry/replay, HMAC/input/output/CID/resources7helpers, UNIT/MAIN/архивы/source30/config24/EV63/ACL; полный nativeShutdown подтверждён guardedcontroller/collector. Итог — work/dev15-rollback-20261103/independent-result-review.json.

До native проверены: фиксированная единственнаякоманда/UNITscope/OIDmarker/role/TLS/caps, lateDMLwitness, настоящийSQLSTATE22012, OSErrorENOSPCexception, nested/service/outerrollback, sameUUIDretry/exactreceipt, независимый UNITwitness послеreap (включая FAIL), readonlyMAINHead13 и архивныепроверки, ACLдо/после.

Два замечания фактического исполнения исправлены отдельными узкими review: неправильныйpasswordmount audit и противоречащийпротоколу смешанныйDTO теста. Вторуюошибку предварительное code-review также пропустило; после статическойдиагностики разделеныROUTE/TOMB, pre-codeplanобновлён, guard/validator/caps/deadlinesнеослаблены. Эквивалентного слепого повтора не было: причины разные, каждый исправленныйrun разрешён после нового свидетельства/diff/SHAreview. Отдельный diagnosticDBrun не выполнялся.

ФинальныеSHA: controller `abd0c83b9602f6f57c5aa9b440668779a600385959e3978d33e2e0d5c1bb12b4`; helper `6c44a5ab637acc2d4ced09a201c79e521cc312e98132eaa3d01018f3f28bec42`; readonlyaudit `136e17eacea16bac0d919318d51be4776e2fd0d42d82513226fe8e4af28ae722`; ACL `21e25fa01dfbb5138beca50148ef175c79b782a2c9f466b003753c5b2bda40e4`; plan `389b6c29c852d1898797d76df9f154836795a94cc3a7fb2c7269f32a0b018bfe`. Node syntax/PythonAST2 PASS, exactgate перед запуском.

Для result-review предъявлены correctedrunSHA `47c7eb394c33fba8a8b486eec9ddea7042117845673dc9781ddda1d0d30e82df`, collectorSHA `a398b3f76a20fb79fed21d62a62d27ba69647cb18616645f9da20cb290f432ca`,8ветвей и7helperrawframes/HMACjoins/actualPostgreSQLerrors, UNIT/MAIN/архивнаясохранность, source30/config24/EV63/ACL/closed-state. Границы — dev15-rollback-results.md.
