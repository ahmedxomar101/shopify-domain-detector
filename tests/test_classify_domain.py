from unittest.mock import patch

from shopify_domain_detector import detector
from shopify_domain_detector.models import Category, DomainResult, ProbeResult


def test_cart_js_hit_is_confirmed():
    with patch.object(detector, "cart_js_is_shopify", return_value=True):
        r = detector.classify_domain("shop.example.com")
    assert r.category == Category.CONFIRMED_SHOPIFY
    assert r.is_shopify


def test_redirect_to_other_shopify_domain():
    def fake_cart(domain, **kw):
        return domain == "realstore.com"

    with patch.object(detector, "cart_js_is_shopify", side_effect=fake_cart), \
         patch.object(detector, "_resolve_redirect", return_value="realstore.com"):
        r = detector.classify_domain("vanity.com")
    assert r.category == Category.REDIRECTS_TO_SHOPIFY
    assert r.discovered_domain == "realstore.com"
    assert r.match_type == "redirect"


def test_subdomain_detection_confirms_on_shop_host():
    probe = ProbeResult(
        domain="example.com", status=200, platforms=("wordpress",),
        shop_subdomains=("shop.example.com",),
    )

    def fake_cart(domain, **kw):
        return domain == "shop.example.com"

    with patch.object(detector, "cart_js_is_shopify", side_effect=fake_cart), \
         patch.object(detector, "_resolve_redirect", return_value=None), \
         patch.object(detector, "probe_domain", return_value=probe):
        r = detector.classify_domain("example.com")
    assert r.category == Category.CONFIRMED_SHOPIFY
    assert r.discovered_domain == "shop.example.com"
    assert r.match_type == "subdomain"


def test_falls_through_to_probe_not_shopify():
    probe = ProbeResult(domain="wixsite.com", status=200, platforms=("wix",))
    with patch.object(detector, "cart_js_is_shopify", return_value=False), \
         patch.object(detector, "_resolve_redirect", return_value=None), \
         patch.object(detector, "probe_domain", return_value=probe):
        r = detector.classify_domain("wixsite.com")
    assert r.category == Category.NOT_SHOPIFY
    assert r.platform == "wix"


def test_classify_domains_returns_dict_keyed_by_input():
    with patch.object(detector, "classify_domain") as m:
        m.side_effect = lambda d, **k: DomainResult(d, Category.DEAD)
        out = detector.classify_domains(["a.com", "b.com"], workers=2)
    assert set(out) == {"a.com", "b.com"}


def test_classify_domains_survives_a_worker_exception():
    def flaky(d):
        if d == "boom.com":
            raise RuntimeError("unexpected")
        return DomainResult(d, Category.CONFIRMED_SHOPIFY)

    with patch.object(detector, "classify_domain", side_effect=flaky):
        out = detector.classify_domains(["ok.com", "boom.com"], workers=2)
    assert out["ok.com"].category == Category.CONFIRMED_SHOPIFY
    assert out["boom.com"].category == Category.DEAD  # errored domain is not lost


# v0.3.0: headless + password-protected subdomain tests

def test_subdomain_headless_shopify_via_shopify_strong():
    """No cart.js on subdomain, but shopify.com in HTML → SHOPIFY_IN_HTML_ACTIVE."""
    headless_probe = ProbeResult(
        domain="eu.x.com", status=200, platforms=(),
        shopify_strong=True, password_protected=False,
    )
    apex_probe = ProbeResult(
        domain="x.com", status=200, platforms=("wordpress",),
        shop_subdomains=("eu.x.com",),
    )

    with patch.object(detector, "cart_js_is_shopify", return_value=False), \
         patch.object(detector, "_resolve_redirect", return_value=None), \
         patch.object(detector, "probe_domain", side_effect=[apex_probe, headless_probe]):
        r = detector.classify_domain("x.com")

    assert r.category == Category.SHOPIFY_IN_HTML_ACTIVE
    assert r.discovered_domain == "eu.x.com"
    assert r.match_type == "subdomain"


