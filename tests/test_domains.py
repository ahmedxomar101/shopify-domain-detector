import pytest

from shopify_domain_detector.domains import base_domain, is_same_domain, normalize


@pytest.mark.parametrize("raw,expected", [
    ("https://Example.com/", "example.com"),
    ("http://www.shop.example.com", "www.shop.example.com"),
    ("  EXAMPLE.com/path/  ", "example.com"),
    ("https://example.com/collections/all?x=1#f", "example.com"),
    ("example.com", "example.com"),
])
def test_normalize_strips_scheme_lowercases_trims(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize("domain,expected", [
    ("example.com", "example.com"),
    ("www.example.com", "example.com"),
    ("shop.example.com", "example.com"),
    ("a.b.example.co.uk", "example.co.uk"),
    ("store.example.com.au", "example.com.au"),
    ("example.com.br", "example.com.br"),
    ("localhost", "localhost"),
])
def test_base_domain_handles_cctlds(domain, expected):
    assert base_domain(domain) == expected


def test_is_same_domain_ignores_subdomain_and_www():
    assert is_same_domain("www.example.com", "shop.example.com")
    assert not is_same_domain("example.com", "other.com")
