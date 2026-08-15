"""A redirect must not carry a fetch into a private network.

This library takes a domain from whoever is calling it and fetches it. Until
now `urlopen` used the default opener, which follows redirects with nothing
re-validating where they lead — so a perfectly ordinary public domain that
answers `302 Location: http://169.254.169.254/...` got fetched, and the caller
received the response body.

Checking the submitted host is not enough and never was. The attacker controls
the redirect, not the domain you screened.

**Why the guard lives here rather than in the caller.** Two reasons. It is the
only place that sees the intermediate hops at all — a caller can screen what it
submits and never learns where the fetch actually went. And this is a library
whose entire job is fetching untrusted domains, so it should be safe by default
rather than safe if you remember.

Verified independently that the network layer will not do this for us: Vercel
Sandbox's `deniedCIDRs` was measured on 2026-08-15 reaching 169.254.169.254
anyway, with the policy accepted and echoed back. There is no infrastructure
backstop to lean on.
"""
import ipaddress
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from shopify_domain_detector import http as http_module
from shopify_domain_detector.http import (
    BLOCKED_REDIRECT_MESSAGE,
    RedirectBlocked,
    address_is_blocked,
    build_request,
    guarded_opener,
    open_url,
)

_real_resolve = http_module._resolved_addresses


# --- which addresses are refused -------------------------------------------


@pytest.mark.parametrize("addr", [
    "127.0.0.1",        # loopback
    "10.0.0.5",         # RFC1918
    "172.16.0.1",       # RFC1918
    "192.168.1.1",      # RFC1918
    "169.254.169.254",  # link-local: cloud metadata, the classic SSRF target
    "0.0.0.0",          # unspecified
    "::1",              # loopback, v6
    "fd00::1",          # unique local, v6
    "fe80::1",          # link-local, v6
])
def test_a_private_or_special_address_is_blocked(addr):
    assert address_is_blocked(ipaddress.ip_address(addr)) is True


@pytest.mark.parametrize("addr", ["93.184.216.34", "1.1.1.1", "2606:4700::1111"])
def test_an_ordinary_public_address_is_allowed(addr):
    """The guard must not break the actual job. A false positive here silently
    stops classifying real stores."""
    assert address_is_blocked(ipaddress.ip_address(addr)) is False


def test_carrier_grade_nat_is_blocked():
    """100.64.0.0/10. Python calls this `is_private` only in newer versions, so
    it is asserted explicitly rather than trusted to the stdlib."""
    assert address_is_blocked(ipaddress.ip_address("100.64.0.1")) is True


# --- the redirect handler itself -------------------------------------------


def _redirect_to(host):
    """Drive the guard's redirect hook the way urllib does, with a Location
    pointing at `host`."""
    handler = guarded_opener().handlers
    guard = next(h for h in handler if hasattr(h, "redirect_request"))
    req = build_request("https://example.com/")
    return guard.redirect_request(
        req, None, 302, "Found", {}, f"http://{host}/next")


def test_a_redirect_into_link_local_is_refused():
    """THE BUG. A public domain 302ing at cloud metadata."""
    with patch.object(socket, "getaddrinfo",
                      return_value=[(2, 1, 6, "", ("169.254.169.254", 0))]), \
         pytest.raises(RedirectBlocked) as exc:
        _redirect_to("metadata.attacker.example")
    assert "169.254.169.254" in str(exc.value)


def test_a_redirect_into_rfc1918_is_refused():
    with patch.object(socket, "getaddrinfo",
                      return_value=[(2, 1, 6, "", ("10.1.2.3", 0))]), \
         pytest.raises(RedirectBlocked):
        _redirect_to("internal.attacker.example")


def test_a_redirect_to_a_public_host_is_allowed_through():
    """The guard has to let the common case work — plenty of real stores
    redirect apex to www, or http to https."""
    with patch.object(socket, "getaddrinfo",
                      return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        assert _redirect_to("www.example.com") is not None


def test_a_redirect_whose_host_will_not_resolve_is_refused():
    """Fail CLOSED. If we cannot tell where it points, we do not go."""
    with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("nope")), \
         pytest.raises(RedirectBlocked):
        _redirect_to("nx.attacker.example")


def test_a_redirect_to_a_bare_ip_is_checked_without_dns():
    """`Location: http://169.254.169.254/` needs no resolution, and a guard
    that only inspected hostnames would wave it straight through."""
    with pytest.raises(RedirectBlocked):
        _redirect_to("169.254.169.254")


@pytest.mark.parametrize("scheme", ["file", "gopher", "ftp"])
def test_a_redirect_to_a_non_http_scheme_is_refused(scheme):
    """`Location: file:///etc/passwd` is the other half of this attack, and
    urllib's default handler is happy to follow some of these."""
    handler = next(h for h in guarded_opener().handlers
                   if hasattr(h, "redirect_request"))
    with pytest.raises(RedirectBlocked):
        handler.redirect_request(build_request("https://example.com/"), None,
                                 302, "Found", {}, f"{scheme}:///etc/passwd")


def test_the_refusal_message_does_not_leak_anything_beyond_the_address():
    """It reaches a caller's logs. It should say enough to debug and no more."""
    assert "redirect" in BLOCKED_REDIRECT_MESSAGE.lower()


# --- every hop, not just the first -----------------------------------------


def test_the_guard_is_installed_on_the_opener_used_for_real_fetches():
    """A handler nobody installs protects nothing.

    The first version of this test asserted only that `guarded_opener()` had a
    guarding handler — which passed while `open_url` was still calling
    `urllib.request.urlopen` and using the DEFAULT opener. The guard existed
    and protected nothing, and the test said everything was fine. So it now
    asserts the wiring instead of the definition.
    """
    names = {type(h).__name__ for h in guarded_opener().handlers}
    assert any("Guard" in n for n in names), \
        f"no guarding redirect handler on the opener: {sorted(names)}"

    source = Path(http_module.__file__).read_text()
    assert "urllib.request.urlopen(" not in source, (
        "something still fetches through the module-level default opener, "
        "which follows redirects unguarded")


def test_open_url_refuses_a_url_that_already_points_somewhere_private():
    """Hop zero. The submitted URL is checked too — otherwise the caller can
    hand us `http://10.0.0.1/` directly and never need a redirect at all."""
    with pytest.raises(RedirectBlocked):
        open_url(build_request("http://169.254.169.254/latest/meta-data/"), 5)


def test_open_url_actually_follows_a_redirect_chain_through_the_guard():
    """End to end over a real socket: a local server 302s to a link-local
    address and the fetch must refuse rather than follow.

    Uses a real HTTP server because the bug was never in the guard's logic —
    it was in which opener `open_url` handed the request to, and only a real
    request exercises that.
    """
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread

    class Redirector(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Redirector)
    Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        # 127.0.0.1 is itself blocked, so point at the loopback server by a
        # name that resolves public-ward for hop zero, then let it redirect.
        req = build_request(f"http://localhost:{port}/")
        with patch("shopify_domain_detector.http._resolved_addresses",
                   side_effect=lambda h: [ipaddress.ip_address("93.184.216.34")]
                   if h == "localhost" else _real_resolve(h)), \
             pytest.raises(RedirectBlocked) as exc:
            open_url(req, 5)
        assert "169.254.169.254" in str(exc.value)
    finally:
        server.shutdown()
