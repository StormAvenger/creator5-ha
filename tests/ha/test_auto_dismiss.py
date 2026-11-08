"""Optional automatic dismissal of the print-complete screen."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import PrinterError, PrinterStatus
from custom_components.creator5.creator5py.client import ControlError
from custom_components.creator5.diagnostics import async_get_config_entry_diagnostics
from custom_components.creator5.settings import validated_options

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
BASE = {"status": "ready", "model": "Creator 5 Pro", "errorCode": ""}
ENABLED = {"auto_dismiss_completion": True, "auto_dismiss_minutes": 5}


@pytest.fixture
def printer():
    state = dict(BASE)

    async def get_status():
        return PrinterStatus(dict(state))

    async def dismiss():
        state["status"] = "ready"
        return PrinterStatus(dict(state))

    with (
        patch("custom_components.creator5.Creator5Client.get_status", side_effect=get_status),
        patch(
            "custom_components.creator5.Creator5Client.dismiss_completion", side_effect=dismiss
        ) as dismiss_mock,
    ):
        yield state, dismiss_mock


async def setup(hass, options):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, options=options, minor_version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def poll(hass, entry, state, **fields):
    state.update(fields)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done(wait_background_tasks=True)


async def wait(hass, freezer, seconds):
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass, datetime.now(UTC))
    await hass.async_block_till_done(wait_background_tasks=True)


async def finish_print(hass, entry, state):
    await poll(hass, entry, state, status="printing", printFileName="a.3mf", printDuration=60)
    await poll(hass, entry, state, status="completed")


async def test_dismisses_once_after_the_configured_delay(hass, freezer, printer):
    state, dismiss = printer
    entry = await setup(hass, ENABLED)
    await finish_print(hass, entry, state)
    await wait(hass, freezer, 5 * 60 - 2)
    dismiss.assert_not_awaited()
    await wait(hass, freezer, 3)
    dismiss.assert_awaited_once()
    assert entry.runtime_data.data.state == "ready"
    await wait(hass, freezer, 60 * 60)
    dismiss.assert_awaited_once()
    report = await async_get_config_entry_diagnostics(hass, entry)
    assert "auto_dismiss_completion" in report["control_scope"]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_off_by_default_never_dismisses(hass, freezer, printer):
    state, dismiss = printer
    entry = await setup(hass, {})
    await finish_print(hass, entry, state)
    await wait(hass, freezer, 6 * 60 * 60)
    dismiss.assert_not_awaited()
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "ready"},  # someone pressed the button on the printer
        {"status": "printing", "printFileName": "b.3mf", "printDuration": 0},  # new job
    ],
)
async def test_leaving_the_completed_screen_cancels_the_countdown(hass, freezer, printer, fields):
    state, dismiss = printer
    entry = await setup(hass, ENABLED)
    await finish_print(hass, entry, state)
    await wait(hass, freezer, 60)
    await poll(hass, entry, state, **fields)
    await wait(hass, freezer, 60 * 60)
    dismiss.assert_not_awaited()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_failure_is_not_retried_for_the_same_completion(hass, freezer, printer):
    state, dismiss = printer
    working = dismiss.side_effect
    dismiss.side_effect = ControlError("request", "Control request failed; outcome unconfirmed")
    entry = await setup(hass, ENABLED)
    await finish_print(hass, entry, state)
    await wait(hass, freezer, 5 * 60 + 1)
    dismiss.assert_awaited_once()
    for _ in range(5):
        await poll(hass, entry, state)  # still on the completed screen
        await wait(hass, freezer, 10 * 60)
    dismiss.assert_awaited_once()
    # The next completion gets its own single attempt.
    dismiss.side_effect = working
    await poll(hass, entry, state, status="ready")
    await finish_print(hass, entry, state)
    await wait(hass, freezer, 5 * 60 + 1)
    assert dismiss.await_count == 2
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_offline_at_due_time_sends_nothing_and_restarts_countdown(hass, freezer, printer):
    state, dismiss = printer
    entry = await setup(hass, ENABLED)
    await finish_print(hass, entry, state)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(side_effect=PrinterError("Off")),
    ):
        for _ in range(3):
            await entry.runtime_data.async_refresh()
        await wait(hass, freezer, 5 * 60 + 1)
    dismiss.assert_not_awaited()
    await poll(hass, entry, state)  # back online, still completed
    await wait(hass, freezer, 5 * 60 + 1)
    dismiss.assert_awaited_once()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_completed_screen_seen_at_startup_is_dismissed_after_delay(hass, freezer, printer):
    state, dismiss = printer
    state["status"] = "completed"
    entry = await setup(hass, ENABLED)
    await wait(hass, freezer, 5 * 60 + 1)
    dismiss.assert_awaited_once()
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "options",
    [
        {"auto_dismiss_minutes": 0},
        {"auto_dismiss_minutes": 241},
        {"auto_dismiss_minutes": 2.5},
        {"auto_dismiss_completion": "yes"},
    ],
)
def test_invalid_auto_dismiss_options(options):
    with pytest.raises(ValueError):
        validated_options(options, DATA["host"])
