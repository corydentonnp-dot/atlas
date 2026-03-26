"""Shared test fixtures and configuration for Atlas."""
import pytest


@pytest.fixture
def anyio_backend():
    """Use asyncio as the async backend for tests."""
    return "asyncio"
