# DEV-07 — подготовка кандидата пакетов D-330

2026-10-31. Только рецепты и инструмент подготовки. Приложение, foundation lock, worker, Windows и VPS не изменяются. Автоматического подключения кандидата нет. Полный транзитивный lock, скачивания, advisories, ABI/native проверки и реальные результаты ещё должен получить координатор в разрешённых изолированных запусках.

## Файлы и неизменяемый состав

- `environment/editor-package/direct-pins.json`: точные десять JS и пять Python пакетов из D-330, база Python `sha256:09433387bce7dd726eb2f76918287c04c1fbd340eed1db2aaa3397fbd0474951`, бюджеты подготовки.
- `package.json`: без lifecycle/scripts; Tiptap3.32.2 и esbuild0.28.2, включая явно одобренный `@esbuild/linux-x64`. Версия pnpm11.25.0 соответствует существующему инструменту.
- `pnpm-workspace.yaml`: ignoreScripts, только linux/x64/glibc. Lock может перечислять optional binaries прочих платформ, но downloader их не скачивает и явно перечисляет как skipped.
- `requirements.lock`: пять точных wheel SHA256, сверяемых с сохранёнными официальными PyPI metadata. Для nh3 только cp38-abi3 manylinux x86_64, не cp314t; его совместимость ещё проверяется реально.
- `App.candidate.Dockerfile`: производный образ от принятой базы через существующий localTag с обязательной предварительной сверкой exact ID; только COPY заранее проверенного site-packages, никаких RUN/package execution в BuildKit. Offline hashed wheel install выполняется перед этим отдельным ограниченным docker run. Wheels не попадают в runtime layers. Runtime user10001:10001. Рецепт не меняет Compose или runtime lock.
- `tools/editor_package/prepare.mjs`: stdlib Node, без subprocess/install/package execution. Режимы вызываются явно, импорт не запускает подготовку.

## Фиксированные пути

Корень только `T:\nestakada\work\dev07-package-cache`:

| Путь относительно корня | Назначение |
|---|---|
| `candidate-manifest.json` | schemaVersion1, D-330, preparation-only, base image ID, exact direct pins, Python filename/size/SHA/url/metadataSha256 |
| `python/requirements.lock`, `python/wheels/` | Только пять проверенных wheels для отдельного bounded offline install |
| `python/site-packages/`, `python/installed-tree.json` | Выход bounded install и фактический список всех файлов с SHA/size |
| `python/base-site-packages.json` | Полученный root из exact base перечень top-level namespaces для collision guard |
| `python/download-receipt.json` | Проверенные артефакты Python, без заявления проверки безопасности |
| `js/project/` | package.json/workspace, исходный pnpm-lock, затем изолированный node_modules |
| `npm-metadata/`, `npm-tarballs/` | Metadata и архивы с именами SHA256 от name@version |
| `npm-artifacts.json` | Реальный исходный lockSHA, полный граф с skipped платформами, actual archive SHA/size/SRI, inventory и заявленные scripts (не исполненные) |
| `qa/` | Только отдельные QA output/bundle; продуктовый bundle этим инструментом не создаётся |

QA владеет `probe.py/probe.mjs`; подготовка эти файлы не меняет. Image ID кандидата объявляется только после фактической сборки координатором.

## Команды и порядок для координатора

Из `T:\nestakada`:

```powershell
node --check tools/editor_package/prepare.mjs
node tools/editor_package/prepare.mjs selfcheck
node tools/editor_package/prepare.mjs init
node tools/editor_package/prepare.mjs python-download
node tools/editor_package/prepare.mjs budget
```

`selfcheck` не пишет файлы и не обращается в сеть. `init` сверяет сохранённые exact PyPI metadata, pins и requirements, создаёт только названный candidate cache. `python-download` выполняет последовательные HTTPS запросы без redirects, сверяет точный размер/SHA перед признанием артефакта готовым. Неизменившийся артефакт можно повторно проверить, несовпадающий существующий файл автоматически не заменяется.

