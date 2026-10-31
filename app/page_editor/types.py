"""Closed immutable values crossing the pure policy boundary."""
from dataclasses import dataclass


class PolicyError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class ControlledUnsupported(PolicyError):
    """Recognised integration not implemented; never a successful admission."""


@dataclass(frozen=True)
class ProtectedBinding:
    marker_id: str
    parent_id: str
    slot_before_id: str
    slot_after_id: str
    image_id: str
    asset_id: str
    alt: str
    alignment: str
    width_px: int | None
    height_px: int | None
    fingerprint: str


@dataclass(frozen=True)
class ProtectedContext:
    nodes: tuple[ProtectedBinding, ...] = ()


@dataclass(frozen=True)
class PolicyWarning:
    code: str
    field: str


@dataclass(frozen=True)
class Metrics:
    source_bytes: int
    text_codepoints: int
    node_count: int
    max_depth: int


@dataclass(frozen=True)
class Anchor:
    label: str
    field: str


@dataclass(frozen=True)
class AnchorLink:
    field: str
    anchor: str
    href: str


@dataclass(frozen=True)
class PendingAsset:
    image_id: str
    asset_id: str


@dataclass(frozen=True)
class URLContext:
    page_path: str
    origin: str
    private_roots: tuple[str, ...] = ('/manage/',)


@dataclass(frozen=True)
class TableCapability:
    table_index: int
    row_count: int
    cell_count: int
    nested: bool
    rich_widget: bool
    reason: str
    virtual_slots: int | None


@dataclass(frozen=True)
class NormalizationResult:
    policy_version: str
    html: str
    changed: bool
    warnings: tuple[PolicyWarning, ...]
    source_sha256: str
    normalized_sha256: str
    metrics: Metrics
    anchors: tuple[Anchor, ...]
    anchor_links: tuple[AnchorLink, ...]
    pending_assets: tuple[PendingAsset, ...]
    table_capabilities: tuple[TableCapability, ...] = ()
    ui_table_slots_used: int = 0
