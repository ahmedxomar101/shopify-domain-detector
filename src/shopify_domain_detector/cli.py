from __future__ import annotations

import argparse
import json
import sys

from .detector import classify_domains
from .domains import normalize


def _read_domains(path: str) -> list[str]:
    with open(path) as f:
        return sorted({normalize(line) for line in f if line.strip()})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="shopify-detect",
        description="Classify domains as Shopify / not-Shopify / uncertain.",
    )
    p.add_argument("--from-file", required=True, help="One domain per line")
    p.add_argument("--workers", type=int, default=15)
    p.add_argument("--format", choices=["jsonl", "summary"], default="summary")
    args = p.parse_args(argv)

    domains = _read_domains(args.from_file)
    if not domains:
        print("No domains found.", file=sys.stderr)
        return 1

    results = classify_domains(domains, workers=args.workers)

    if args.format == "jsonl":
        for d in domains:
            r = results[d]
            print(json.dumps({
                "domain": r.domain,
                "category": r.category.value,
                "is_shopify": r.is_shopify,
                "platform": r.platform,
                "redirects_to": r.redirects_to,
            }))
        return 0

    counts: dict[str, int] = {}
    for r in results.values():
        counts[r.category.value] = counts.get(r.category.value, 0) + 1
    total = len(results)
    healthy = sum(1 for r in results.values() if r.is_shopify)
    print(f"Total: {total}  Shopify (healthy): {healthy} ({healthy * 100 // total}%)")
    for cat in sorted(counts):
        print(f"  {cat}: {counts[cat]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
