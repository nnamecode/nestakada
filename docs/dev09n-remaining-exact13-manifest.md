# DEV-09N exact13 — identity manifest

Дата: 2026-11-15. Статус: **owner contact choice resolved; canonical package pending**. Authority: D-1101, D-1095/D-1098.

## Page identities

Root UUID: MAP-001 `e80c3de1-feea-4847-b550-325a825ffc0e`. Existing occupied root positions: MAP-002=1, MAP-008=2, MAP-006=4. DEV-09N fills only free positions and does not reorder existing pages.

| MAP | UUID | URL | kind | parent | position | name / H1 |
|---|---|---|---|---|---:|---|
| MAP-003 | `ffdbdc65-39d8-4e22-88e3-7e44e752fbde` | `/partners` | legacy_partner_links | MAP-001 | 3 | Партнёры |
| MAP-004 | `b427b1b8-2fb9-44cd-a301-5b14f2f991b2` | `/actions` | actions | MAP-001 | 5 | Акции |
| MAP-005 | `df6b50bb-d749-4106-b053-2999e0335223` | `/reviews` | reviews | MAP-001 | 6 | Отзывы |
| MAP-007 | `91631e35-5e81-407f-806b-e973223d7340` | `/contacts` | contacts | MAP-001 | 7 | Контакты |
| MAP-009 | `87cf5862-20fd-4ad3-b90c-bb4d6e888355` | `/direct-contact` | legacy_director_message | MAP-001 | 8 | Прямая связь с директором |
| MAP-044 | `e3c55ade-799b-4118-88b8-3fb03deea235` | `/nash-servisnyij-czentr` | legacy_empty_main | MAP-001 | 9 | Наш сервисный центр / empty H1 |
| MAP-049 | `9b5b3c53-d8c7-4395-89e5-6d07645f0d61` | `/about` | legacy_empty_main | MAP-001 | 10 | О компании / empty H1 |
| MAP-078 | `da5e675f-fedf-4c4e-a3b4-c82d6a6dafcb` | `/news/` | legacy_news_catalog | MAP-001 | 11 | Новости |
| MAP-090 | `62228d71-44ce-44da-82b5-85ba9c7d93dd` | `/garantii` | legacy_under_construction | MAP-001 | 12 | Гарантии |
| MAP-097 | `f30b0e81-5ac6-4779-bb0e-65dc3ae5c301` | `/cctv` | legacy_camera_schedule_text | MAP-001 | 13 | Web-камеры техцентра |
| MAP-045 | `13fe0f8c-001c-446a-8cb7-b588fcdb1916` | `/news/priobretenie-podemnika-do-10-tonn-dlya-remonta-malotonnazhnyix-avtomobilej` | legacy_news_article | MAP-078 | 0 | Приобретение подъемника… |
| MAP-039 | `f1c97615-2220-4732-a9cb-d5979d6500b2` | `/news/atcz-estakada-podklyuchila-mnogokanalnyij-telefon` | legacy_news_article | MAP-078 | 1 | АТЦ «ЭСТАКАДА» подключила… |
| MAP-033 | `06f43591-ff13-4409-89ef-823534b5b33e` | `/news/okazanie-dopolnitelnyix-uslug` | legacy_news_article | MAP-078 | 2 | Оказание дополнительных услуг |

All13 pages are initially hidden. Titles/descriptions/source SHA/text come only from pinned route/evidence/source/artifact authorities; this manifest does not authorize invented content.

## Contact override D-1101

The old direct number `8 (903) 772-33-43` is excluded from package, rendered text and links. `/direct-contact` preserves the approved explanatory text but uses only current company contact `+7 (499) 110-25-52` / `tel:+74991102552`. Contacts email is the owner-confirmed current `estakada10@yandex.ru`; the old source email is not migrated.

## Media identities

Folder UUID `53e5e79f-3aca-40c7-a130-c025bdde8a8b`, path `dev09n/remaining-content`.

| MED | asset | file | image | bytes | SHA-256 |
|---|---|---|---|---:|---|
| MED-0001 | `89f6efb6-b243-4fc8-80ec-a61dc5393ef8` | `cdad24a4-91f9-451f-9c59-fa9f305f3a77` | `edd55fd1-91cf-4e20-8cfc-2f5e9861dcc1` | 151726 | `be710512d347e6b4d529240817edb9050df9d5daf61bd4efcf4c02b5b2c262bc` |
| MED-0002 | `70dab673-6a5f-4274-947a-7bf8efc5e029` | `6488fe3d-cef6-484a-aa48-a2fa0291ae0b` | `0721a988-5dc4-42a4-b73e-8bb2f27705ca` | 222598 | `df13ba501d57cbade361225c90f34d1276f7fbff5911217624569a2d319cd02a` |
| MED-0004 | `6bd3397f-d79e-4542-bf2a-168bf8eefd14` | `efb52c4a-3926-4eee-b7a5-c8d7c3d6d923` | `4f680d0d-66e0-41a4-8361-6a85b84d9bba` | 191734 | `8fc2142538ad2f7c3a0016df89f3d3f90df2da37d03bd1b39135e95f810c3df5` |
| MED-0005 | `cdaba860-0d92-4c28-a340-d392cf5412ab` | `012aeb12-0028-4da8-a74f-64c2ccc07538` | `94c7fa00-3395-465f-abbe-d991bedbcd0e` | 190431 | `68fb97e86a37c2361686bb057590d602b951fca6eb269725813265915a2472ad` |
| MED-0006 | `e1f19d53-5811-4166-858d-35308ae853c1` | `6e1eeea7-b8ae-4f08-a71f-fbc9d0983dd6` | `5857c071-6e81-460d-9fac-519bae6a0ebc` | 189101 | `e7e0b315e4fd6f192713476680f2cee5ba830983def383b0c1f43f72a9cfcec0` |
| MED-0007 | `ac6af51d-a08b-47bb-b818-0c84e13e7050` | `5ef31b85-ec14-49a7-a944-e5c62fcb977e` | `7efdc034-f931-4397-be93-fe503a19eeca` | 247402 | `5f8dd608684af7baf484397c77d9a9cc3805cc7bd9255df1079646f1b79df8e9` |
| MED-0008 | `27fe380b-0728-489a-b7cf-64a47aea9c14` | `29f355a7-3a9f-4692-8295-0591afbe4f5c` | `191e8b95-af10-423e-9507-59a7c62be591` | 201684 | `640bc75001fede5e3c29c85ca2629af2263770da5014339edc0e5def9d83d43f` |

Storage key is exactly `img/<asset-id>/original.<source-extension>`. Provenance is fixed `DEV09N owner-approved remaining content`; assets are design media, not legacy gallery originals.
