from __future__ import annotations

# Body must already be lowercased by the caller.
PLATFORM_SIGNATURES: dict[str, list[str]] = {
    "shopify": ["cdn.shopify.com", "myshopify.com", "shopify"],
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
