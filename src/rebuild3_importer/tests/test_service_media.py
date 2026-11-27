import copy
from unittest import TestCase

from rebuild3_importer.errors import ManifestError
from rebuild3_importer.service_media import (
    INFOGRAPHIC_ASSET_ID,
    MAP019_PAGE_ID,
    bind_service_media,
    service_media_by_page,
    service_media_rows,
)


class ServiceMediaAuthorityTests(TestCase):
    def payload(self, *, hero=None, body=None):
        return {"fields": {"media": {"hero": hero, "body": [] if body is None else body}}}

    def test_exact23_ids_and_map019_preserves_only_exact_infographic(self):
        rows = service_media_rows()
        self.assertEqual(len(rows), 23)
        self.assertNotIn("MAP-115", {row["map_id"] for row in rows})

        source = self.payload(hero=INFOGRAPHIC_ASSET_ID)
        result = bind_service_media(source, MAP019_PAGE_ID)
        self.assertEqual(source["fields"]["media"]["hero"], INFOGRAPHIC_ASSET_ID)
        self.assertEqual(
            result["fields"]["media"],
            {
                "hero": service_media_by_page()[MAP019_PAGE_ID]["asset_id"],
                "body": [INFOGRAPHIC_ASSET_ID],
            },
        )

    def test_unexpected_prior_media_fails_closed(self):
        other_page = next(row["page_id"] for row in service_media_rows() if row["page_id"] != MAP019_PAGE_ID)
        cases = (
            (other_page, self.payload(hero="00000000-0000-4000-8000-000000000001")),
            (MAP019_PAGE_ID, self.payload(hero=None)),
            (MAP019_PAGE_ID, self.payload(hero="00000000-0000-4000-8000-000000000001")),
            (MAP019_PAGE_ID, self.payload(hero=INFOGRAPHIC_ASSET_ID, body=[INFOGRAPHIC_ASSET_ID])),
        )
        for page_id, payload in cases:
            with self.subTest(page_id=page_id, payload=copy.deepcopy(payload)):
                with self.assertRaisesRegex(ManifestError, "service-media-payload"):
                    bind_service_media(payload, page_id)
