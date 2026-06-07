# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/)
and [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-06-07
### Added
- `classify_domain` / `classify_domains` two-stage Shopify detector.
- 8-category model (confirmed, in-html active/suspended, redirects, not-shopify,
  dead, rate-limited, bot-protected).
- `shopify-detect` CLI (summary + jsonl output).
- ccTLD-aware registrable-domain comparison; error-page body reading.
- TLS verified by default with documented unverified fallback for broken certs.
- Dependency-free (stdlib only); Python 3.10–3.12 CI.
