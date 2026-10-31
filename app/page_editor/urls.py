"""Literal safe URL checks and explicit same-Page anchor bindings; no fetch."""
import ipaddress
import re
import unicodedata
from urllib.parse import quote, unquote, urlsplit, urljoin
from .policy_constants import FIELDS
from .types import AnchorLink, ControlledUnsupported, PolicyError, URLContext


def anchor_label(value):
    if type(value) is not str or not value or any(ord(char)<32 or ord(char)==127 for char in value):
        raise PolicyError('ANCHOR_INVALID')
    return unicodedata.normalize('NFC', value)


def _decoded_path(value):
    # Inspection only: never rewrite a safe literal path to a decoded URL.
    inspected=value
    for _ in range(len(value)+1):
        try:next_value=unquote(inspected, encoding='utf-8', errors='strict')
        except UnicodeError:raise PolicyError('URL_INVALID') from None
        if next_value==inspected:break
        inspected=next_value
    return inspected


def _origin(parts):
    if parts.scheme.lower() not in ('http','https') or not parts.netloc or parts.username is not None or parts.password is not None:
        raise PolicyError('URL_UNSUPPORTED')
    host=parts.hostname
    if not host or '%' in host:raise PolicyError('URL_INVALID')
    port=parts.port
    if ':' in host:
        host=ipaddress.IPv6Address(host).compressed
    else:
        # Both the stdlib IDNA and a non-transitional Unicode form must agree.
        # Divergent mappings need a browser/IDNA context this pure cohort does
        # not pretend to possess (e.g. IDNA2003 vs browser treatment of sharp-s).
        ascii_host=host.encode('idna').decode('ascii').lower()
        labels=ascii_host.rstrip('.').split('.')
        if len(ascii_host)>253 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) for label in labels):raise PolicyError('URL_INVALID')
        if not host.isascii():
            mapped=unicodedata.normalize('NFC',unicodedata.normalize('NFKC',host).lower())
            nontransitional='.'.join(label if label.isascii() else 'xn--'+label.encode('punycode').decode('ascii') for label in mapped.split('.'))
            if ascii_host!=nontransitional:raise ControlledUnsupported('IDN_ORIGIN_CONTEXT_REQUIRED')
        host=ascii_host
    return parts.scheme.lower(),host,port if port is not None else (443 if parts.scheme.lower()=='https' else 80)


def _resolved_path(path_value, base_path=None):
    inspected=_decoded_path(path_value)
    if '\\' in inspected or inspected.startswith('//') or any(ord(char)<32 or ord(char)==127 for char in inspected):raise PolicyError('URL_UNSUPPORTED')
    if inspected.startswith('/') or base_path is None:segments=[]
    else:
        segments=[part for part in _decoded_path(base_path).split('/') if part]
        if not base_path.endswith('/') and segments:segments.pop()
    for segment in inspected.split('/'):
        if segment in ('','.'):continue
        if segment=='..':
            if not segments:raise PolicyError('URL_OUTSIDE_ROOT')
            segments.pop()
        else:segments.append(segment)
    return '/'+('/'.join(segments))


def _private(path_value, roots):
    return any(path_value==root.rstrip('/') or path_value.startswith(root.rstrip('/')+'/') for root in roots)


def validate_context(context):
    if not isinstance(context,URLContext) or type(context.origin) is not str or type(context.page_path) is not str or type(context.private_roots) is not tuple:
        raise PolicyError('URL_CONTEXT_INVALID')
    if not context.page_path.startswith('/') or context.page_path.startswith('//') or any(char.isspace() or ord(char)<32 or ord(char)==127 for char in context.page_path+context.origin) or '\\' in context.page_path+context.origin:
        raise PolicyError('URL_CONTEXT_INVALID')
    try:
        parts=urlsplit(context.origin);page=urlsplit(context.page_path)
        if parts.path not in ('','/') or parts.query or parts.fragment or page.scheme or page.netloc or page.fragment:raise PolicyError('URL_CONTEXT_INVALID')
        identity=_origin(parts)
        roots=[]
        for root in context.private_roots:
            if type(root) is not str or not root.startswith('/') or root.startswith('//') or any(char.isspace() for char in root):raise PolicyError('URL_CONTEXT_INVALID')
            components=urlsplit(root)
            if components.query or components.fragment or components.scheme or components.netloc:raise PolicyError('URL_CONTEXT_INVALID')
            normalized=_resolved_path(root)
            if normalized=='/' or normalized!=root.rstrip('/'):raise PolicyError('URL_CONTEXT_INVALID')
            roots.append(normalized)
        if '/manage' not in roots:raise PolicyError('URL_CONTEXT_INVALID')
        path_value=_resolved_path(page.path)
        if _private(path_value,roots):raise PolicyError('URL_CONTEXT_INVALID')
    except ControlledUnsupported:raise
    except (ValueError,UnicodeError):raise PolicyError('URL_CONTEXT_INVALID') from None
    return identity,tuple(roots)


