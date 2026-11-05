# KEY28 — приёмка трёх исправлений

D-509/утверждённый Q028 plan3bbd78169af67609cc72072cb1a273c881e8e76e8cdb4ca33bae8d95715e2ae3. Сохраняются KEY27-A01–A11, профиль, caps и oneShot. Ниже только ID для уже согласованных критериев.

| ID | Ожидаемое поведение |
| --- | --- |
| KEY28-A01 | Image query получает Id+Config без template-доступа кoptionalchildren. Missing/null Env/Volumes даютemptydefaults; invalidpresentтипы/неobjectConfig/неpinnedId/nonemptyVolumes отклоняются доcreate. |
| KEY28-A02 | Неуспешная команда сохраняет только согласованную closedcategory, bytes/hash/exit/clock. Неизвестный/неоднозначный stderr→OTHER, rawtext/Env/keydata не публикуются. Это не ретроспективная классификация старогоQ027. |
| KEY28-A03 | Отдельно сохранены before/after metadataACL fingerprints и результат их сравнения; failure/неполнаяcapture честноUNPROVEN, неbyteimmutability ключа. |
| KEY28-A04 | Новые copy/runId/attempt не изменяют старыеQ027frozen7/result иQ02642. OfflinePASS→independentcodeAPPROVED→onePreparePASS→atmostoneconditionalRun→cleanup/resultaudit. |

Настоящий ключ offlineтестами не открывать. Обеветвиread-open проверяются mockedOS, фактическийhelperтолькоодин: отказopen является результатом, неоснованиемповтора.