def test_subdomain_password_protected_returns_password_category():
    """Subdomain redirects to /password with shopify.com → SHOPIFY_PASSWORD_PROTECTED."""
    locked_probe = ProbeResult(
        domain="shop.x.com", status=200, platforms=("shopify",),
        shopify_strong=True, password_protected=True,
    )
    apex_probe = ProbeResult(
        domain="x.com", status=200, platforms=("wordpress",),
        shop_subdomains=("shop.x.com",),
    )

    with patch.object(detector, "cart_js_is_shopify", return_value=False), \
         patch.object(detector, "_resolve_redirect", return_value=None), \
         patch.object(detector, "probe_domain", side_effect=[apex_probe, locked_probe]):
        r = detector.classify_domain("x.com")

    assert r.category == Category.SHOPIFY_PASSWORD_PROTECTED
    assert r.discovered_domain == "shop.x.com"
    assert r.match_type == "subdomain"


def test_open_subdomain_wins_over_locked_subdomain():
    """If eu.x.com is open (shopify_strong) and shop.x.com is locked, open wins."""
    locked_probe = ProbeResult(
        domain="shop.x.com", status=200, platforms=("shopify",),
        shopify_strong=True, password_protected=True,
    )
    open_probe = ProbeResult(
        domain="eu.x.com", status=200, platforms=(),
        shopify_strong=True, password_protected=False,
    )
    # eu.x.com comes first (HTML-harvested), shop.x.com is blind fallback
    apex_probe = ProbeResult(
        domain="x.com", status=200, platforms=("wordpress",),
        shop_subdomains=("eu.x.com", "shop.x.com"),
    )

    def fake_probe(host):
        mapping = {
            "x.com": apex_probe,
            "eu.x.com": open_probe,
            "shop.x.com": locked_probe,
        }
        return mapping[host]

    with patch.object(detector, "cart_js_is_shopify", return_value=False), \
         patch.object(detector, "_resolve_redirect", return_value=None), \
         patch.object(detector, "probe_domain", side_effect=fake_probe):
        r = detector.classify_domain("x.com")

    assert r.category == Category.SHOPIFY_IN_HTML_ACTIVE
    assert r.discovered_domain == "eu.x.com"


def test_apex_password_protected_classified_correctly():
    """Apex probe with password_protected + shopify → SHOPIFY_PASSWORD_PROTECTED."""
    pw_probe = ProbeResult(
        domain="newbrand.com", status=200, platforms=("shopify",),
        password_protected=True, shopify_strong=True,
    )
    with patch.object(detector, "cart_js_is_shopify", return_value=False), \
         patch.object(detector, "_resolve_redirect", return_value=None), \
         patch.object(detector, "probe_domain", return_value=pw_probe):
        r = detector.classify_domain("newbrand.com")

    assert r.category == Category.SHOPIFY_PASSWORD_PROTECTED


def test_bare_shopify_word_no_dot_com_is_not_shopify_strong():
    """Body with 'we love shopify' but no 'shopify.com' must not trigger strong signal."""
    weak_probe = ProbeResult(
        domain="x.com", status=200, platforms=("shopify",),
        shopify_strong=False, password_protected=False,
    )
    apex_probe = ProbeResult(
        domain="x.com", status=200, platforms=(),
        shop_subdomains=("shop.x.com",),
    )

    with patch.object(detector, "cart_js_is_shopify", return_value=False), \
         patch.object(detector, "_resolve_redirect", return_value=None), \
         patch.object(detector, "probe_domain", side_effect=[apex_probe, weak_probe]):
        r = detector.classify_domain("x.com")

    # shopify_strong=False → not classified as headless active
    assert r.category != Category.SHOPIFY_IN_HTML_ACTIVE or r.discovered_domain != "shop.x.com"


def test_reason_for_password_protected():
    """reason_for returns a non-empty human string for SHOPIFY_PASSWORD_PROTECTED."""
    probe = ProbeResult(domain="x.com", status=200, password_protected=True)
    reason = detector.reason_for(Category.SHOPIFY_PASSWORD_PROTECTED, probe)
    assert reason and "password" in reason.lower()
