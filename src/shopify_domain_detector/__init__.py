"""shopify-domain-detector: dependency-free Shopify store detection."""

from .detector import categorize, classify_domain, classify_domains, probe_domain
from .models import Category, DomainResult, ProbeResult

__version__ = "0.3.0"
__all__ = [
    "classify_domain",
    "classify_domains",
    "categorize",
    "probe_domain",
    "Category",
    "DomainResult",
    "ProbeResult",
    "__version__",
]
