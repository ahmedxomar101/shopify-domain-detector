from shopify_domain_detector.detector import categorize
from shopify_domain_detector.models import Category, ProbeResult
from shopify_domain_detector.signatures import detect_platforms, is_suspended


def _probe(**kw):
    return ProbeResult(domain="x.com", **kw)


def _probe_from_html(status, html: str) -> ProbeResult:
    """Build a ProbeResult the way probe_domain() does: run the real
    signature functions over a lowercased body. No network involved."""
    body = html.lower()
    return ProbeResult(
        domain="x.com",
        status=status,
        platforms=tuple(detect_platforms(body)),
        suspended_shopify=is_suspended(body),
    )


def test_rate_limited_wins():
    cat, plat = categorize(_probe(status=429, rate_limited=True, platforms=("shopify",)))
    assert cat == Category.RATE_LIMITED and plat is None


def test_bot_protected_is_403_with_no_platforms():
    cat, plat = categorize(_probe(status=403, platforms=()))
    assert cat == Category.BOT_PROTECTED


def test_403_with_platform_is_not_bot_protected():
    cat, plat = categorize(_probe(status=403, platforms=("shopify",)))
    assert cat == Category.SHOPIFY_IN_HTML_SUSPENDED


def test_active_shopify_requires_200_and_not_suspended():
    cat, plat = categorize(_probe(status=200, platforms=("shopify",)))
    assert cat == Category.SHOPIFY_IN_HTML_ACTIVE


def test_suspended_shopify():
    cat, plat = categorize(_probe(status=200, platforms=("shopify",), suspended_shopify=True))
    assert cat == Category.SHOPIFY_IN_HTML_SUSPENDED


def test_shopify_with_4xx_is_suspended():
    cat, plat = categorize(_probe(status=404, platforms=("shopify",)))
    assert cat == Category.SHOPIFY_IN_HTML_SUSPENDED


def test_unreachable_is_dead():
    cat, plat = categorize(_probe(status="unreachable", platforms=()))
    assert cat == Category.DEAD


def test_not_shopify_records_other_platform():
    cat, plat = categorize(_probe(status=200, platforms=("wix",)))
    assert cat == Category.NOT_SHOPIFY and plat == "wix"


def test_not_shopify_no_platform():
    cat, plat = categorize(_probe(status=200, platforms=()))
    assert cat == Category.NOT_SHOPIFY and plat is None


# v0.3.0: password-protected branch

def test_password_protected_with_shopify_strong():
    """password_protected + shopify.com strong signal → SHOPIFY_PASSWORD_PROTECTED."""
    cat, plat = categorize(_probe(
        status=200, platforms=("shopify",), password_protected=True, shopify_strong=True
    ))
    assert cat == Category.SHOPIFY_PASSWORD_PROTECTED and plat is None


def test_password_protected_strong_signal_no_platforms():
    """password_protected + shopify_strong (no platforms list) → password-protected."""
    cat, plat = categorize(_probe(
        status=200, platforms=(), password_protected=True, shopify_strong=True
    ))
    assert cat == Category.SHOPIFY_PASSWORD_PROTECTED and plat is None


def test_password_protected_without_shopify_is_not_password_category():
    """password_protected with no shopify signals → falls through normally."""
    cat, plat = categorize(_probe(status=200, platforms=(), password_protected=True))
    assert cat == Category.NOT_SHOPIFY


def test_password_protected_requires_strong_signal_not_bare_word():
    """A /password page with only a bare 'shopify' mention (no shopify.com) is NOT
    treated as password-protected — the strong signal is required for precision."""
    cat, plat = categorize(_probe(
        status=200, platforms=("shopify",), password_protected=True, shopify_strong=False
    ))
    assert cat != Category.SHOPIFY_PASSWORD_PROTECTED
    assert cat == Category.SHOPIFY_IN_HTML_ACTIVE


def test_password_protected_takes_priority_over_active():
    """A password-protected shopify page (strong signal) must NOT be 'active'."""
    cat, plat = categorize(_probe(
        status=200, platforms=("shopify",), password_protected=True, shopify_strong=True
    ))
    assert cat != Category.SHOPIFY_IN_HTML_ACTIVE
    assert cat == Category.SHOPIFY_PASSWORD_PROTECTED


# v0.3.2: suspended-store shopify-y marker (34/268 = 12.7% of a real 600-domain
# not-shopify sample were suspended Shopify stores misclassified as
# not-shopify). Fixtures are run through the *real* signature functions
# (detect_platforms/is_suspended), not hand-set platforms=(...), so this is a
# true regression test of the detection code, not just of categorize()'s gate.

# Captured verbatim from https://apothandco.com (404, confirmed suspended
# Shopify store) on 2026-08-08; trimmed of the template's CSS/SVG boilerplate.
REAL_SUSPENDED_SHOPIFY_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>This store is unavailable</title>
  <meta name="referrer" content="never" />
<meta name="shopify-y" content="00000000-0000-0000-0000-000000000000"></head>
<body class="status-error status-code-500">
  <div class="wrapper">
    <div class="content">
      <div class="content--block">
        <div class="content--desc">
          This store is unavailable
        </div>
      </div>
    </div>
    <div class="request-id">Request ID: 0e04a9d0-90c7-4c91-b15b-4e75d2df506e</div>
  </div>
</body>
</html>
"""

# A generic, unrelated host's suspension page that uses the SAME "this store
# is unavailable" phrase but carries no Shopify marker at all. This is the
# scenario the rejected fix (trusting is_suspended() text alone) would get
# wrong — proving the has_shopify gate still matters after this change.
GENERIC_NON_SHOPIFY_UNAVAILABLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Store Unavailable</title></head>
<body>
  <h1>Sorry, this store is unavailable.</h1>
  <p>If you are the owner, please contact your hosting provider.</p>
</body>
</html>
"""


def test_real_suspended_shopify_page_is_classified_suspended():
    cat, plat = categorize(_probe_from_html(404, REAL_SUSPENDED_SHOPIFY_HTML))
    assert cat == Category.SHOPIFY_IN_HTML_SUSPENDED
    assert plat is None


def test_generic_non_shopify_unavailable_page_is_not_shopify():
    """Same 'unavailable' phrasing, no shopify-y marker → must NOT be promoted
    to a Shopify category, even though is_suspended() alone would say True."""
    probe = _probe_from_html(404, GENERIC_NON_SHOPIFY_UNAVAILABLE_HTML)
    assert probe.suspended_shopify is True  # is_suspended() alone can't tell
    cat, plat = categorize(probe)
    assert cat == Category.NOT_SHOPIFY
    assert cat != Category.SHOPIFY_IN_HTML_SUSPENDED


def test_suspended_and_generic_pages_classify_differently():
    """N=2 regression proof: a single fixture can't distinguish a working
    matcher from one that says 'shopify' to everything — these two must not
    collapse to the same category."""
    suspended_cat, _ = categorize(_probe_from_html(404, REAL_SUSPENDED_SHOPIFY_HTML))
    generic_cat, _ = categorize(_probe_from_html(404, GENERIC_NON_SHOPIFY_UNAVAILABLE_HTML))
    assert suspended_cat != generic_cat
