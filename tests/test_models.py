from shopify_domain_detector.models import Category, DomainResult, ProbeResult


def test_category_values_are_stable_slugs():
    assert Category.CONFIRMED_SHOPIFY.value == "confirmed-shopify"
    assert Category.SHOPIFY_IN_HTML_ACTIVE.value == "shopify-in-html-active"
    assert Category.REDIRECTS_TO_SHOPIFY.value == "redirects-to-shopify"
    assert Category.NOT_SHOPIFY.value == "not-shopify"


def test_healthy_membership():
    assert Category.CONFIRMED_SHOPIFY.is_healthy
    assert Category.SHOPIFY_IN_HTML_ACTIVE.is_healthy
    assert not Category.NOT_SHOPIFY.is_healthy
    assert not Category.SHOPIFY_IN_HTML_SUSPENDED.is_healthy


def test_domain_result_is_shopify_property():
    r = DomainResult(domain="x.com", category=Category.CONFIRMED_SHOPIFY)
    assert r.is_shopify is True
    r2 = DomainResult(domain="x.com", category=Category.NOT_SHOPIFY, platform="wix")
    assert r2.is_shopify is False


def test_probe_result_defaults():
    p = ProbeResult(domain="x.com")
    assert p.status is None
    assert p.platforms == ()
    assert p.suspended_shopify is False
    assert p.rate_limited is False
    assert p.shop_subdomains == ()


def test_domain_result_v2_fields_default():
    r = DomainResult(domain="x.com", category=Category.NOT_SHOPIFY)
    assert r.discovered_domain is None
    assert r.match_type == ""
    assert r.reason == ""


def test_domain_result_discovered_domain_and_match_type():
    r = DomainResult(
        domain="x.com",
        category=Category.CONFIRMED_SHOPIFY,
        discovered_domain="shop.x.com",
        match_type="subdomain",
        reason="cart.js on subdomain (shop.x.com)",
    )
    assert r.discovered_domain == "shop.x.com"
    assert r.match_type == "subdomain"
    assert r.reason.startswith("cart.js")