После init координатор запускает metadata-only подготовку lock в уже принятом Playwright image `mcr.microsoft.com/playwright@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea`. Внутри контейнера проект монтируется как `/cache/js/project`, весь cache как `/cache`, существующий pnpm11.25.0 только readonly как `/pnpm`. Рабочий каталог `/cache/js/project`; память≤1GiB,CPU≤2, без секретов/БД/Docker socket. Команда внутри:

```sh
node /pnpm/bin/pnpm.mjs install --lockfile-only --ignore-scripts --store-dir /tmp/pnpm-store --network-concurrency=1 --fetch-retries=0
```

Этот шаг разрешён координатором отдельно как получение metadata/full lock; он не распаковывает и не запускает пакеты. Его фактическое потребление cache проверяется до/после, не объявляется поштучной жёсткой квотой Windows. После получения неизвестной формы lock инструмент останавливается; нельзя молча расширять parser или выполнять network install как обход.

```powershell
node tools/editor_package/prepare.mjs npm-download
node tools/editor_package/prepare.mjs budget
node tools/editor_package/prepare.mjs verify
```

`npm-download` принимает только известную pnpm9 структуру exact package identities + inline integrity, проверяет наличие direct pins, сопоставляет каждую identity/SRI с официальной exact-version metadata, сохраняет реальные bytes и hashes. URL/git/file/workspace sources и YAML anchors отвергаются. Только одобренный linux-x64 esbuild artifact принимается с зафиксированным D-330 SHA512. Прочие @esbuild/platform остаются skipped, не загружаются.

Прежде распаковки каждый gzip/tar имеет bounded decompression≤128MiB, checksum/entry-path/type/duplicate checks и inventory≤10000files; links/devices/неизвестные PAX формы не допускаются автоматически. Это предохранители подготовки пакетов, не лимиты содержимого сайта. Tar ничего не извлекает. Перед offline install резервируется место под две копии всех файлов (store+project) с запасом4096байт на файл. Слишком большой/неподдержанный официальный архив требует отдельного разбора причины, не повторов с ослабленным guard.

**Фактический статус offline derivation: эксперимент отклонён.** Первый actual pnpm11 install производного lock завершился ERR_PNPM_RESOLUTION_SHAPE_MISMATCH49, протокол npm-offline-install.txt. Policy не отключается, install с этим derived lock повторно не запускать. Исходный canonical lock восстанавливает координатор; partial node_modules сохраняется в evidence. Ниже механизм derivation описан только как сохранённый эксперимент, не рекомендуемый путь установки.

Offline pnpm store/import — отдельный шаг координатора после проверки графа и архивов. Одного наличия tarballs недостаточно, чтобы объявить pnpm store готовым. Производный offline lock был допущен для эксперимента: только resolution.tarball для уже проверенных identity/SRI, без изменений dependency versions/importers/snapshots/peer resolution/integrity. Фактическая policy-проверка этот вариант не приняла.

```powershell
node tools/editor_package/prepare.mjs offline-lock
```

Экспериментальный инструмент сохраняет исходный lock неизменным в `js/original-pnpm-lock.yaml`, создаёт `js/offline-pnpm-lock.yaml` и `offline-lock-receipt.json` с обоими SHA и точным line diff. Только проверенные ссылки `file:../../npm-tarballs/<identitySHA>.tgz` добавляются в resolution; другие платформы esbuild остаются skipped без добавления artifact. Обратное применение зафиксированных line changes должно побайтно восстановить весь исходный lock. Перед derivation повторно проверяются actual bytes/hash/SRI каждого архива. Полнота графа обязательна. Следующая ранее применённая команда сохранена как диагностика эксперимента, **не выполнять её для новой установки**:

```powershell
Copy-Item -LiteralPath work/dev07-package-cache/js/offline-pnpm-lock.yaml -Destination work/dev07-package-cache/js/project/pnpm-lock.yaml
node tools/editor_package/prepare.mjs verify
```

`verify` проверяет original/derived hashes, регенерирует exact diff и проверяет working lock только как original/derived, без произвольного третьего состояния. После замены working lock `npm-download` повторно не запускать: его вход — только исходный upstream lock. Окончательная установка из `/cache/js/project` обязана использовать в контейнере `--network none`:

