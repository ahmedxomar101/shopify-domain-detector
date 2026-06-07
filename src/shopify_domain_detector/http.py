from __future__ import annotations

import ssl
import urllib.error
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 10
PROBE_TIMEOUT = 15


def _verified_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def _unverified_context() -> ssl.SSLContext:
    # Used ONLY as a fallback to *read public HTML* from sites with broken/
    # expired certs, purely for platform classification. No data is sent, no
    # credentials are exchanged. Verification is attempted first (see open_url).
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def build_request(url: str) -> urllib.request.Request:
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "text/html,application/xhtml+xml,*/*;q=0.8")
    req.add_header("Accept-Language", "en-US,en;q=0.9")
    return req


def open_url(req: urllib.request.Request, timeout: int):
    """urlopen with TLS verified by default; fall back to unverified ONLY on a
    certificate/SSL error so we can still classify misconfigured stores. Re-raises
    HTTPError so callers can read error-page bodies.

    Note: CPython wraps handshake SSL errors in urllib.error.URLError whose
    `.reason` is the ssl.SSLError, so we must inspect the reason, not just catch
    the bare ssl exception."""
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=_verified_context())
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLError):
            return urllib.request.urlopen(req, timeout=timeout, context=_unverified_context())
        raise
    except ssl.SSLError:
        return urllib.request.urlopen(req, timeout=timeout, context=_unverified_context())


def cart_js_is_shopify(domain: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """True iff GET https://domain/cart.js returns 200 with a JS content-type."""
    try:
        req = build_request(f"https://{domain}/cart.js")
        with open_url(req, timeout) as resp:
            ct = resp.headers.get("Content-Type", "")
            return resp.status == 200 and "javascript" in ct.lower()
    except Exception:
        return False
