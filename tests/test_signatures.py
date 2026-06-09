from shopify_domain_detector.signatures import detect_platforms, has_shopify_strong, is_suspended


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


def test_detect_platforms_ignores_bare_shopify_word():
    """v0.3.1: a bare 'shopify' mention in prose (e.g. a blog citing
    'Shopify sales data') must NOT flag the page as a Shopify store. Only
    asset/backend domains (cdn.shopify.com / myshopify.com) count."""
    body = "today shopify sales data shows a rise in camping gear".lower()
    assert "shopify" not in detect_platforms(body)


def test_detect_platforms_myshopify_backend():
    body = '<script>domain:"olivers-real-food.myshopify.com"</script>'.lower()
    assert "shopify" in detect_platforms(body)


def test_suspended_detection():
    assert is_suspended("Sorry, this store is unavailable.".lower())
    assert not is_suspended("welcome to our shop".lower())


# v0.3.0: has_shopify_strong — "shopify.com" substring test

def test_has_shopify_strong_cdn_shopify_com():
    assert has_shopify_strong("cdn.shopify.com") is True


def test_has_shopify_strong_myshopify_com():
    assert has_shopify_strong("mystore.myshopify.com") is True


def test_has_shopify_strong_false_for_bare_shopify_word():
    """'shopify' without '.com' must NOT match — avoids false positives."""
    assert has_shopify_strong("we love shopify and use it") is False


def test_has_shopify_strong_false_for_empty():
    assert has_shopify_strong("") is False
