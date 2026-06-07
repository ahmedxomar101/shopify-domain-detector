from shopify_domain_detector.detector import categorize
from shopify_domain_detector.models import Category, ProbeResult


def _probe(**kw):
    return ProbeResult(domain="x.com", **kw)


def test_rate_limited_wins():
    cat, plat = categorize(_probe(status=429, rate_limited=True, platforms=("shopify",)))
    assert cat == Category.RATE_LIMITED and plat is None


def test_bot_protected_is_403_with_no_platforms():
    cat, plat = categorize(_probe(status=403, platforms=()))
    assert cat == Category.BOT_PROTECTED


def test_403_with_platform_is_not_bot_protected():
    cat, plat = categorize(_probe(status=403, platforms=("shopify",)))
    assert cat == Category.SHOPIFY_IN_HTML_SUSPENDED


def test_active_shopify_requires_200_and_not_suspended():
    cat, plat = categorize(_probe(status=200, platforms=("shopify",)))
    assert cat == Category.SHOPIFY_IN_HTML_ACTIVE


def test_suspended_shopify():
    cat, plat = categorize(_probe(status=200, platforms=("shopify",), suspended_shopify=True))
    assert cat == Category.SHOPIFY_IN_HTML_SUSPENDED


def test_shopify_with_4xx_is_suspended():
    cat, plat = categorize(_probe(status=404, platforms=("shopify",)))
    assert cat == Category.SHOPIFY_IN_HTML_SUSPENDED


def test_unreachable_is_dead():
    cat, plat = categorize(_probe(status="unreachable", platforms=()))
    assert cat == Category.DEAD


def test_not_shopify_records_other_platform():
    cat, plat = categorize(_probe(status=200, platforms=("wix",)))
    assert cat == Category.NOT_SHOPIFY and plat == "wix"


def test_not_shopify_no_platform():
    cat, plat = categorize(_probe(status=200, platforms=()))
    assert cat == Category.NOT_SHOPIFY and plat is None
