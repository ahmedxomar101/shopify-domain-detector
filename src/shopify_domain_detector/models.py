from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Category(str, Enum):
    CONFIRMED_SHOPIFY = "confirmed-shopify"
    SHOPIFY_IN_HTML_ACTIVE = "shopify-in-html-active"
    SHOPIFY_IN_HTML_SUSPENDED = "shopify-in-html-suspended"
    REDIRECTS_TO_SHOPIFY = "redirects-to-shopify"
    NOT_SHOPIFY = "not-shopify"
    DEAD = "dead"
    RATE_LIMITED = "rate-limited"
    BOT_PROTECTED = "bot-protected"

    @property
    def is_healthy(self) -> bool:
        return self in _HEALTHY


_HEALTHY = frozenset(
    {Category.CONFIRMED_SHOPIFY, Category.SHOPIFY_IN_HTML_ACTIVE}
)


@dataclass(frozen=True)
class ProbeResult:
    """Raw outcome of fetching a domain's homepage (incl. error pages)."""

    domain: str
    status: int | str | None = None          # int code, "unreachable", or None
    platforms: tuple[str, ...] = ()
    suspended_shopify: bool = False
    rate_limited: bool = False
    resolved_domain: str | None = None
    server: str = ""
    html_size: int = 0
    shop_subdomains: tuple[str, ...] = ()    # candidate Shopify storefront hosts


@dataclass(frozen=True)
class DomainResult:
    """Final classification for one domain."""

    domain: str
    category: Category
    platform: str | None = None              # set for NOT_SHOPIFY
    discovered_domain: str | None = None     # host where Shopify was confirmed
    match_type: str = ""                     # apex | www | subdomain | redirect
    reason: str = ""                         # short human explanation
    status: int | str | None = None

    @property
    def is_shopify(self) -> bool:
        return self.category.is_healthy
