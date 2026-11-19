from __future__ import annotations

import json
import hashlib
import re
import unicodedata
import uuid
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any
from urllib.parse import unquote, urlsplit

import nh3

class ContentValidationError(ValueError):
    """A closed pages-owned content contract violation."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code



MIB = 1_048_576
RICH_TAGS = {"p", "br", "h2", "h3", "blockquote", "ul", "ol", "li", "strong", "em",
             "u", "s", "sub", "sup", "a", "table", "caption", "thead", "tbody", "tr", "th", "td"}
RICH_ATTRIBUTES = {"a": {"href", "title"}, "th": {"rowspan", "colspan", "scope"},
                   "td": {"rowspan", "colspan"}}
BASE = {"seo", "heading"}
FIELD_SETS = {
    "home": BASE | {"lead", "service_refs", "process_steps", "about", "brand_refs", "review_refs", "contact_text", "media"},
    "services_master_catalog": BASE | {"intro"}, "service_catalog": BASE | {"intro", "media"},
    "service_section_overview": BASE | {"intro", "body", "media"},
    "service_detail": BASE | {"intro", "body", "price_rows", "media"},
    "articles_catalog": BASE | {"intro"}, "article": BASE | {"intro", "body", "media"},
    "contacts": BASE | {"intro", "body", "media"}, "reviews": BASE | {"intro", "reviews", "media"},
    "actions": BASE | {"intro", "actions", "media"}, "gallery_catalog": BASE | {"intro"},
    "gallery_album": BASE | {"intro"}, "legacy_partner_links": BASE | {"links"},
    "legacy_director_message": BASE | {"intro", "body", "media"},
    "legacy_news_article": BASE | {"intro", "body", "media"},
    "legacy_empty_main": BASE, "legacy_news_catalog": BASE | {"intro"},
    "legacy_under_construction": BASE | {"intro", "body"},
    "legacy_camera_schedule_text": BASE | {"intro", "body"},
}
MEDIA_SLOTS = {
    "home": {"hero": 1, "service_cards": 12, "process": 12, "works": 32, "brand_logos": 20},
    "service_catalog": {"hero": 1}, "service_section_overview": {"hero": 1, "works": 32},
    "service_detail": {"hero": 1, "body": 32, "works": 32},
    "article": {"hero": 1, "body": 32, "works": 32}, "contacts": {"gallery": 5},
    "reviews": {"thumbnail": 32}, "actions": {"banner": 32},
    "legacy_director_message": {"hero": 1}, "legacy_news_article": {"hero": 1},
}


def canonical_payload_hash(payload: Any) -> str:
    """Hash the closed content envelope using the import/runtime JSON authority."""

    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContentValidationError("payload-json") from exc
    return hashlib.sha256(encoded).hexdigest()
RICH_BY_KIND = {
    "home": {"lead", "about", "contact_text"},
    "services_master_catalog": {"intro"}, "service_catalog": {"intro"},
    "service_section_overview": {"intro", "body"}, "service_detail": {"intro", "body"},
    "articles_catalog": {"intro"}, "article": {"intro", "body"}, "contacts": {"intro", "body"},
    "reviews": {"intro"}, "actions": {"intro"}, "gallery_catalog": {"intro"},
    "gallery_album": {"intro"}, "legacy_director_message": {"intro", "body"},
    "legacy_news_article": {"intro", "body"}, "legacy_news_catalog": {"intro"},
    "legacy_under_construction": {"intro", "body"}, "legacy_camera_schedule_text": {"intro", "body"},
}


def _closed(value: Any, fields: set[str], code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ContentValidationError(code)
    return value


def _plain(value: Any, cap: int, code: str, *, empty: bool = False) -> str:
    if (not isinstance(value, str) or (not empty and not value) or len(value) > cap
            or unicodedata.normalize("NFC", value) != value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ContentValidationError(code)
    return value


def _uuid(value: Any, code: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ContentValidationError(code) from exc
    if not isinstance(value, str) or str(parsed) != value:
        raise ContentValidationError(code)
    return value


def _internal(value: Any, code: str) -> str:
    value = _plain(value, 2048, code)
    try:
        parsed = urlsplit(value)
        decoded = unquote(parsed.path, errors="strict")
        decoded_query = unquote(parsed.query, errors="strict")
    except (UnicodeDecodeError, ValueError) as exc:
        raise ContentValidationError(code) from exc
    if (re.search(r"%(?![0-9A-Fa-f]{2})", value) or not value.startswith("/") or value.startswith("//")
            or parsed.scheme or parsed.netloc or parsed.fragment or parsed.query not in {"", "page=1", "page=2"}
            or "\\" in value or "\\" in decoded
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in decoded + decoded_query)
            or any(part in {".", ".."} for part in decoded.split("/"))):
        raise ContentValidationError(code)
    return value


def validate_https(value: Any, code: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    value = _plain(value, 2048, code)
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
        decoded = unquote(parsed.path, errors="strict")
        decoded_query = unquote(parsed.query, errors="strict")
    except (UnicodeDecodeError, ValueError) as exc:
        raise ContentValidationError(code) from exc
    labels = host.split(".") if host else []
    if (parsed.scheme != "https" or not host or not host.isascii() or len(labels) < 2
            or any(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) is None for label in labels)
            or port is not None or parsed.username is not None or parsed.password is not None
            or parsed.fragment or re.search(r"%(?![0-9A-Fa-f]{2})", value)
            or "\\" in decoded or any(
                char.isspace() or ord(char) < 32 or ord(char) == 127
                for char in decoded + decoded_query
            )):
        raise ContentValidationError(code)
    return value


class _RichInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.nodes = 0
        self.visible = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.nodes += 1
        if tag != "br": self.depth += 1
        if self.depth > 32 or self.nodes > 20_000: raise ContentValidationError("rich-shape")
        values = dict(attrs)
        if tag == "a" and "href" in values:
            href = values["href"]
            if href is None: raise ContentValidationError("rich-href")
            validate_https(href, "rich-href") if href.startswith("https://") else _internal(href, "rich-href")
        if tag == "a" and "title" in values:
            _plain(values["title"], 500, "rich-title", empty=True)
        for name in ("rowspan", "colspan"):
            if name in values and re.fullmatch(r"(?:[1-9]|[1-9][0-9]|100)", values[name] or "") is None:
                raise ContentValidationError("rich-table-attribute")
        if "scope" in values and values["scope"] not in {"row", "col"}: raise ContentValidationError("rich-table-attribute")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs); self.depth -= 1

    def handle_endtag(self, tag: str) -> None:
        self.depth -= 1
        if self.depth < 0: raise ContentValidationError("rich-shape")

    def handle_data(self, data: str) -> None:
        if data:
            self.nodes += 1
            if self.nodes > 20_000: raise ContentValidationError("rich-shape")
        self.visible += len(data)


def _rich(value: Any) -> tuple[int, int]:
    value = _plain(value, MIB, "rich", empty=True)
    if len(value.encode("utf-8")) > MIB: raise ContentValidationError("rich-bytes")
    cleaned = nh3.clean(value, tags=RICH_TAGS, attributes=RICH_ATTRIBUTES,
                        url_schemes={"https"}, link_rel=None, strip_comments=True)
    if cleaned != value or nh3.clean(cleaned, tags=RICH_TAGS, attributes=RICH_ATTRIBUTES,
                                     url_schemes={"https"}, link_rel=None, strip_comments=True) != cleaned:
        raise ContentValidationError("rich-noncanonical")
    inspector = _RichInspector(); inspector.feed(value); inspector.close()
    if inspector.depth != 0: raise ContentValidationError("rich-shape")
    return inspector.visible, inspector.nodes


def _uuid_list(value: Any, cap: int, code: str) -> list[str]:
    if not isinstance(value, list) or len(value) > cap: raise ContentValidationError(code)
    result = [_uuid(item, code) for item in value]
    if len(result) != len(set(result)): raise ContentValidationError(code)
    return result


def _price(value: Any) -> None:
    value = _closed(value, {"columns", "rows"}, "price-shape")
    columns, rows = value["columns"], value["rows"]
    if not isinstance(columns, list) or len(columns) > 32 or not isinstance(rows, list) or len(rows) > 500:
        raise ContentValidationError("price-cap")
    column_ids: set[str] = set()
    for column in columns:
        column = _closed(column, {"id", "label"}, "price-column")
        identifier = _uuid(column["id"], "price-column-id"); _plain(column["label"], 500, "price-label")
        if identifier in column_ids: raise ContentValidationError("price-column-id")
        column_ids.add(identifier)
    row_ids: set[str] = set(); total_cells = 0
    for row in rows:
        row = _closed(row, {"id", "label", "cells"}, "price-row")
        identifier = _uuid(row["id"], "price-row-id"); _plain(row["label"], 500, "price-label")
        if identifier in row_ids or identifier in column_ids or not isinstance(row["cells"], list):
            raise ContentValidationError("price-row-id")
        row_ids.add(identifier); seen: set[str] = set(); total_cells += len(row["cells"])
        if total_cells > 10_000: raise ContentValidationError("price-cap")
        for cell in row["cells"]:
            if not isinstance(cell, dict) or cell.get("kind") not in {"text", "amount"}: raise ContentValidationError("price-cell")
            fields = {"column_id", "kind", "text"} if cell["kind"] == "text" else {"column_id", "kind", "amount", "from"}
            cell = _closed(cell, fields, "price-cell")
            column = _uuid(cell["column_id"], "price-cell-column")
            if column not in column_ids or column in seen: raise ContentValidationError("price-cell-column")
            seen.add(column)
            if cell["kind"] == "text": _plain(cell["text"], 1000, "price-text", empty=True)
            else:
                if not isinstance(cell["from"], bool) or not isinstance(cell["amount"], str): raise ContentValidationError("price-amount")
                if re.fullmatch(r"(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,2})?", cell["amount"]) is None: raise ContentValidationError("price-amount")
                try: amount = Decimal(cell["amount"])
                except InvalidOperation as exc: raise ContentValidationError("price-amount") from exc
                if amount > Decimal("999999999.99"): raise ContentValidationError("price-amount")


def validate_payload(payload: Any, expected_kind: str) -> dict[str, list[str]]:
    payload = _closed(payload, {"schema", "schema_version", "kind", "fields"}, "payload-envelope")
    if (payload["schema"] != "estakada.page-content"
            or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
            or payload["kind"] != expected_kind or expected_kind not in FIELD_SETS):
        raise ContentValidationError("payload-kind")
    if len(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) > MIB:
        raise ContentValidationError("payload-bytes")
    fields = _closed(payload["fields"], FIELD_SETS[expected_kind], "payload-fields")
    seo = _closed(fields["seo"], {"title", "description", "allow_index"}, "payload-seo")
    _plain(seo["title"], 255, "payload-title"); _plain(seo["description"], 1000, "payload-description", empty=True)
    if not isinstance(seo["allow_index"], bool): raise ContentValidationError("payload-index")
    heading = _closed(fields["heading"], {"h1"}, "payload-heading"); _plain(heading["h1"], 255, "payload-h1")
    visible = nodes = 0
    for field in RICH_BY_KIND.get(expected_kind, set()):
        field_visible, field_nodes = _rich(fields[field]); visible += field_visible; nodes += field_nodes
    for field, cap in (("service_refs", 12), ("brand_refs", 20), ("review_refs", 12)):
        if field in fields: _uuid_list(fields[field], cap, f"payload-{field}")
    if "process_steps" in fields:
        if not isinstance(fields["process_steps"], list) or len(fields["process_steps"]) > 12: raise ContentValidationError("payload-process")
        for step in fields["process_steps"]:
            step = _closed(step, {"title", "body"}, "payload-process")
            _plain(step["title"], 500, "payload-process"); _plain(step["body"], 4000, "payload-process", empty=True)
    if "actions" in fields:
        if not isinstance(fields["actions"], list) or len(fields["actions"]) > 32: raise ContentValidationError("payload-actions")
        for action in fields["actions"]:
            action = _closed(action, {"title", "body", "internal_url"}, "payload-action")
            _plain(action["title"], 500, "payload-action")
            action_visible, action_nodes = _rich(action["body"]); visible += action_visible; nodes += action_nodes
            _internal(action["internal_url"], "payload-action")
    if "reviews" in fields:
        if not isinstance(fields["reviews"], list) or len(fields["reviews"]) > 32: raise ContentValidationError("payload-reviews")
        for review in fields["reviews"]:
            review = _closed(review, {"title", "https_url", "caption"}, "payload-review")
            _plain(review["title"], 500, "payload-review"); validate_https(review["https_url"], "payload-review"); _plain(review["caption"], 1000, "payload-review", empty=True)
    if "links" in fields:
        if not isinstance(fields["links"], list) or len(fields["links"]) > 64: raise ContentValidationError("payload-links")
        for link in fields["links"]:
            link = _closed(link, {"label", "https_url"}, "payload-link")
            _plain(link["label"], 500, "payload-link"); validate_https(link["https_url"], "payload-link")
    if "price_rows" in fields: _price(fields["price_rows"])
    if visible > 200_000 or nodes > 20_000: raise ContentValidationError("payload-visible-shape")
    media: dict[str, list[str]] = {}
    if "media" in fields:
        raw = _closed(fields["media"], set(MEDIA_SLOTS[expected_kind]), "payload-media")
        for slot, cap in MEDIA_SLOTS[expected_kind].items():
            value = raw[slot]
            if slot == "hero":
                media[slot] = [] if value is None else [_uuid(value, "payload-media")]
            else:
                media[slot] = _uuid_list(value, cap, "payload-media")
        if sum(map(len, media.values())) > 64: raise ContentValidationError("payload-media-cap")
        if expected_kind == "reviews" and len(media["thumbnail"]) > len(fields["reviews"]): raise ContentValidationError("payload-media-cap")
        if expected_kind == "actions" and len(media["banner"]) > len(fields["actions"]): raise ContentValidationError("payload-media-cap")
    return media
