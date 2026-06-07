from shopify_domain_detector.subdomains import extract_shop_hosts


def test_extracts_body_hosts_and_blind_fallbacks():
    body = (
        "<a href='https://shop.example.com/products'>shop</a> "
        "<script src='https://mystore.myshopify.com/x.js'></script>"
    ).lower()
    hosts = extract_shop_hosts(body, "example.com")

    assert "shop.example.com" in hosts
    assert "mystore.myshopify.com" in hosts
    assert "store.example.com" in hosts  # blind fallback always included


def test_excludes_base_and_www():
    body = "https://example.com https://www.example.com".lower()
    hosts = extract_shop_hosts(body, "example.com")
    assert "example.com" not in hosts
    assert "www.example.com" not in hosts


def test_no_duplicates_and_body_hosts_first():
    body = (
        "shop.example.com shop.example.com mystore.myshopify.com"
    ).lower()
    hosts = extract_shop_hosts(body, "example.com")
    assert len(hosts) == len(set(hosts))
    # body-discovered hosts precede blind store. fallback
    assert hosts.index("shop.example.com") < hosts.index("store.example.com")


def test_empty_body_still_returns_blind_candidates():
    hosts = extract_shop_hosts("", "brand.co.uk")
    assert hosts == ["shop.brand.co.uk", "store.brand.co.uk"]


# v0.3.0: arbitrary subdomains harvested from body HTML

def test_arbitrary_subdomain_eu_harvested_from_body():
    """eu.x.com appearing in body HTML must be extracted (not just shop./store.)."""
    body = "<a href='https://eu.x.com/products'>EU store</a>".lower()
    hosts = extract_shop_hosts(body, "x.com")
    assert "eu.x.com" in hosts


def test_arbitrary_subdomain_tienda_harvested_from_body():
    body = "visit tienda.brand.co for spanish store".lower()
    hosts = extract_shop_hosts(body, "brand.co")
    assert "tienda.brand.co" in hosts


def test_html_harvested_hosts_come_before_blind_fallbacks():
    """eu.x.com (HTML-harvested) must appear before shop.x.com (blind) in results."""
    body = "https://eu.x.com/products something else".lower()
    hosts = extract_shop_hosts(body, "x.com")
    assert "eu.x.com" in hosts
    assert hosts.index("eu.x.com") < hosts.index("shop.x.com")


def test_html_harvested_before_myshopify():
    """HTML-harvested *.base subdomain appears before myshopify.com refs."""
    body = "eu.x.com and mystore.myshopify.com".lower()
    hosts = extract_shop_hosts(body, "x.com")
    assert hosts.index("eu.x.com") < hosts.index("mystore.myshopify.com")


def test_multilabel_subdomain_harvested():
    """Multi-label subdomains like a.b.x.com are valid and harvested."""
    body = "checkout.eu.x.com is our storefront".lower()
    hosts = extract_shop_hosts(body, "x.com")
    assert "checkout.eu.x.com" in hosts


def test_base_and_www_always_excluded_even_if_in_body():
    body = "x.com and www.x.com are the same site".lower()
    hosts = extract_shop_hosts(body, "x.com")
    assert "x.com" not in hosts
    assert "www.x.com" not in hosts


def test_myshopify_comes_before_blind_fallbacks():
    """*.myshopify.com refs come before blind shop./store. candidates."""
    body = "mystore.myshopify.com is used".lower()
    hosts = extract_shop_hosts(body, "x.com")
    assert "mystore.myshopify.com" in hosts
    assert hosts.index("mystore.myshopify.com") < hosts.index("shop.x.com")