def safe_url(value, *, context=None):
    if type(value) is not str or not value or len(value)>2048:
        raise PolicyError('URL_INVALID')
    if any(char.isspace() or ord(char)<32 or ord(char)==127 for char in value) or '\\' in value:
        raise PolicyError('URL_UNSUPPORTED')
    if value.startswith('//'):raise PolicyError('URL_UNSUPPORTED')
    try:
        parts=urlsplit(value)
        context_identity,roots=validate_context(context) if context is not None else (None,('/manage',))
        identity=None
        if parts.scheme:
            identity=_origin(parts)
        elif not value.startswith(('/', '#')):
            if context is None:raise ControlledUnsupported('RELATIVE_URL_CONTEXT_REQUIRED')
        if not parts.scheme and not value.startswith('#'):
            # Resolve only for admission. Preserve the literal href and its
            # cross-page fragment; no Page registry or fragment rewrite exists.
            base_path=urlsplit(context.page_path).path if context is not None else None
            checked_path=_resolved_path(parts.path,base_path)
            if _private(checked_path,roots):raise PolicyError('URL_PRIVATE_TARGET')
            if context is not None:
                resolved=urlsplit(urljoin(context.origin.rstrip('/')+context.page_path,value))
                if _origin(resolved)!=context_identity:raise PolicyError('URL_OUTSIDE_ROOT')
                if _private(_resolved_path(resolved.path),roots):raise PolicyError('URL_PRIVATE_TARGET')
        elif identity is not None and context_identity is not None and identity==context_identity:
            if _private(_resolved_path(parts.path or '/'),roots):raise PolicyError('URL_PRIVATE_TARGET')
    except PolicyError:
        raise
    except (ValueError,UnicodeError):
        raise PolicyError('URL_INVALID') from None
    return value


def normalize_link(attributes, *, field, context=None):
    result=dict(attributes);link=None
    href=result.get('href')
    has_field='data-es-target-field' in result
    has_anchor='data-es-target-anchor' in result
    if has_field!=has_anchor:raise PolicyError('ANCHOR_BINDING_INVALID')
    # Validate all non-URL attributes before a missing relative-path context can
    # yield ControlledUnsupported. Unsupported is never an unsafe-input oracle.
    target=result.get('target')
    if target is not None and target not in ('_self','_blank'):raise PolicyError('LINK_TARGET_INVALID')
    if 'title' in result:
        title=result['title']
        if len(title)>300 or any(ord(char)<32 or ord(char)==127 for char in title):raise PolicyError('LINK_TITLE_INVALID')
    relations=set(result.get('rel','').split())
    if not relations.issubset({'noopener','noreferrer','nofollow'}):raise PolicyError('LINK_REL_INVALID')
    if target=='_blank':relations.add('noopener')
    if relations:result['rel']=' '.join(sorted(relations))
    else:result.pop('rel',None)
    if href is not None:
        safe_url(href,context=context)
        if href.startswith('#'):
            fragment=href[1:]
            if re.search(r'%(?![0-9A-Fa-f]{2})',fragment):raise PolicyError('ANCHOR_INVALID')
            try:label=anchor_label(unquote(fragment,encoding='utf-8',errors='strict'))
            except UnicodeError:raise PolicyError('ANCHOR_INVALID') from None
            target=result.get('data-es-target-field',field)
            if target not in FIELDS:raise PolicyError('ANCHOR_BINDING_INVALID')
            if has_anchor and anchor_label(result['data-es-target-anchor'])!=label:raise PolicyError('ANCHOR_BINDING_INVALID')
            result.update({'href':'#'+quote(label,safe=''), 'data-es-target-field':target,'data-es-target-anchor':label})
            link=AnchorLink(target,label,result['href'])
        elif has_field:
            raise PolicyError('ANCHOR_BINDING_INVALID')
    elif has_field:raise PolicyError('ANCHOR_BINDING_INVALID')
    return result,link
