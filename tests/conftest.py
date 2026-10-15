"""The client suite stays usable without installing Home Assistant."""

from importlib.util import find_spec

collect_ignore = ["ha"] if find_spec("pytest_homeassistant_custom_component") is None else []
