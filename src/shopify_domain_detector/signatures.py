from __future__ import annotations

# Body must already be lowercased by the caller.
#
# All keywords must be technical markers Shopify's own platform emits (asset/
# backend domains, meta-tag names), never a bare English word — see v0.3.1,
# which dropped a bare "shopify" keyword after it false-positived on prose
# ("...Shopify sales data..."). "shopify-y" is the `<meta name="shopify-y">`
# tag Shopify's suspended-store template ("This store is unavailable") emits;
# it is not a phrase a page author would type, so it carries the same
# precision as the domain markers around it (v0.3.2).
PLATFORM_SIGNATURES: dict[str, list[str]] = {
    "shopify": ["cdn.shopify.com", "myshopify.com", "shopify-y"],
    "woocommerce": ["woocommerce", "wp-content/plugins/woocommerce"],
    "wordpress": ["wordpress", "wp-json", "wp-content"],
    "squarespace": ["squarespace", "sqsp.net"],
    "wix": ["wix", "wixsite", "parastorage.com"],
    "bigcommerce": ["bigcommerce", "bigcontent.io"],
    "prestashop": ["prestashop"],
    "drupal": ["drupal"],
    "joomla": ["joomla"],
    "webflow": ["webflow"],
    "kajabi": ["kajabi"],
    "ghost": ["ghost"],
    "ecwid": ["ecwid"],
    "opencart": ["opencart"],
    "nuvemshop": ["nuvemshop", "tiendanube"],
}

_SUSPENDED_TITLE = "this store is unavailable"


def detect_platforms(body: str) -> list[str]:
    """Return platforms whose signatures appear in a lowercased HTML body."""
    return [
        platform
        for platform, keywords in PLATFORM_SIGNATURES.items()
        if any(kw in body for kw in keywords)
    ]


def is_suspended(body: str) -> bool:
    return _SUSPENDED_TITLE in body


def has_shopify_strong(body: str) -> bool:
    """True iff the lowercased body contains 'shopify.com'.

    This is a stronger signal than a bare 'shopify' word: it matches
    cdn.shopify.com and *.myshopify.com but not a stray mention of 'shopify'
    with no domain, preventing false positives on status/blog pages."""
    return "shopify.com" in body
