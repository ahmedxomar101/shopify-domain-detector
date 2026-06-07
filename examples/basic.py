"""Minimal usage. Run: python examples/basic.py"""
from shopify_domain_detector import classify_domains

DOMAINS = ["gymshark.com", "apple.com", "example.com"]

for domain, result in classify_domains(DOMAINS, workers=5).items():
    flag = "SHOPIFY" if result.is_shopify else result.category.value
    print(f"{domain:20s} -> {flag}")
