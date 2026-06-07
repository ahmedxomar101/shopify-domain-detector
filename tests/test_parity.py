"""Categorizer parity with smartlead-analytics/analyze-shopify.py phase-4 rules.
Encodes the reference truth table so future refactors can't drift.

v0.3.0 addition: shopify-password-protected rows (password_protected field).
The table uses a tuple of (status, platforms, suspended, rate_limited,
password_protected, shopify_strong) — new fields default to False/False for
backward-compat rows so the table reads top-to-bottom without duplication."""
from shopify_domain_detector.detector import categorize
from shopify_domain_detector.models import ProbeResult

# Row format: (status, platforms, suspended, rate_limited, pw_protected, strong)
REFERENCE_TRUTH = [
    ((429, ("shopify",), False, True, False, False), "rate-limited"),
    ((403, (), False, False, False, False), "bot-protected"),
    ((403, ("shopify",), False, False, False, False), "shopify-in-html-suspended"),
    ((200, ("shopify",), False, False, False, False), "shopify-in-html-active"),
    ((200, ("shopify",), True, False, False, False), "shopify-in-html-suspended"),
    ((404, ("shopify",), False, False, False, False), "shopify-in-html-suspended"),
    (("unreachable", (), False, False, False, False), "dead"),
    ((200, ("woocommerce",), False, False, False, False), "not-shopify"),
    ((200, (), False, False, False, False), "not-shopify"),
    # v0.3.0: password-protected requires the strong shopify.com signal.
    ((200, ("shopify",), False, False, True, True), "shopify-password-protected"),
    ((200, (), False, False, True, True), "shopify-password-protected"),
    # /password with only a bare "shopify" mention (no shopify.com) → not trusted
    # as password-protected; falls through to active.
    ((200, ("shopify",), False, False, True, False), "shopify-in-html-active"),
]


def test_categorizer_matches_reference_truth_table():
    for (status, platforms, suspended, rl, pw, strong), expected in REFERENCE_TRUTH:
        probe = ProbeResult(
            domain="x.com", status=status, platforms=platforms,
            suspended_shopify=suspended, rate_limited=rl,
            password_protected=pw, shopify_strong=strong,
        )
        cat, _ = categorize(probe)
        assert cat.value == expected, (status, platforms, suspended, rl, pw, strong)
