"""Categorizer parity with smartlead-analytics/analyze-shopify.py phase-4 rules.
Encodes the reference truth table so future refactors can't drift."""
from shopify_domain_detector.detector import categorize
from shopify_domain_detector.models import ProbeResult

REFERENCE_TRUTH = [
    # (status, platforms, suspended, rate_limited) -> expected category value
    ((429, ("shopify",), False, True), "rate-limited"),
    ((403, (), False, False), "bot-protected"),
    ((403, ("shopify",), False, False), "shopify-in-html-suspended"),
    ((200, ("shopify",), False, False), "shopify-in-html-active"),
    ((200, ("shopify",), True, False), "shopify-in-html-suspended"),
    ((404, ("shopify",), False, False), "shopify-in-html-suspended"),
    (("unreachable", (), False, False), "dead"),
    ((200, ("woocommerce",), False, False), "not-shopify"),
    ((200, (), False, False), "not-shopify"),
]


def test_categorizer_matches_reference_truth_table():
    for (status, platforms, suspended, rl), expected in REFERENCE_TRUTH:
        probe = ProbeResult(
            domain="x.com", status=status, platforms=platforms,
            suspended_shopify=suspended, rate_limited=rl,
        )
        cat, _ = categorize(probe)
        assert cat.value == expected, (status, platforms, suspended, rl)
