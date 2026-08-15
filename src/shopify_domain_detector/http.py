from __future__ import annotations

import ipaddress
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 10
PROBE_TIMEOUT = 15

# --- SSRF: a redirect must not carry a fetch into a private network ---------
#
# This library is handed a domain by its caller and fetches it, and until this
# existed `urlopen` used the default opener — which follows redirects with
# nothing re-checking where they lead. So a public domain answering
# `302 Location: http://169.254.169.254/...` was fetched and its body returned.
# Screening the SUBMITTED host cannot close that: the attacker controls the
# redirect, not the name you screened.
#
# The check lives here because this is the only layer that sees the
# intermediate hops at all, and because a library whose job is fetching
# untrusted domains should be safe by default rather than safe if the caller
# remembers.
#
# Do not assume infrastructure will catch this. Vercel Sandbox `deniedCIDRs`
# was measured on 2026-08-15 still reaching 169.254.169.254, with the policy
# accepted and echoed back in the create response.

BLOCKED_REDIRECT_MESSAGE = "refusing a redirect into a non-public address"

# 100.64.0.0/10. `is_private` covers this on newer Pythons and not on older
# ones, so it is stated rather than inherited.
_CGNAT = ipaddress.ip_network("100.64.0.0/10")

_ALLOWED_REDIRECT_SCHEMES = frozenset({"http", "https"})


class RedirectBlocked(urllib.error.URLError):
    """A redirect pointed somewhere we will not follow.

    A URLError subclass on purpose: callers already treat a URLError as "this
    fetch did not happen", and `detector.classify_domain` turns that into a
    `dead` verdict rather than a crash.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(f"{BLOCKED_REDIRECT_MESSAGE}: {detail}")


def address_is_blocked(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for anything that is not an ordinary public address."""
    return bool(
        addr.is_private or addr.is_loopback or addr.is_link_local
        or addr.is_reserved or addr.is_unspecified or addr.is_multicast
        or (addr.version == 4 and addr in _CGNAT)
    )


def _resolved_addresses(host: str) -> list:
    """Every address `host` resolves to, or a bare IP parsed directly.

    A `Location` may carry an IP literal, which needs no DNS — and a guard that
    only looked at hostnames would wave `http://169.254.169.254/` straight
    through.
    """
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def assert_target_is_public(url: str) -> None:
    """Raise RedirectBlocked unless `url` names a public http(s) address.

    Fails CLOSED: a host that will not resolve is refused, because "I cannot
    tell where this goes" is not a reason to go there.
    """
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in _ALLOWED_REDIRECT_SCHEMES:
        raise RedirectBlocked(f"scheme {parts.scheme!r}")
    host = parts.hostname
    if not host:
        raise RedirectBlocked("no host")
    try:
        addresses = _resolved_addresses(host)
    except OSError as exc:
        raise RedirectBlocked(f"{host} does not resolve ({exc})") from exc
    blocked = [str(a) for a in addresses if address_is_blocked(a)]
    if blocked:
        raise RedirectBlocked(f"{host} -> {', '.join(blocked)}")


class _GuardedRedirects(urllib.request.HTTPRedirectHandler):
    """Re-checks the target of EVERY hop, not just the first.

    One check on the submitted URL is worth nothing against a chain: the second
    hop is exactly where an attacker puts the address they actually want.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        assert_target_is_public(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def guarded_opener(context: ssl.SSLContext | None = None) -> urllib.request.OpenerDirector:
    """An opener that refuses redirects into non-public addresses."""
    handlers: list = [_GuardedRedirects()]
    if context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    return urllib.request.build_opener(*handlers)



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
    # guarded_opener, never urlopen: the module-level default opener follows
    # redirects with nothing re-checking the target, which is the whole SSRF
    # hole. A guard that is defined but not installed protects nothing.
    assert_target_is_public(req.full_url)
    try:
        return guarded_opener(_verified_context()).open(req, timeout=timeout)
    except urllib.error.HTTPError:
        raise
    except RedirectBlocked:
        # Never retried unverified: the refusal is about WHERE it points, and
        # a second attempt would point at exactly the same place.
        raise
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLError):
            return guarded_opener(_unverified_context()).open(req, timeout=timeout)
        raise
    except ssl.SSLError:
        return guarded_opener(_unverified_context()).open(req, timeout=timeout)


def cart_js_is_shopify(domain: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """True iff GET https://domain/cart.js returns 200 with a JS content-type."""
    try:
        req = build_request(f"https://{domain}/cart.js")
        with open_url(req, timeout) as resp:
            ct = resp.headers.get("Content-Type", "")
            return resp.status == 200 and "javascript" in ct.lower()
    except Exception:
        return False
