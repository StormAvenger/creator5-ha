"""Synthetic credentials and status responses; no network calls."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import AuthenticationError, PrinterError, PrinterStatus
from custom_components.creator5.creator5py.discovery import PrinterIdentity

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
INPUT = {"host": DATA["host"], "check_code": DATA["check_code"]}
STATUS = PrinterStatus({"status": "ready", "model": "Creator 5 Pro"})


@pytest.fixture(autouse=True)
def identity_lookup():
    with patch(
        "custom_components.creator5.config_flow.discover_identity",
        new=AsyncMock(return_value=PrinterIdentity(DATA["serial_number"], 41)),
    ) as lookup:
        yield lookup


async def test_user_flow(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert {str(key) for key in result["data_schema"].schema} == {"host", "check_code"}
    with (
        patch(
            "custom_components.creator5.config_flow.Creator5Client.get_status",
            new=AsyncMock(return_value=STATUS),
        ),
        patch("custom_components.creator5.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == DATA
    assert result["result"].unique_id == DATA["serial_number"]


@pytest.mark.parametrize(
    "error,expected",
    [
        (AuthenticationError("Rejected"), "invalid_auth"),
        (PrinterError("Unavailable"), "cannot_connect"),
    ],
)
async def test_connection_errors(hass, error, expected):
    with patch(
        "custom_components.creator5.config_flow.Creator5Client.get_status",
        new=AsyncMock(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_invalid_host_never_contacts_printer(hass, identity_lookup):
    with patch(
        "custom_components.creator5.config_flow.Creator5Client.get_status", new=AsyncMock()
    ) as read:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={**INPUT, "host": "8.8.8.8"}
        )
    assert result["errors"] == {"base": "invalid_config"}
    read.assert_not_awaited()
    identity_lookup.assert_not_awaited()


async def test_duplicate_printer(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DATA["serial_number"], data=DATA)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.creator5.config_flow.Creator5Client.get_status", new=AsyncMock()
    ) as read:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    read.assert_not_awaited()


async def test_reauth_updates_existing_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DATA["serial_number"], data=DATA)
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    with (
        patch(
            "custom_components.creator5.config_flow.Creator5Client.get_status",
            new=AsyncMock(return_value=STATUS),
        ),
        patch("custom_components.creator5.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {"check_code": "new-synthetic-code"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["check_code"] == "new-synthetic-code"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize("pid,model", [(40, "Creator 5"), (41, "Creator 5 Pro")])
async def test_automatic_model_detection(hass, identity_lookup, pid, model):
    identity_lookup.return_value = PrinterIdentity(DATA["serial_number"], pid)
    with (
        patch(
            "custom_components.creator5.config_flow.Creator5Client.get_status",
            new=AsyncMock(return_value=PrinterStatus({"model": model})),
        ),
        patch("custom_components.creator5.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=INPUT
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == model
    assert result["data"] == DATA
    identity_lookup.assert_awaited_once_with(INPUT["host"])


@pytest.mark.parametrize("model", ["Creator 5", "Other printer", None])
async def test_model_mismatch_never_creates_entry(hass, model):
    with patch(
        "custom_components.creator5.config_flow.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus({"model": model})),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=INPUT
        )
    assert result["errors"] == {"base": "model_mismatch"}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_discovery_failure_never_sends_credentials(hass, identity_lookup):
    identity_lookup.side_effect = PrinterError("Unavailable")
    with patch(
        "custom_components.creator5.config_flow.Creator5Client.get_status", new=AsyncMock()
    ) as read:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=INPUT
        )
    assert result["errors"] == {"base": "discovery_failed"}
    read.assert_not_awaited()


async def test_wrong_discovery_family_never_sends_credentials(hass, identity_lookup):
    identity_lookup.return_value = PrinterIdentity("SYNTHETIC", 38)
    with patch(
        "custom_components.creator5.config_flow.Creator5Client.get_status", new=AsyncMock()
    ) as read:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=INPUT
        )
    assert result["errors"] == {"base": "unsupported_model"}
    read.assert_not_awaited()


async def test_empty_code_never_opens_discovery(hass, identity_lookup):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={**INPUT, "check_code": " "}
    )
    assert result["errors"] == {"base": "invalid_config"}
    identity_lookup.assert_not_awaited()