```sh
node /pnpm/bin/pnpm.mjs install --offline --frozen-lockfile --ignore-scripts --store-dir /tmp/pnpm-store --config.package-import-method=copy --config.node-linker=hoisted
```

Те же platform settings обязательны; missing artifact приводит к отказу, не к fallback download. После установки координатор повторно измеряет budget и сверяет lock; Docker mount не открывает произвольные пути. Автоматический esbuild postinstall запрещён; проверенный binary запускается явно только для сборки QA bundle после аудита. После отказа derived-lock координатор/рецензент рассматривают canonical plan: original frozen lock, bounded temporary builder1GiB/2CPU, online fetch в ограниченный256MiB store tmpfs, затем фактический Docker network disconnect/inspect empty и install frozen/offline в том же контейнере. Новые команды/запуск этого плана исполнитель не выполняет; допуск и фактические свидетельства фиксирует root отдельно.

Python install сначала выполняется координатором в отдельном docker run от exact Python base ID с `--memory=1g --cpus=2 --network=none`, без секретов/БД/всего приложения. Wheels/requirements монтируются readonly, отдельный пустой `python/site-packages/` — единственный выход, tmpfs ограничен. Это прежний согласованный builder resource budget; обычные BuildKit RUN не объявляются гарантированно ограниченными этими пределами. Команда Python внутри такого контейнера:

```sh
python -m pip install --target /output/site-packages --no-index --no-cache-dir --no-compile --only-binary=:all: --require-hashes --no-deps --find-links=/inputs/wheels -r /inputs/requirements.lock
```

Не использовать старую RUN-рецептуру. После установки координатор отдельно запускает pip check с PYTHONPATH=/output/site-packages и фактические QA/native проверки в ограниченном контейнере, не в BuildKit. Предварительный actual base inventory имеет точный контракт `python/base-site-packages.json`: schemaVersion1, imageId=принятый094333..., sitePackagesPath=/usr/local/lib/python3.14/site-packages, topLevelEntries=массив настоящих имён из этой директории base. Никаких expected libraries вместо чтения базы. Root фиксирует provenance фактического Docker inspect/capture.

```powershell
node tools/editor_package/prepare.mjs installed-manifest
```

Эта команда читает все выходные файлы и проверяет обычные directories/files, no symlink/junction/hardlink, ровно пять библиотечных namespaces и пять dist-info из exact pins, реальные Name/Version в METADATA, отсутствие любого top-level collision с фактической base. Записывается sorted file manifest с actualSHA/bytes/treeSHA и hash baseline. Неизвестный/пропавший namespace либо несовпадение existing manifest дают отказ, не overwrite. Перед COPY координатор повторно сверяет installed tree с этим manifest; после сборки проверяет фактический импорт/native/версии и отсутствие архивов/компиляторов. Это не разрешение подменить guard именами expected после build.

Финальная упаковка из корня проекта — только после этих проверок:

```powershell
docker.exe build --pull=false --network=none -f environment/editor-package/App.candidate.Dockerfile -t nestakada-local/app-editor:candidate-d330 work/dev07-package-cache/python
```

Выполняет только координатор. Перед сборкой Docker inspect должен подтвердить точный локальный base ID. Полученный tag не является разрешением подключить образ; новый фактический ID/состав/native evidence/advisories/QA и независимое ревью фиксируются отдельно. Старый worker по-прежнему на прежнем образе.

## Бюджет и границы безопасности подготовки

2GiB — общий плановый бюджет названного cache, не установленная quota Windows. Downloader перед каждым сетевым получением резервирует полный верхний предел ответа против фактически измеренного дерева; max metadata2MiB, tarball32MiB, wheel — точный официальный размер. Запрос≤30s, redirects запрещены, счётчик проверяется и при отсутствии Content-Length. Одна операция под эксклюзивным `.prepare.lock`, никаких параллельных writers/installs в том же cache. После crash lock не удаляется автоматически: оператор проверяет отсутствие процесса и состояние файлов.

