# DEV-06 — независимый oracle новых изображений

2026-10-31. Статус: профиль согласован по D-324/D-325 (файл≤1000000байт); ничего здесь не является уже пройденным тестом. Основание REQ026/AC026, TEST-R013, security-baseline ARC-SEC003 и dev06-media-proposal.md. Значения ниже берутся из профиля владельца после его явного принятия, не из списка того, что случайно принял сервер.

| ID | Заранее заданные вход/ожидание |
|---|---|
| IMG-001-JPEG/PNG/WEBP | Настоящий одиночный файл согласованного формата/extension/MIME проходит: owner multipart сCSRF, не JSON/base64. Employee/visitor тотже payload иhandler получаютотказ |
| IMG-002-BYTES | Ровно1000000байт и40MP допустимы припрочихусловиях;1000001байт/11МиБ+1тело/2файла отклоняютсябезусечения/usableAsset. Позитивныйконтроль1000000байт — декодируемыйфайл, не paddingкоторыйсамклассифицируетсянеподдержаннойкомпозицией |
| IMG-003-PIXELS | 8000×5000=40MP проходит;8001×5000=40005000px (обестороны≤10000) и10001пооднойстороне отклоняютсядоопасногодекодирования. Отдельно позитивнаясторона10000при≤40MP; не заменятьпроверкуоднимсвойствомPillow.MAX_IMAGE_PIXELS |
| IMG-004-ORIENTATION | ИзвестныйJPEG400×300,EXIForientation6 → готовый300×400безorientation/GPS; приватныйsource имеетисходныебайты. Неиспользоватьmetadataдекодеракакединственныйожидаемыйрезультат |
| IMG-005-ALPHA | PNG/WebPсзаранеезаданнымипрозрачными/полупрозрачнымипикселями сохраняютальфу; малыйфайлнеувеличивается, proportionsнеискажаются. ВыходWebP:image/webp, носniff |
| IMG-006-RESIZE | Заранеезаданные4000×2000 → main1920×960 иpreview480×240;100×50 остаётся100×50вобоих. Границы1920/480необрезаютсяи не растягиваются |
| IMG-007-REJECT | SVG/HTML/EPS/PDF/GIF/TIFF/HEIC/AVIF,PNGподименем.jpg,неверныйMIME,обрезанныйPNG/JPEG,APNG/animatedWebP не создаютпригодныйAsset. Необещаетсядетекторлюбогоpolyglot; вpublicвыходиттолькозановокодированныйWebP |
| IMG-008-METADATA | ПодготовленныеEXIF/GPS/XMP/ICC/PNGtext/comments отсутствуютвготовыхвариантах; ниимяпользовательскогофайла,ниметаданные не формируютOSpath/шаблон/SQL/логpayload |
| IMG-009-ISOLATION | Реальныйworker: noNetwork/noDBsecrets/noappmount/nonroot/readonly/capdrop/resourcecaps; произвольныйjobpath/symlink/traversal/неизвестныеполя/повторнаякоманда не обходятfixedprotocol |
| IMG-010-BUDGET | Предельные40MPвключаяRGBAиEXIFrotation проходятвсогласованном512MiB/15s; actualpeak/time/exitOOM измеряются. Бюджетexchange128MiB подтверждёнфактическимENOSPC, небуквойвYAML |
| IMG-011-FAILURE | Workerunavailable/timeout/crash/badreceipt/outputhashmismatch/tempfull даютконтролируемыйотказилиpending,неAssetREADY/ложныйуспех; сохранившийсячастичныйфайлнеотдаётсяpublic |
| IMG-012-PRIVATE | НовыйsourceURIугадываниемнечитаетсяvisitor/employee; ownerpreviewзакрыт,publicderivative correctMIME/nosniffтолькопопринятомудопуску. Directorylisting/sourceoriginalsнепоявляютсячерез/img/ |
| IMG-013-LEGACY | Отдельныйпобайтныйпутьсравниваетреальныекопииснезависимымsourcehash/bytes,недекодирует/непереориентирует/неперекодирует214galleryoriginals. Полныеальбомы/порядок/миграцияпоDEV09/10,необъявлятьполныйAC025отодноймодельнойпроверки |

Захватиндикаторовпроводитсянанастоящихпроцессах/SQL/HTTP/файлах. Начальныеfixtureданныедопустимы,но проверяемыйuploadнеподменяетсяinsertAsset илиготовымexpectedJSON. По cleanup/usage моделиотносятсяк отдельному DEV06-storage testplan; настоящиеversionsStableHTMLинтеграциидобавляютсяприпоявлениисоответствующихмодулей.
