"""The sole closed nh3 call. Never pass raw/unvalidated user HTML here."""
import nh3
from .policy_constants import TAGS, attributes_for


def restricted_clean(approved_html: str) -> str:
    # Affected upstream CSS/SVG pathways are deliberately unreachable.
    # No caller kwargs, wildcard attributes, style or filter_style_properties.
    return nh3.clean(approved_html, tags=set(TAGS),
                     attributes={tag: set(attributes_for(tag)) for tag in TAGS},
                     url_schemes={'http', 'https'}, link_rel=None)
