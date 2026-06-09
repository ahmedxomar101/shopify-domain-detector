# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/)
and [Semantic Versioning](https://semver.org/).

## [0.3.1] - 2026-06-10
### Fixed
- Apex false positive: `PLATFORM_SIGNATURES["shopify"]` dropped the bare
  `"shopify"` keyword, leaving only `cdn.shopify.com` / `myshopify.com`. A page
  that merely *mentions* the word "Shopify" in prose (e.g. a blog citing
  "Shopify sales data") is no longer misclassified as `shopify-in-html-active`.
  The apex content check now matches the same strong-signal intent as
  `has_shopify_strong`. The subdomain and password-protected paths were already
  strong-signal-gated and are unchanged.

## [0.3.0] - 2026-06-07
### Added
- Arbitrary-subdomain HTML harvesting: `extract_shop_hosts` now captures every
  `*.<base>` subdomain (any label, including multi-level) found in body HTML,
  not just `shop.`/`store.`. Document-order HTML hosts appear before
  `*.myshopify.com` refs, which appear before blind `shop.`/`store.` fallbacks.
- `has_shopify_strong(body)` in `signatures.py`: returns `True` when the body
  contains `"shopify.com"` — matches `cdn.shopify.com` and `*.myshopify.com`
  without false-positive on a bare `"shopify"` word.
- `Category.SHOPIFY_PASSWORD_PROTECTED` for pre-launch stores whose root
  redirects to `/password`. Not healthy (`is_healthy` remains False).
- `ProbeResult.password_protected` and `ProbeResult.shopify_strong` fields
  (both `bool`, default `False`), populated by `probe_domain()`.
- Full subdomain probe in `_classify_via_subdomain`: each candidate is checked
  with `cart.js` first, then a full `probe_domain()` call. Open stores
  (shopify_strong, not password-protected) are returned immediately; locked
  candidates (password_protected) are remembered as a fallback in case no
  open store is found in the candidate list.

### Changed
- `categorize()` checks `password_protected` before the active/suspended
  branches — a pre-launch store is never classified as active.
- Parity truth table in `test_parity.py` extended to 6-tuple row format
  (adds `password_protected` and `shopify_strong` columns); 2 new rows.

## [0.2.0] - 2026-06-07
### Added
- `shop.`/`store.` subdomain detection: when the apex is a marketing site, the
  store on a storefront subdomain is now found via its `/cart.js`.
- `discovered_domain`, `match_type`, and `reason` on `DomainResult`.
- `shop_subdomains` on `ProbeResult` (storefront candidates from homepage HTML).

### Changed
- Replaced `DomainResult.redirects_to` with `discovered_domain` (the exact host
  where Shopify was confirmed — apex, www, subdomain, or redirect target).

## [0.1.0] - 2026-06-07
### Added
- `classify_domain` / `classify_domains` two-stage Shopify detector.
- 8-category model (confirmed, in-html active/suspended, redirects, not-shopify,
  dead, rate-limited, bot-protected).
- `shopify-detect` CLI (summary + jsonl output).
- ccTLD-aware registrable-domain comparison; error-page body reading.
- TLS verified by default with documented unverified fallback for broken certs.
- Dependency-free (stdlib only); Python 3.10–3.12 CI.
