"""Run real Home Assistant lifecycle code; replace only printer I/O."""

import pytest


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Enable loading this repository's integration in the HA fixture."""
