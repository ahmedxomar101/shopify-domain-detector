from __future__ import annotations

import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .domains import base_domain, is_same_domain, normalize
from .http import PROBE_TIMEOUT, build_request, cart_js_is_shopify, open_url
from .models import Category, DomainResult, ProbeResult
from .signatures import detect_platforms, is_suspended
from .subdomains import extract_shop_hosts

# Cap subdomain cart.js probes to bound the number of extra requests per domain.
_MAX_SUBDOMAIN_PROBES = 6


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
                        shop_subdomains=tuple(
                            extract_shop_hosts(body, base_domain(domain))
                        ),
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
                    shop_subdomains=tuple(
                        extract_shop_hosts(body, base_domain(domain))
                    ) if body else (),
                )
            except Exception:
                continue
    return ProbeResult(domain=domain, status="unreachable")


_REASONS = {
    Category.CONFIRMED_SHOPIFY: "shopify cart.js / signature",
    Category.SHOPIFY_IN_HTML_ACTIVE: "shopify cart.js / signature",
    Category.SHOPIFY_IN_HTML_SUSPENDED: "shopify store unavailable/suspended",
    Category.DEAD: "unreachable",
    Category.RATE_LIMITED: "rate limited (429)",
    Category.BOT_PROTECTED: "bot-protected (403)",
}


def reason_for(category: Category, probe: ProbeResult) -> str:
    """Short human explanation for a categorized probe outcome."""
    if category == Category.NOT_SHOPIFY:
        platform = next((p for p in probe.platforms if p != "shopify"), None)
        return "no shopify signal" + (f"; platform={platform}" if platform else "")
    return _REASONS.get(category, "")


def _confirmed(domain: str, host: str, match_type: str, reason: str) -> DomainResult:
    return DomainResult(
        domain,
        Category.CONFIRMED_SHOPIFY,
        discovered_domain=host,
        match_type=match_type,
        reason=reason,
        status=200,
    )


def _classify_via_redirect(d: str, resolved: str) -> DomainResult | None:
    """Classify using the redirect target's /cart.js, or None if not Shopify."""
    if not cart_js_is_shopify(resolved):
        return None
    if not is_same_domain(resolved, d):
        return DomainResult(
            d,
            Category.REDIRECTS_TO_SHOPIFY,
            discovered_domain=resolved,
            match_type="redirect",
            reason=f"redirects to shopify ({resolved})",
        )
    match_type = "www" if resolved.startswith("www.") else "apex"
    return _confirmed(d, resolved, match_type, f"cart.js on {match_type}")


def _classify_via_subdomain(d: str, probe: ProbeResult) -> DomainResult | None:
    """Probe storefront subdomain candidates; confirm on the first hit."""
    for sub in probe.shop_subdomains[:_MAX_SUBDOMAIN_PROBES]:
        if cart_js_is_shopify(sub):
            return _confirmed(d, sub, "subdomain", f"cart.js on subdomain ({sub})")
    return None


def classify_domain(domain: str) -> DomainResult:
    """Full pipeline: cart.js -> www -> redirect -> probe -> subdomain -> categorize."""
    d = normalize(domain)
    if cart_js_is_shopify(d):
        return _confirmed(d, d, "apex", "cart.js on apex")

    wwwhost = d if d.startswith("www.") else f"www.{d}"
    if wwwhost != d and cart_js_is_shopify(wwwhost):
        return _confirmed(d, wwwhost, "www", "cart.js on www")

    resolved = _resolve_redirect(d)
    if resolved:
        via_redirect = _classify_via_redirect(d, resolved)
        if via_redirect:
            return via_redirect

    probe = probe_domain(d)
    via_subdomain = _classify_via_subdomain(d, probe)
    if via_subdomain:
        return via_subdomain

    category, platform = categorize(probe)
    return DomainResult(
        d,
        category,
        platform=platform,
        discovered_domain=None,
        match_type="",
        reason=reason_for(category, probe),
        status=probe.status,
    )


def classify_domains(domains: list[str], workers: int = 15) -> dict[str, DomainResult]:
    """Classify many domains concurrently. Returns {input_domain: DomainResult}."""
    results: dict[str, DomainResult] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(classify_domain, d): d for d in domains}
        for fut in futures:
            d = futures[fut]
            try:
                results[d] = fut.result()
            except Exception:
                # Never let one domain abort the whole batch (matters at scale).
                results[d] = DomainResult(d, Category.DEAD)
    return results
