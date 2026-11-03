# DEV-29: ревью фактического focused-допуска

2026-11-03. **FOCUSED-PAYLOAD-REVIEW APPROVED**, ACTUAL-FOCUSED-PAYLOAD-REVIEW-001. Независимый рецензент проверил HMAC, закрытые схемы и связи фактических admission/provenance/baseline/budget, current package14 и Docker boundary. Файлы не менял, SQL/Run не запускал, ключ не выводил.

| Артефакт | SHA256 |
|---|---|
| Plan canonical | e87e5ac447ef46b0b1a5b8e23149a24e23ffe2432f3df3766acda933f746f320 |
| Admission raw | 9a06be06873e6d0ce3fb8734e0baf740791d6bfd24638523cba1e6ee821c0427 |
| Admission payload | e6ec34e3187bcbac3647366bf1fc3f1893532d8db7ca1c766e67e45b63f13f8e |
| Authorization receipt raw | b9ffa2235e792bcd2d755679580b35c9abb293a6bff1f83f8bce56969886c583 |
| Baseline receipt raw | a34492a14e5033eb731d272efbcb203bd131aa34f745cb11a0bbd3d1f68b37e1 |
| Budget-before raw | 0fd4daf6d81f9c433343ee71ec8051fcad1ad89fefa4ca2dc3f423e6c819bf11 |
| Code-review raw | 6c02ae7e8f487c822ff989f284aa1a3da94a8cfd64b4855414f891c54cca0f62 |
| Owner D-421 line | 5a05886b69fc5475db401c0a6da47164908b6a2c9922fa45688c20e702e82c3f |

Run c7c7e203-9a52-4cd7-b5ab-e9c46a7a975d, точные DB efb9e7a619b6d4db9f8627ff229f5d9a780cea31a479fee4daa2e5b621622ebf и сеть a2f15b0e601ccfd0917f9cf921fe6585970cca3a66bd209938b16f98e0dff813. Только PG29-001/003/004/005/006, без старого Run/quota/007. Expiry 2026-11-03T16:12:49.164Z не продлевать.

Witness совпал с Q007 по MAIN/UNIT/архивам/preservation/source: UNIT пустые7 journal tables,3 migration rows, sequence4true, MAIN b42ec332…, архивы закрыты. Duration7295ms, peak79,749,120байт, OOM0. DB caps512MiB/.5CPU/128, internal sole endpoint, no ports/exact mounts подтверждены. Budget339,233,627<2GiB. Предстартовое ACTUAL-FOCUSED-START-REVIEW-001 также APPROVED.

Это допуск reviewed Payload signer и одного Run001. Продолжение003–006 требует отдельного измерения/ревью и signed Measurement gate. Никакого разрешения MAIN writer/APP/production/старого сайта/VPS. Первое диагностическое сравнение рецензента ошибочно обратилось к wrapper вместо payload.baseline; исправленное pure-сравнение PASS, runtime не повторялся.
