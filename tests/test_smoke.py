"""Smoke test — verifies project imports and basic sanity."""


def test_import_core():
    """Core package is importable."""
    import atlas.core  # noqa: F401


def test_import_workflows():
    """Workflow package is importable."""
    import atlas.workflows  # noqa: F401


def test_import_integrations():
    """Integration package is importable."""
    import atlas.integrations  # noqa: F401
