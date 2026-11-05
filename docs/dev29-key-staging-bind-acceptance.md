# KEY30 — приёмка bind API compatibility fix

Техническийплан13a46fff6d62418ca8e9e4c340e0da295b9f64264f73285e999526f714eda9cf уточняетреализациюужеутверждённойpolicyQ029; KEY29-A01–A11 сохраняются. НовыйnativeтолькопослеQ030.

| ID | Ожидаемое поведение |
| --- | --- |
| KEY30-A01 | RW OUT: отсутствующийReadOnlyэквивалентенfalse, runtimeRWдолженбытьtrue. Original/ReaderRO: ReadOnlyтребуетсяtrue иruntimeRWfalse; missingROнепринимается. Любойpresentнеbool(null/0/string/object) отклоняется. |
| KEY30-A02 | Propagationabsent/empty/rprivate — privateэквиваленты; другиезначения/invalidpresenttypes отклоняются. Остальныеколичество/Type/Source/Target/options/securitychecks сохраняются. |
| KEY30-A03 | Failureсохраняетclosedpredicate/role иbool/presence/typefacts; никакогоrawEnv/paths/ключей/секретныхhashes. СтарыйQ029predicateостаётсяunknown. |
| KEY30-A04 | CandidateauthorityотклоняеттолькоQ029approval/предложенияQ030/отсутствиеявногобудущегоownerQ030. ДажеcodeAPPROVEDнедопускаетPrepare/Runдоответа. ActualPrivateDir/copy/nativeдотогонет. |
| KEY30-A05 | Writer/reader/secrettransport/caps/clocks/R1R2правиласохранены. Старыеsource/history/resultне меняются; новаяcopy/runId/freezeпроверяютсянезависимо. |

ДокументнеразрешаетновыйRun. Послеготовогокода/offlineиindependentreview—отдельныйownerответQ030наonePrepare/conditionalqualification/cleanup/audit.
