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
