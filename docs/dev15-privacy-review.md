# DEV-15: независимое ревью HTTP/privacy controls

2026-11-03, D-396, RP15-018/PV15. Независимые plan/code/result-review — **APPROVED в ограниченной HTTP/privacy fixture области**. Рецензент `/root/tls_review` не редактировал исходные артефакты и не повторял native/БД/Docker. Итоговый independent-result-review.json сверил raw2cases/6captures/8safeevents/responseheaders+body/HMACgate/code/source30/config24/EV63/certs. Closed-state проверен по реально исполненным guarded controller/collector, не по новому runtime прогону.

Предварительное ревью потребовало различать SERVER_EOF/408 и client timeout, доказывать фактическую exactbody длину и вход в actualendpoint, собирать обаcontainerlogs иsuccessfulexec stderr доStop, явно обозначать syntheticchild. Эти условия реализованы.

PV-REV-001 (P2): первый кандидат сканировал только bodyresponse. До native добавлены scan имён/значений всех headers, границы32headers/16КиБ, наружу safe bool/count. Узкий diff принят, finding закрыт.

Финальные SHA: controller `d4aa2831660275bcc83cc871c2a8ce0fd26e3f36393fbdac385cfcde64489570`; privacyprobe `998684e9602c1010380be0d7da6775f0d91cd491629634a5fc79f5d3771b3101`; importedLDprobe `3aecac210f1d3f0501daf09dc1caaaaa16bda3660bf47866eb166b070d75484d`; ACL `51ca0d8149c0558cf677badf158b10e7428d818f4ffcf90b00902111bae40ee9`; plan `dee502a3bb2c61c08151fb7929986b47ea1cdf2e3408b59a9fa98f3c60ede118`. Node syntax/Python AST PASS до native, exactgate после независимого review.

Для result-review предъявлены reportSHA `289a19af370e68722e613262950b285522b9767c9186617f3efa19d66f08f02d`, collectorSHA `a96b64f254532862a12b7ae43720e06ca67c1e1c65643f71866c9f2244c37d8d`, rawcases/6captures/HMACgate, реальныеserverEOF5/10с,8safeevents/no-canaries, source30/config24/EV63 и closed-state. Scope/непроверенныеграницы — dev15-privacy-results.md.
