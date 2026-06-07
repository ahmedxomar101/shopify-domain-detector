from __future__ import annotations

# Second-level labels used under country-code TLDs (example.co.uk, example.com.au)
_CC_SLDS = {"co", "com", "org", "net", "edu", "gov", "ac"}


def normalize(raw: str) -> str:
    """Lowercase, strip scheme and surrounding whitespace, trim trailing slash."""
    d = raw.strip().lower()
    d = d.replace("https://", "").replace("http://", "")
    return d.rstrip("/")


def base_domain(domain: str) -> str:
    """Registrable domain. shop.example.com / www.example.com -> example.com.
    Country-code aware: a.b.example.co.uk -> example.co.uk."""
    d = domain.lower().strip(".")
    d = d.split("/")[0]  # host portion only
    parts = d.split(".")
    if len(parts) >= 3 and parts[-2] in _CC_SLDS and len(parts[-1]) <= 3:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return d


def is_same_domain(a: str, b: str) -> bool:
    return base_domain(a) == base_domain(b)
