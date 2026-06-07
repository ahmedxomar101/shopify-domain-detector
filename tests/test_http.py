from shopify_domain_detector.http import USER_AGENT, build_request


def test_build_request_sets_browser_headers():
    req = build_request("https://example.com/cart.js")
    assert req.get_header("User-agent") == USER_AGENT
    assert "text/html" in req.get_header("Accept")
    assert req.full_url == "https://example.com/cart.js"
