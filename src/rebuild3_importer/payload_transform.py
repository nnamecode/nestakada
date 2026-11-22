from __future__ import annotations

import copy
from html import escape
from typing import Any

from rebuild3_importer.content import MEDIA_SLOTS, validate_payload
from rebuild3_importer.errors import ManifestError


TARGET_KIND = {
    "service_wash_legacy_alias": "service_detail",
}


def target_page_kind(source_kind: str) -> str:
    return TARGET_KIND.get(source_kind, source_kind)


def _paragraph(value: str) -> str:
    return "" if not value else f"<p>{_inline(value)}</p>"


def _inline(value: str) -> str:
    return escape(value, quote=False).replace("\r\n", "<br>").replace(
        "\r", "<br>"
    ).replace("\n", "<br>")


def _plain(value: str) -> str:
    return " ".join(value.splitlines())


def _join_rich(*values: str) -> str:
    return "".join(value for value in values if value)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _image_assets(source: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    mapping: dict[str, str] = {}
    ordered: list[str] = []
    for row in source["embedded_images"]:
        image_id = row["id"]
        asset_id = row["asset_id"]
        if image_id in mapping and mapping[image_id] != asset_id:
            raise ManifestError("legacy-media-image")
        mapping[image_id] = asset_id
        ordered.append(asset_id)
    return mapping, _unique(ordered)


def _media(
    source: dict[str, Any], target_kind: str, profile: dict[str, Any] | None,
) -> dict[str, Any]:
    slots = MEDIA_SLOTS.get(target_kind)
    if slots is None:
        return {}
    result: dict[str, Any] = {
        slot: None if slot == "hero" else [] for slot in slots
    }
    image_assets, embedded = _image_assets(source)
    main = source["main_image"]
    preview = source["preview_image"]
    lead = [
        row["asset_id"] for row in (main, preview)
        if row is not None
    ]
    if target_kind == "home":
        if profile is None:
            return result

        def asset(image_id: str) -> str:
            value = image_assets.get(image_id)
            if value is None:
                raise ManifestError("legacy-home-media")
            return value

        result["hero"] = asset(profile["hero"]["image_id"])
        result["service_cards"] = _unique([
            asset(row["image_id"]) for row in profile["services"]
        ])
        result["process"] = _unique([
            asset(row["image_id"]) for row in profile["steps"]
        ])
        result["works"] = _unique([
            asset(profile["photo_strip"]["image_id"]),
            *[row["asset_id"] for row in profile["works"]],
        ])
        result["brand_logos"] = []
        covered = {
            result["hero"],
            *result["service_cards"],
            *result["process"],
            *result["works"],
        }
        if covered != set(embedded):
            raise ManifestError("legacy-home-media")
        return result
    if target_kind == "actions" and profile is not None:
        banners: list[str] = []
        for row in profile["cards"]:
            asset_id = image_assets.get(row["image_id"])
            if asset_id is None:
                raise ManifestError("legacy-action-media")
            banners.append(asset_id)
        result["banner"] = _unique(banners)
        if set(result["banner"]) != set(embedded):
            raise ManifestError("legacy-action-media")
        return result
    if "hero" in result:
        candidates = _unique([*lead, *embedded])
        result["hero"] = candidates[0] if candidates else None
        embedded = candidates[1:]
    target_slot = {
        "service_section_overview": "works",
        "service_detail": "body",
        "article": "body",
        "contacts": "gallery",
        "reviews": "thumbnail",
        "actions": "banner",
    }.get(target_kind)
    if target_slot in result:
        result[target_slot] = _unique(embedded)
    return result


def _home_about(profile: dict[str, Any]) -> str:
    parts: list[str] = []
    advantages = profile["advantages"]
    if advantages:
        parts.append("<ul>" + "".join(
            f"<li>{_inline(value)}</li>" for value in advantages
        ) + "</ul>")
    for comparison in profile["comparisons"]:
        parts.append(f"<h2>{_inline(comparison['heading'])}</h2>")
        parts.append("<ul>" + "".join(
            f"<li>{_inline(value)}</li>"
            for value in comparison["bullets"]
        ) + "</ul>")
        parts.append(_paragraph(
            comparison["result_mark"] + " " + comparison["result_text"]
        ))
    for service in profile["services"]:
        parts.append(
            f'<p><a href="{escape(service["url"], quote=True)}">'
            f'{escape(service["label"], quote=False)}</a> — '
            f'{escape(service["caption"], quote=False)}</p>'
        )
    for group in profile["prices"]:
        parts.append(f"<h2>{escape(group['label'], quote=False)}</h2><ul>")
        for row in group["rows"]:
            parts.append(
                f'<li><a href="{escape(row["url"], quote=True)}">'
                f'{escape(row["label"], quote=False)}</a> — '
                f'{escape(row["price_text"], quote=False)}</li>'
            )
        parts.append("</ul>")
    return "".join(parts)


def _target_home_profile(
    source: dict[str, Any], profile: dict[str, Any]
) -> dict[str, Any]:
    image_assets, _ = _image_assets(source)

    def asset(image_id: str) -> str:
        value = image_assets.get(image_id)
        if value is None:
            raise ManifestError("legacy-home-profile")
        return value

    services = []
    for row in profile["services"]:
        value = {key: copy.deepcopy(item) for key, item in row.items() if key != "image_id"}
        value["asset_id"] = asset(row["image_id"])
        services.append(value)
    steps = [
        {"alt": row["alt"], "asset_id": asset(row["image_id"])}
        for row in profile["steps"]
    ]
    works = []
    for row in profile["works"]:
        value = {key: copy.deepcopy(item) for key, item in row.items() if key != "image_id"}
        if value["asset_id"] != asset(row["image_id"]):
            raise ManifestError("legacy-home-profile")
        works.append(value)
    return {
        "schema": "estakada.home-profile",
        "schema_version": 1,
        "hero": {"alt": profile["hero"]["alt"], "asset_id": asset(profile["hero"]["image_id"])},
        "advantages": copy.deepcopy(profile["advantages"]),
        "comparisons": copy.deepcopy(profile["comparisons"]),
        "steps": steps,
        "services": services,
        "prices": copy.deepcopy(profile["prices"]),
        "photo_strip": {"alt": profile["photo_strip"]["alt"], "asset_id": asset(profile["photo_strip"]["image_id"])},
        "works": works,
        "reviews": copy.deepcopy(profile["reviews"]),
    }


def _base(source: dict[str, Any], target_kind: str) -> dict[str, Any]:
    return {
        "seo": {
            "title": source["title"],
            "description": source["description"],
            "allow_index": source["indexing_allowed"],
        },
        "heading": {"h1": source["h1"]},
    }


def transform_legacy_payload(
    source: dict[str, Any],
    *,
    source_kind: str,
    page_url: str,
    profile: dict[str, Any] | None = None,
    page_name: str | None = None,
) -> dict[str, Any]:
    """Translate the one approved legacy snapshot shape into RB3 content v1."""

    if (
        not isinstance(source, dict)
        or source.get("schema_version") != "page-content-v1"
        or source.get("page_kind") != source_kind
    ):
        raise ManifestError("legacy-payload-envelope")
    target_kind = target_page_kind(source_kind)
    fields = _base(source, target_kind)
    if target_kind == "legacy_empty_main" and source["h1"] == "":
        if (
            not isinstance(page_name, str)
            or page_name == ""
            or page_name != page_name.strip()
        ):
            raise ManifestError("payload-h1")
        fields["heading"]["h1"] = page_name
    intro = source["intro_text"]
    body = source["main_text"]
    media = _media(source, target_kind, profile)

    if target_kind == "home":
        if profile is None:
            if (
                intro != ""
                or body != ""
                or source["price"] is not None
                or source["main_image"] is not None
                or source["preview_image"] is not None
                or source["embedded_images"] != []
            ):
                raise ManifestError("legacy-home-previous")
            fields.update({
                "lead": "", "service_refs": [], "process_steps": [],
                "about": "", "brand_refs": [], "review_refs": [],
                "contact_text": "", "media": media,
            })
        else:
            fields.update({
                "lead": _paragraph(profile["hero"]["lead"]),
                "service_refs": [],
                "process_steps": [{
                    "title": _plain(row["heading"]), "body": _plain(row["text"]),
                } for row in profile["steps"]],
                "about": _home_about(profile),
                "brand_refs": [],
                "review_refs": [],
                "contact_text": (
                    f'<p><a href="{escape(profile["reviews"]["url"], quote=True)}">'
                    f'{escape(profile["reviews"]["label"], quote=False)}</a></p>'
                ),
                "media": media,
                "home_profile": _target_home_profile(source, profile),
            })
    elif target_kind in {
        "services_master_catalog", "articles_catalog", "gallery_catalog",
        "gallery_album", "legacy_news_catalog",
    }:
        fields["intro"] = _join_rich(intro, body)
    elif target_kind == "service_catalog":
        fields.update({"intro": _join_rich(intro, body), "media": media})
    elif target_kind in {
        "service_section_overview", "article", "legacy_director_message",
        "legacy_news_article",
    }:
        fields.update({"intro": intro, "body": body, "media": media})
    elif target_kind in {"legacy_under_construction", "legacy_camera_schedule_text"}:
        fields.update({"intro": intro, "body": body})
    elif target_kind == "service_detail":
        fields.update({
            "intro": intro, "body": body,
            "price_rows": source["price"] or {"columns": [], "rows": []},
            "media": media,
        })
    elif target_kind == "contacts":
        fields.update({"intro": intro, "body": body, "media": media})
    elif target_kind == "reviews":
        if profile is None:
            raise ManifestError("legacy-profile-missing")
        fields.update({
            "intro": intro,
            "reviews": [{
                "title": row["title"], "https_url": row["url"], "caption": "",
            } for row in profile["videos"]],
            "media": media,
        })
    elif target_kind == "actions":
        if profile is None:
            raise ManifestError("legacy-profile-missing")
        fields.update({
            "intro": intro,
            "actions": [{
                "title": row["heading"], "body": _paragraph(row["text"]),
                "internal_url": page_url,
            } for row in profile["cards"]],
            "media": media,
        })
    elif target_kind == "legacy_partner_links":
        if profile is None:
            raise ManifestError("legacy-profile-missing")
        fields["links"] = [{
            "label": row["text"],
            "https_url": (
                "https://" + row["url"][7:]
                if row["url"].startswith("http://") else row["url"]
            ),
        } for row in profile["items"]]
    elif target_kind == "legacy_empty_main":
        pass
    else:
        raise ManifestError("legacy-payload-kind")

    target = {
        "schema": "estakada.page-content",
        "schema_version": 1,
        "kind": target_kind,
        "fields": fields,
    }
    validate_payload(target, target_kind)
    return target
