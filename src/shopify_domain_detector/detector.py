from __future__ import annotations

import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .domains import is_same_domain, normalize
from .http import PROBE_TIMEOUT, build_request, cart_js_is_shopify, open_url
from .models import Category, DomainResult, ProbeResult
from .signatures import detect_platforms, is_suspended


def categorize(probe: ProbeResult) -> tuple[Category, str | None]:
    """Map a probed homepage to a category. Pure; mirrors the reference logic.
    Order matters: rate-limit and bot-protection are checked before content."""
    status = probe.status
    platforms = probe.platforms
    has_shopify = "shopify" in platforms
    is_4xx_plus = isinstance(status, int) and status >= 400

    if probe.rate_limited:
        return Category.RATE_LIMITED, None
    if isinstance(status, int) and status == 403 and not platforms:
        return Category.BOT_PROTECTED, None
    if has_shopify and not probe.suspended_shopify and status == 200:
        return Category.SHOPIFY_IN_HTML_ACTIVE, None
    if has_shopify and probe.suspended_shopify:
        return Category.SHOPIFY_IN_HTML_SUSPENDED, None
    if has_shopify and is_4xx_plus:
        return Category.SHOPIFY_IN_HTML_SUSPENDED, None
    if status == "unreachable":
        return Category.DEAD, None
    other = next((p for p in platforms if p != "shopify"), None)
    return Category.NOT_SHOPIFY, other


def _resolve_redirect(domain: str) -> str | None:
    """Return the host the homepage resolves to (following redirects), or None."""
    candidates = [domain]
    if not domain.startswith("www."):
        candidates.append(f"www.{domain}")
    for candidate in candidates:
        for scheme in ("https", "http"):
            try:
                req = build_request(f"{scheme}://{candidate}")
                with open_url(req, 10) as resp:
                    return resp.url.split("//")[-1].split("/")[0]
            except Exception:
                continue
    return None


def probe_domain(domain: str) -> ProbeResult:
    """Fetch the homepage (bare + www., https+http), reading error-page bodies."""
    candidates = [domain]
    if not domain.startswith("www."):
        candidates.append(f"www.{domain}")
    for candidate in candidates:
        for scheme in ("https", "http"):
            url = f"{scheme}://{candidate}"
            try:
                req = build_request(url)
                with open_url(req, PROBE_TIMEOUT) as resp:
                    body = resp.read().decode("utf-8", errors="replace").lower()
                    return ProbeResult(
                        domain=domain,
                        status=resp.status,
                        platforms=tuple(detect_platforms(body)),
                        suspended_shopify=is_suspended(body),
                        resolved_domain=candidate,
                        server=resp.headers.get("Server", ""),
                        html_size=len(body),
                    )
            except urllib.error.HTTPError as e:
                try:
                    body = e.read().decode("utf-8", errors="replace").lower()
                except Exception:
                    body = ""
                return ProbeResult(
                    domain=domain,
                    status=e.code,
                    platforms=tuple(detect_platforms(body)) if body else (),
                    suspended_shopify=is_suspended(body) if body else False,
                    rate_limited=(e.code == 429),
                    resolved_domain=candidate,
                    html_size=len(body),
                )
            except Exception:
                continue
    return ProbeResult(domain=domain, status="unreachable")


def classify_domain(domain: str) -> DomainResult:
    """Full pipeline for one domain: cart.js -> redirect -> probe -> categorize."""
    d = normalize(domain)
    if cart_js_is_shopify(d):
        return DomainResult(d, Category.CONFIRMED_SHOPIFY, status=200)
    resolved = _resolve_redirect(d)
    if resolved and not is_same_domain(resolved, d) and cart_js_is_shopify(resolved):
        return DomainResult(d, Category.REDIRECTS_TO_SHOPIFY, redirects_to=resolved)
    if resolved and is_same_domain(resolved, d) and cart_js_is_shopify(resolved):
        return DomainResult(d, Category.CONFIRMED_SHOPIFY, status=200)
    probe = probe_domain(d)
    category, platform = categorize(probe)
    return DomainResult(d, category, platform=platform, status=probe.status)


def classify_domains(domains: list[str], workers: int = 15) -> dict[str, DomainResult]:
    """Classify many domains concurrently. Returns {input_domain: DomainResult}."""
    results: dict[str, DomainResult] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(classify_domain, d): d for d in domains}
        for fut in futures:
            d = futures[fut]
            results[d] = fut.result()
    return results