Cache measurement разрешает внутренние relative links только в `js/project/node_modules`; все другие cache links отвергаются. Для Windows/Linux portability используется lstat/readlink каждого компонента, без native realpath и без предварительного lexical удаления `..` до проверки промежуточных links. Target остаётся внутри этого node_modules, absolute/drive/backslash/control/unknown node types/неизвестные targets/cycles/>32hops отвергаются. Directories/files не обходятся повторно через link; hardlinked файлы учитываются по inode. Исходные artifact paths/предки через checked/read по-прежнему полностью запрещают symlink/junction. Переполнение или drift вызывает отказ. Файл, оборванный при записи/скачивании, не считается receipt; автоматическая перезапись/очистка не выполняется. Политика не разрешает удалять существующие данные ради места.

Проверки этого исполнителя: Node syntax PASS и12 pure selfchecks PASS (exact graph/optional skip, malformed URL/identity/anchor, gzip/tar measurement и traversal/link/absolute denial; offline exact diff/completeness/path/integrity), без network/filesystem writes. Первая PowerShell ошибка чтения metadata `empty pipe element` исправлена конкретной структурной заменой `foreach`→присваивание массива перед pipeline; повтор того же действия без изменения не выполнялся. Реальные загрузки, полный lock/install, Docker build, ABI/codec/CSP/security/advisory испытания этим исполнителем не запускались и PASS не заявлены.

Первые диагностики координатора относятся к подготовке, не к совместимости пакетов: generic `--config.network-concurrency=1` передал строку вместо Number и PQueue отказал до создания lock; принятое исправление — штатные numeric CLI options. Затем первый npm-download отказал до загрузок: поиск URI `file:` ошибочно совпал с суффиксом штатного `excludeLinksFromLockfile: false`. Теперь запрет URI имеет явную token boundary и остаётся case-insensitive для настоящих file/git/link/workspace/URL значений. Регрессия содержит реальные settings autoInstallPeers/excludeLinksFromLockfile, отрицательные plain/quoted/mixed-case sources; syntax и17 pure selfchecks PASS. Root повторяет runtime только после адресного ревью. Для offline layout согласованы copy+hoisted, чтобы Linux symlinks/hardlinks не конфликтовали с Windows guard; граф/версии не меняются.

Следующий запуск после lexical fix остановился по другой фактической причине до fetch: Windows realpath получил EACCES на созданном Linux pnpm-store/v11/projects symlink. Root readlink/lstat подтвердил внутреннюю ссылку `../../../js/project`, но host guard её не смог проверить; guard не ослаблен. Координатор сохраняет metadata store в evidence отдельно проверенным перемещением, active cache освобождается от этой неподдержанной структуры. В дальнейших metadata/offline командах store размещается только в `/tmp/pnpm-store` ограниченного container tmpfs (точный размер фиксирует координатор в пределах принятого memory1GiB), не на Windows T:. Постоянный проект сохраняет copy+hoisted; для derived file-tarball lock store не нужно переносить между контейнерами. Временный store измеряется отдельно; cache2GiB не выдаётся за ограничение Docker tmpfs. Новый download разрешается лишь после подтверждённого изменения состояния cache, без повторения прежнего условия.

Координатор сообщил actual canonical путь: fetch74 policy PASS; после Docker network disconnect Networks={} и только lo внутри, install original frozen/offline49packages PASS12.9s, lifecycle scripts ignored, три inputSHA неизменны, peak349294592B. Builder остановлен/удалён координатором. Затем cache guard впервые встретил другую новую Linux link `node_modules/.bin/esbuild -> ../esbuild/bin/esbuild`, regular internal target; Windows realpath снова не смог проверить её. Только installed-node_modules проверка теперь использует ограниченный portable resolver выше; обычные artifact paths не ослаблены. Pure selfchecks расширены до24: internal chain positive, настоящий external chain, cycle, absolute path, hidden intermediate escape,32hop limit и missing target negative с проверкой причин. Node syntax/selfchecks PASS; исполнитель не писал cache и не выполнял packages/install/Docker. Повтор actual budget/installed-manifest — только после независимого адресного ревью.
