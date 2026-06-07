from __future__ import annotations

import re

# Hosts like mystore.myshopify.com referenced anywhere in the page HTML.
_MYSHOPIFY_RE = re.compile(r"\b([a-z0-9][a-z0-9-]*\.myshopify\.com)\b")

# Common storefront subdomain labels for a brand whose apex is a marketing site.
_PREFIXES = ("shop", "store")


def _subdomain_hosts(body: str, base: str) -> list[str]:
    """Every *.<base> host that literally appears in the body, in document order.

    Matches any subdomain label (single or multi-level), e.g. eu.x.com,
    checkout.eu.x.com. Uses a compiled regex with the escaped base."""
    escaped = re.escape(base)
    pattern = re.compile(
        r"\b([a-z0-9][a-z0-9.-]*\." + escaped + r")\b"
    )
    return pattern.findall(body)


def _myshopify_hosts(body: str) -> list[str]:
    """<label>.myshopify.com hosts referenced in the body, in order."""
    return _MYSHOPIFY_RE.findall(body)


def extract_shop_hosts(body: str, base: str) -> list[str]:
    """Candidate Shopify storefront hosts to check for a domain.

    Pure: regex/string scan only, no network. `body` must be lowercased and
    `base` is the registrable domain.

    Order:
    1. HTML-harvested *.<base> hosts (document order, any subdomain label)
    2. *.myshopify.com refs from the body
    3. Blind shop.<base> / store.<base> fallbacks

    Deduped; excludes base itself and www.<base>."""
    excluded = {base, f"www.{base}"}
    blind = [f"{p}.{base}" for p in _PREFIXES]
    ordered = _subdomain_hosts(body, base) + _myshopify_hosts(body) + blind

    seen: set[str] = set()
    result: list[str] = []
    for host in ordered:
        if host in excluded or host in seen:
            continue
        seen.add(host)
        result.append(host)
    return result
