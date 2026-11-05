# Q030 — исправление bind API defaults и точная диагностика

Статус: техническое исправление в пределах согласованной архитектуры Q029; offline подготовка допустима, новый native lifecycle требует отдельного Q030. Q029result/history/frozen8 остаютсянеизменными. Исходнаяархитектура149b77d0acc3b38605594c859ffa6af81173f78087dff73a0a7114a3f93045f7 иKEY29-A01–A11 сохраняются.

## Подтверждённая несовместимость кода

[Официальный тип Moby Mount](https://github.com/moby/moby/blob/master/api/types/mount/mount.go): ReadOnly — bool сjsonomitempty; falseможетотсутствовать. Q029сравнивалhm.ReadOnly===false дляRWкаталога, поэтомуmissingdefaultfalseотклоняется. Это статический дефектсовместимости, не доказательство точного предиката прошлогоотказаKEY29_BIND. [Docker bind docs](https://docs.docker.com/engine/storage/bind-mounts/) определяютrprivateкакdefaultpropagation.

## Минимальное исправление

Новаяизолированнаякопия/runId, старыйrunне повторять. ReadOnly: missing→false; presentзначение допускаетсятолькобулево, null/строка/0/objectsотклоняются. Послеnormalization/sourceRO всёравнообязателенtrue, OUT_RWобязателенfalse; runtimeMounts.RW проверяетсяотдельнострого.

BindOptionsPropagation: толькоотсутствие/defaultempty либоrprivate считаютсятойжеприватнойизоляцией; нестандартные/разделяемыеpropagationиinvalidpresenttypesотклоняются. Type/target/canonicalsource/числоmounts/VolumeOptions/TmpfsOptions/остальныеsecurityfields неослаблять. Invalidне маскироватьtruthy/falsyпреобразованием.

ВместоодногонедиагностируемогоKEY29_BIND сохранитьclosedpredicateID+role SOURCE/OUT/COPY иограниченныеbool/presence/typefacts bindпроверки, втомчислеприотказе. НикакихrawhostEnv/sourcebytes/keyrepr/contentdigest. Другиеsecrettransport/privacy/clocks/cleanupguardR1R2неизменны.

## Порядок допуска

Сначалаoffline: reproducemissingfalseRW, absentROrefusal, invalidpresenttypes, wrongRuntimeRW/source/target/options/propagation; прежниеprivacy/partialcleanup tests иsourcebyteidentityhash. Независимоеcode reviewточногопакета доownerquestion. Candidateauthorityдолженждатьявнуюбудущуюстрокуowner «Разрешаю DEV29-Q030», анеиспользоватьистёкшийQ029допуск; дотакогоответаPrepare/Runзаблокированы.

ПослеответаQ030 — одинPrepare и, толькоприуспехе, одинусловныйqualificationlifecyclewriter10001:GID999→copy10001:999/0640→reader999RO→удалениеhelpers/copy/emptydir иindependentresultaudit. ЭтоНЕPGRun.

ВсеисходныеcapsQ029: тотжеpinnedimage/endpoint/engine, networknone/rootfsRO/capdropALL/no-new-privileges/128MiB/CPU0.25/PIDs32/shm16MiB/lognone; max1helperпоследовательно, firstinventory44с/info+inventory90с, прочиеcommands/helper10с/cleanup30с/global180с, output4096bytes. SourceRO/coremetadataACL, atimeobservationonly, boundedsecretread8192/nooutput/contentdigest иsafeownednonrecursivecleanupсохраняются. Никакихpull/build/install/settings/restart/новыхCAPs/измененийoriginalACL/старогосайта/VPS/SQL/PG.
