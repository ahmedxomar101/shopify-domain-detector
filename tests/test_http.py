import ssl
from types import SimpleNamespace
import urllib.error
from unittest.mock import patch

from shopify_domain_detector import http
from shopify_domain_detector.http import USER_AGENT, build_request


def test_build_request_sets_browser_headers():
    req = build_request("https://example.com/cart.js")
    assert req.get_header("User-agent") == USER_AGENT
    assert "text/html" in req.get_header("Accept")
    assert req.full_url == "https://example.com/cart.js"


def test_open_url_falls_back_to_unverified_on_wrapped_cert_error():
    """CPython wraps cert failures in URLError(reason=SSLCertVerificationError);
    open_url must still fall back to an unverified read."""
    seen = []

    # Patches guarded_opener, not urlopen: open_url stopped calling the
    # module-level urlopen when the redirect guard landed, because the default
    # opener follows redirects unchecked. Patching the old seam would have gone
    # green against code that never runs.
    def fake_opener(context=None):
        seen.append(context.verify_mode)
        if context.verify_mode != ssl.CERT_NONE:
            raise urllib.error.URLError(ssl.SSLCertVerificationError("bad cert"))
        return SimpleNamespace(open=lambda req, timeout=None: "OK")

    with patch.object(http, "guarded_opener", side_effect=fake_opener), \
         patch.object(http, "assert_target_is_public"):
        result = http.open_url(build_request("https://x.com"), 5)
    assert result == "OK"
    assert seen[0] != ssl.CERT_NONE and seen[-1] == ssl.CERT_NONE


def test_open_url_reraises_non_cert_urlerror():
    def fake_opener(context=None):
        raise urllib.error.URLError("connection refused")

    with patch.object(http, "guarded_opener", side_effect=fake_opener), \
         patch.object(http, "assert_target_is_public"):
        try:
            http.open_url(build_request("https://x.com"), 5)
            raised = False
        except urllib.error.URLError:
            raised = True
    assert raised
