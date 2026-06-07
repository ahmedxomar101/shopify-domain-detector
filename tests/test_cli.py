import json
from unittest.mock import patch

from shopify_domain_detector import cli
from shopify_domain_detector.models import Category, DomainResult


def test_public_api_exports():
    import shopify_domain_detector as sdd
    assert hasattr(sdd, "classify_domain")
    assert hasattr(sdd, "classify_domains")
    assert hasattr(sdd, "Category")
    assert hasattr(sdd, "DomainResult")


def test_cli_writes_jsonl(tmp_path, capsys):
    infile = tmp_path / "domains.txt"
    infile.write_text("a.com\nb.com\n")
    fake = {
        "a.com": DomainResult("a.com", Category.CONFIRMED_SHOPIFY),
        "b.com": DomainResult("b.com", Category.NOT_SHOPIFY, platform="wix"),
    }
    with patch.object(cli, "classify_domains", return_value=fake):
        rc = cli.main(["--from-file", str(infile), "--format", "jsonl"])
    assert rc == 0
    out = capsys.readouterr().out.strip().splitlines()
    parsed = [json.loads(line) for line in out]
    cats = {p["domain"]: p["category"] for p in parsed}
    assert cats["a.com"] == "confirmed-shopify"
    assert cats["b.com"] == "not-shopify"
