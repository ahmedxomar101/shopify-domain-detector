# AGENTS.md

Guidance for AI agents and contributors working in this repository.

## Project purpose

`shopify-domain-detector` classifies whether a web domain is a live Shopify
store. It is a dependency-free Python library (stdlib only) consumed both as a
package API and a CLI, and depended on by downstream apps via pinned git tags.

## Architecture map

| Module | Responsibility | Network? |
|--------|----------------|:--------:|
| `models.py` | `Category` enum, `DomainResult`, `ProbeResult` | no |
| `domains.py` | normalize, registrable-domain (ccTLD-aware) compare | no |
| `signatures.py` | platform signatures, suspended-store detection | no |
| `http.py` | request builder, TLS contexts, `open_url`, `cart_js_is_shopify` | yes |
| `detector.py` | `probe_domain`, `categorize` (pure), `classify_domain(s)` | yes |
| `cli.py` | `shopify-detect` entrypoint | via detector |

## Golden rules

- **Keep `domains`, `signatures`, and `categorize` pure** — no sockets, no I/O.
  All network access lives in `http.py` and the orchestration in `detector.py`.
  This is what makes the logic unit-testable without a network.
- **Zero runtime dependencies.** Standard library only. Never add a dependency
  without explicit approval.
- **TLS posture:** verify by default; the unverified context in `http.py` is a
  documented fallback used only on certificate-validation failure to read public
  HTML for classification. Do not make unverified the default.
- **Conventional commits** (`feat:` / `fix:` / `docs:` / `test:` / `chore:`),
  one logical change per commit, feature branches, PRs reviewed before merge.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -e ".[dev]"
ruff check .
python -m pytest -v
```

## TDD workflow

1. Write one failing test first; run it; confirm it fails for the right reason.
2. Pure logic → real unit tests. Network paths → mocked-HTTP tests via
   `unittest.mock.patch` on `detector.cart_js_is_shopify`,
   `detector._resolve_redirect`, or `detector.probe_domain`.
3. Implement the minimal code to pass; refactor green; commit.

## Changing categorization (the contract)

`categorize()` and `tests/test_parity.py` are a pair. If you change a
categorization rule, update **both** in the same commit — the truth table is the
behavioral contract downstream apps rely on.

## Release

Bump `__version__` (`src/shopify_domain_detector/__init__.py`), `version` in
`pyproject.toml`, and `CHANGELOG.md` together; tag `vX.Y.Z`. Downstream apps pin
tags, so a release is the unit of propagation.
