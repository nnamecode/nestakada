# INFOGRAPHICS-01: образец MAP-019

Статус: **визуальное направление принято владельцем D-969; файл закреплён за MAP-019, placement отложен**.

Дата: 2026-11-13. Основание: D-965/D-967 и approved `INFO-MAP-019` из `docs/infographics-dev09m-content-map.md`.

## Файл

| Параметр | Значение |
| --- | --- |
| Путь | `media/design-concepts/infographics/map-019-body-repair-sample-v1.png` |
| Формат | PNG preview |
| Размер | 1448×1086 |
| Байты | 2025618 |
| SHA-256 | `01bfda46e7dba90adb38affd6fe615beba90f9e182a77073a5ec6e27fa5c5678` |
| Генерация | built-in `image_gen`, один вызов |

Файл находится вне Git согласно правилу `media/`. Исходный built-in output сохранён отдельно в каталоге Codex и не удалялся.

## Содержание образца

Ровно три утверждённых этапа:

1. `ОЦЕНКА ПОВРЕЖДЕНИЙ` — автомобиль с видимым повреждением кузова и знак осмотра.
2. `ВОССТАНОВЛЕНИЕ ДЕТАЛЕЙ` — кузовная деталь в процессе ремонта/окраски.
3. `ПРОВЕРКА РЕЗУЛЬТАТА` — собранный кузов, контрольный лист и визуальный осмотр покрытия.

Заголовок: `РЕМОНТ КУЗОВА`. Другого текста, цен, сроков, гарантий, телефона, логотипа и watermark нет.

Alt candidate: `Три этапа ремонта кузова: оценка повреждений, восстановление деталей и проверка результата.`

Caption candidate: `Объём кузовного ремонта определяют по фактическим повреждениям автомобиля.`

## Фактическая проверка

- Русские строки визуально совпадают с prompt и присутствуют ровно по одному разу.
- Поток слева направо и три равных смысловых блока читаются без дополнительного объяснения.
- Белый/светло-серый, чёрный и оранжевый соответствуют принятому направлению публичного дизайна.
- Легковые автомобили не содержат различимых марок или логотипов.
- Смысл не добавляет цен, сроков, гарантии результата или неподтверждённых методов ремонта.

## Отклонение кандидатных параметров

Built-in generation вернул PNG 1448×1086 и 2025618 байт. Это preview для проверки композиции, а не утверждённый production asset. В проекте не найдено уже установленного Sharp/ImageMagick/ffmpeg/cwebp; новая зависимость ради образца не добавлялась.

До будущего полного `INFO-Q002=1` запрещено:

- объявлять WebP/1200×900/1MB окончательными параметрами;
- генерировать остальные 23 изображения;
- добавлять новый converter/dependency;
- импортировать файл в Asset/БД, привязывать к версии страницы, менять renderer/slot, публиковать или затрагивать live/VPS.

## Prompt

```text
Use case: infographic-diagram
Asset type: explanatory infographic sample for the service page “Ремонт кузова”
Primary request: create one polished, clear 4:3 infographic explaining the three confirmed stages of car body repair.
Scene/backdrop: clean white and very light gray background, restrained automotive workshop visual language.
Subject: one neutral modern passenger car body shown in three connected stages: first inspection of visible body damage, then restoration of body panels, then final inspection of assembled body and paint surface.
Style/medium: crisp vector-like raster infographic, professional automotive service website, realistic-enough car proportions, simple technical pictograms and arrows, generous whitespace.
Composition/framing: landscape 4:3, left-to-right flow with exactly three equal stages, large readable Russian typography, mobile-readable hierarchy.
Color palette: white, light gray, black and restrained orange accents; no other strong brand colors.
Text (verbatim): "РЕМОНТ КУЗОВА", "1. ОЦЕНКА ПОВРЕЖДЕНИЙ", "2. ВОССТАНОВЛЕНИЕ ДЕТАЛЕЙ", "3. ПРОВЕРКА РЕЗУЛЬТАТА"
Constraints: render the four Russian text strings exactly once and verbatim; no other words or numbers; no prices, timing, guarantees or promotional claims; no logos, trademarks, badges, phone numbers, people, watermark or fine print; do not imply guaranteed restoration; the visual must communicate assessment, repair-or-replacement work, and result inspection without adding technical claims.
```

## Решение владельца

Сообщение владельца «Отличная картинка» принято как `INFO-Q004=1`: визуальное направление preview MAP-019 одобрено. Владелец попросил добавить изображение внутрь страницы, но явно отложил выбор места.

До выбора placement файл закреплён за MAP-019 только в утверждённой content map. Не создаётся скрытая Asset/usage/version запись, которая не отображалась бы посетителю. После выбора места используется существующий `embedded_images` + image layout node; новая модель, schema branch или renderer не нужны.

`INFO-Q002` пока не открыт. Он может быть поставлен владельцу только после отдельного review предложения placement и production-параметров; его утверждённый смысл не меняется: одновременно принять композицию/placement/format/dimensions/byte cap и разрешить остальные 23 файла.

Последующим прямым сообщением «поставь после вводного текста» владелец закрыл placement и разрешил локальную production-подготовку только MAP-019 как `INFO-Q005=1`: WebP1200×900/≤1000000 bytes, existing image block after `intro_text`, без remaining23/persistent apply/publication/live. `INFO-Q002` этим не открывается.
