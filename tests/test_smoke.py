def test_package_imports_and_has_version():
    import shopify_domain_detector as sdd
    assert isinstance(sdd.__version__, str)
    assert sdd.__version__.count(".") >= 1
