def test_cli_entrypoint_imports():
    import src.cli  # noqa: F401


def test_api_entrypoint_imports():
    import src.api.v1.cli  # noqa: F401

