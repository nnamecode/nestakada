# REBUILD-1 source-resolution foundation-host semantics

Дата: 2026-11-17. Evidence ID: `RB1-MEDIA-SOURCE-HOST-SEMANTICS-001`.

## Статическая проверка

Без DB/Docker/media read проверен foundation host: Windows `10.0.19045`, PowerShell `7.6.9` Core, .NET `10.0.14`. `System.IO.File.OpenHandle` доступен, но `System.IO.FileOptions` не содержит `OpenReparsePoint`/no-follow option.

Standard runtime удерживает один handle и запрещает write/delete sharing, но не доказывает атомарный no-follow open. Strict D-1352 потребовал бы Windows-native wrapper; код/runtime/media read не начинались.

## Решение владельца

Владелец выбрал лёгкий вариант 1: trusted quiescent foundation media root. Native wrapper/library/container helper/scanner0.

Amendment требует до DB/media read доказать project containers0, отсутствие известных project writer processes/jobs и immutable approved canonical root; затем strict key/component no-link checks до open, один `File.OpenHandle` с `FileAccess.Read` и `FileShare.Read`, size/SHA из одного handle, post-read component/type/size checks. Результат — локальное point-in-time evidence при заявленной trusted/quiescent границе, не защита от привилегированного внешнего attacker и не обещание после close.

Если quiescence/root/component checks не доказаны, read запрещён. Exact301/transfer/Q002/product/live остаются закрыты.
