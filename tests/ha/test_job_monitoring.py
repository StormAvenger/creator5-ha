"""Job transitions, trustworthy estimates and view-only thumbnail I/O in real HA."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.components.image import async_get_image
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import PrinterError, PrinterStatus
from custom_components.creator5.diagnostics import async_get_config_entry_diagnostics
from custom_components.creator5.image import color_png

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
DETAIL = {
    "status": "printing",
    "model": "Creator 5 Pro",
    "printFileName": "Test.3mf",
    "estimatedTime": 120,
    "printProgress": 0.5,
    "printLayer": 20,
    "cumulativePrintTime": 120,
    "remainingDiskSpace": 5.25,
    "printFileThumbUrl": "https://untrusted.invalid/private",
}


async def test_job_sensors_gating_frozen_eta_and_counter_units(hass, freezer):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, minor_version=2)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(DETAIL)),
    ) as read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data
        finish = hass.states.get("sensor.creator_5_estimated_finish_time").state
        assert dt_util.parse_datetime(finish) == (
            dt_util.utcnow() + timedelta(seconds=120)
        ).replace(microsecond=0)
        assert hass.states.get("sensor.creator_5_current_print_filename").state == "Test.3mf"
        lifetime = hass.states.get("sensor.creator_5_reported_lifetime_printing_time")
        assert lifetime.state == "2.0" and lifetime.attributes["unit_of_measurement"] == "h"
        storage = hass.states.get("sensor.creator_5_reported_free_storage")
        assert storage.state == "5.25" and storage.attributes["unit_of_measurement"] == "GB"
        freezer.tick(timedelta(seconds=5))
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("sensor.creator_5_estimated_finish_time").state == finish
        for state in ("paused", "pause", "error", "heating", "completed", "ready"):
            read.return_value = PrinterStatus({**DETAIL, "status": state})
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get("sensor.creator_5_estimated_finish_time").state == "unknown"
            if state not in ("paused", "pause"):
                assert hass.states.get("sensor.creator_5_current_print_filename").state == "unknown"
                assert (
                    hass.states.get("image.creator_5_current_print_thumbnail").state
                    == "unavailable"
                )
        read.return_value = PrinterStatus({**DETAIL, "estimatedTime": 60})
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.estimated_completion == dt_util.utcnow() + timedelta(seconds=60)
        diagnostics = str(await async_get_config_entry_diagnostics(hass, entry))
        assert "Test.3mf" not in diagnostics and "untrusted.invalid" not in diagnostics
        assert "SYNTHETIC-SN" not in diagnostics and "synthetic-code" not in diagnostics
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_thumbnail_no_poll_io_shared_cache_job_change_failure_and_unload(hass, freezer):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, minor_version=2)
    entry.add_to_hass(hass)
    png = color_png("#112233")
    with (
        patch(
            "custom_components.creator5.Creator5Client.get_status",
            new=AsyncMock(return_value=PrinterStatus(DETAIL)),
        ) as read,
        patch(
            "custom_components.creator5.Creator5Client.get_current_thumbnail",
            new=AsyncMock(return_value=(png, "image/png")),
        ) as thumbnail,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        thumbnail.assert_not_awaited()
        entity_id = "image.creator_5_current_print_thumbnail"
        images = await asyncio.gather(
            async_get_image(hass, entity_id), async_get_image(hass, entity_id)
        )
        assert all(image.content == png and image.content_type == "image/png" for image in images)
        assert thumbnail.await_count == 1 and read.await_count == 1
        first = hass.states.get(entity_id).state
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert thumbnail.await_count == 1
        assert hass.states.get(entity_id).state == first
        read.return_value = PrinterStatus({**DETAIL, "printFileName": "Next.3mf"})
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        thumbnail.side_effect = PrinterError("No image")
        from custom_components.creator5.image import Creator5JobThumbnail

        entity = next(e for e in hass.data["image"].entities if isinstance(e, Creator5JobThumbnail))
        assert await entity.async_image() is None
        assert await entity.async_image() is None
        assert thumbnail.await_count == 2
        freezer.tick(timedelta(seconds=61))
        thumbnail.side_effect = None
        assert await entity.async_image() == png
        assert thumbnail.await_count == 3
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert entity._image is None
        assert await entity.async_image() is None


async def test_thumbnail_discards_a_response_for_an_old_job(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, minor_version=2)
    entry.add_to_hass(hass)
    started, release = asyncio.Event(), asyncio.Event()

    async def delayed_image(_client):
        started.set()
        await release.wait()
        return color_png("#112233"), "image/png"

    with (
        patch(
            "custom_components.creator5.Creator5Client.get_status",
            new=AsyncMock(return_value=PrinterStatus(DETAIL)),
        ) as read,
        patch("custom_components.creator5.Creator5Client.get_current_thumbnail", new=delayed_image),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        from custom_components.creator5.image import Creator5JobThumbnail

        entity = next(e for e in hass.data["image"].entities if isinstance(e, Creator5JobThumbnail))
        request = asyncio.create_task(entity.async_image())
        await asyncio.wait_for(started.wait(), timeout=2)
        read.return_value = PrinterStatus({**DETAIL, "printFileName": "Different.3mf"})
        await entry.runtime_data.async_refresh()
        release.set()
        assert await request is None
        assert entity._image is None
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_invalid_estimates_and_disconnect_recovery_never_reuse_old_eta(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, minor_version=2)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(DETAIL)),
    ) as read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data
        read.side_effect = PrinterError("Disconnected")
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.estimated_completion is None
        assert hass.states.get("sensor.creator_5_estimated_finish_time").state == "unavailable"
        read.side_effect = None
        for remaining in (None, -1, True, "120", float("nan"), float("inf"), 1e12):
            read.return_value = PrinterStatus({**DETAIL, "estimatedTime": remaining})
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get("sensor.creator_5_estimated_finish_time").state == "unknown"
        read.return_value = PrinterStatus(DETAIL)
        await coordinator.async_refresh()
        assert coordinator.estimated_completion is not None
        assert await hass.config_entries.async_unload(entry.entry_id)
