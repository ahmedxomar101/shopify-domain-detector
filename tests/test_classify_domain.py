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
    assert r.redirects_to == "realstore.com"


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
