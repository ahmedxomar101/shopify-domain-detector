# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/)
and [Semantic Versioning](https://semver.org/).

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
