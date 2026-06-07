from shopify_domain_detector.signatures import detect_platforms, is_suspended


def test_detects_shopify_signature():
    body = '<script src="https://cdn.shopify.com/s/files/1/app.js"></script>'.lower()
    assert "shopify" in detect_platforms(body)


def test_detects_multiple_platforms():
    body = "woocommerce wp-content/plugins/woocommerce kajabi".lower()
    found = detect_platforms(body)
    assert "woocommerce" in found
    assert "kajabi" in found


def test_no_signature_returns_empty():
    assert detect_platforms("plain html nothing here") == []


def test_suspended_detection():
    assert is_suspended("Sorry, this store is unavailable.".lower())
    assert not is_suspended("welcome to our shop".lower())
