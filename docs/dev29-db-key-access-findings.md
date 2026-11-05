# DEV-29 — метаданные TLS key

2026-11-04, продолжение D-502. Только read-only Windows metadata и статический код; Docker/SQL не запускались. Содержимое ключа не читалось, файл/ACL/frozen package не менялись.

Известный исходный файл regular, не link/reparse,1704bytes. Windows ACL наследуется, разрешает владельцу и SYSTEM; широких явных разрешений в прочитанной ACL нет. Это не доказывает эффективные Linux UID/GID/mode или read-access через Docker Desktop bind.

`scripts/local-foundation.ps1`, Prepare-Secrets: Protect-Private до создания, OpenSSL req -newkey создаёт TLS pair через helper с readonly rootfs/cap-dropALL/networknone и bind private. Явный --user в helper отсутствует. Далее файлы сохраняют ограниченную наследуемую Windows ACL. Наблюдение не доказывает точный исторический запуск/umask/Linux mode текущего ключа; имеющийся ключ не регенерировали.

Подтверждённая runtime причина Q026 остаётся: cp TLS key получил Permission denied под999:999 передINITDB. Механизм запрета на Windows↔Linux bind пока не установлен. Следующая диагностическая ступень требует отдельного ограниченного nonSQL helper; текущий read-only план Docker не разрешает.

Одна первая ошибка поиска: указаны отсутствующие compose/foundation каталоги; повтор поиска по ним не выполнялся. Найденный известный scripts/local-foundation.ps1 прочитан ограниченными фрагментами.

Родительская private — обычная directory, не link/reparse; ACL защищена от наследования, две explicit rules. Файл наследует две правила от этой директории. ACL и файлы не менялись. Это не заменяет Linux bind metadata.
