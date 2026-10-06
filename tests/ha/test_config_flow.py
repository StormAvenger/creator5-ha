"""Synthetic credentials and status responses; no network calls."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import AuthenticationError, PrinterError, PrinterStatus

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
STATUS = PrinterStatus({"status": "ready"})


async def test_user_flow(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    with (
        patch(
            "custom_components.creator5.config_flow.Creator5Client.get_status",
            new=AsyncMock(return_value=STATUS),
        ),
        patch("custom_components.creator5.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
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
            DOMAIN, context={"source": SOURCE_USER}, data=DATA
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_invalid_host_never_contacts_printer(hass):
    with patch(
        "custom_components.creator5.config_flow.Creator5Client.get_status", new=AsyncMock()
    ) as read:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={**DATA, "host": "8.8.8.8"}
        )
    assert result["errors"] == {"base": "invalid_config"}
    read.assert_not_awaited()


async def test_duplicate_printer(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DATA["serial_number"], data=DATA)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.creator5.config_flow.Creator5Client.get_status", new=AsyncMock()
    ) as read:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DATA
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
