"""Local persistence, meaningful events, cooling, maintenance and verified errors."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import callback
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import PrinterError, PrinterStatus
from custom_components.creator5.diagnostics import async_get_config_entry_diagnostics
from custom_components.creator5.error_info import explanation
from custom_components.creator5.history import PrintHistory, finite_number
from custom_components.creator5.settings import validated_options

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
BASE = {
    "status": "ready",
    "model": "Creator 5 Pro",
    "errorCode": "",
    "firmwareVersion": "2.0.0",
    "cumulativePrintTime": 600,
    "platTemp": 25,
    "platTargetTemp": 0,
}


async def setup(hass, options=None):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, options=options or {}, minor_version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def listen(hass):
    events = []

    @callback
    def record(event):
        events.append(event.data)

    hass.bus.async_listen("creator5_event", record)
    return events


async def update(hass, entry, read, **fields):
    read.return_value = PrinterStatus({**BASE, **fields})
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_summary_completion_once_cooling_latch_and_local_reload(hass):
    events = listen(hass)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(BASE)),
    ) as read:
        entry = await setup(hass)
        await update(
            hass, entry, read, status="printing", printFileName="sample.3mf", printDuration=0
        )
        await update(
            hass, entry, read, status="printing", printFileName="sample.3mf", printDuration=120
        )
        await update(hass, entry, read, status="completed", printDuration=0, platTemp=60)
        summary = hass.states.get("sensor.creator_5_last_print")
        assert summary.state == "completed"
        assert summary.attributes["filename"] == "sample.3mf"
        assert summary.attributes["duration_seconds"] == 120
        assert summary.attributes["incomplete"] is False
        assert hass.states.get("binary_sensor.creator_5_bed_cooled_after_print").state == "off"
        await update(hass, entry, read, status="completed", platTemp=40)
        assert len(events) == 1  # threshold is below, not equal
        await update(hass, entry, read, platTemp=39)
        assert hass.states.get("binary_sensor.creator_5_bed_cooled_after_print").state == "on"
        await update(hass, entry, read, platTemp=38)
        await update(hass, entry, read, platTemp=60, platTargetTemp=70)
        assert hass.states.get("binary_sensor.creator_5_bed_cooled_after_print").state == "off"
        await update(hass, entry, read, platTemp=30)
        assert [e["kind"] for e in events] == ["completed", "bed_cooled"]
        assert all("sample.3mf" not in e["message"] for e in events)
        assert all(DATA["serial_number"] not in str(e) for e in events)
        assert await hass.config_entries.async_unload(entry.entry_id)
        read.return_value = PrinterStatus(BASE)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.creator_5_last_print").attributes["filename"] == "sample.3mf"
        assert len(events) == 2  # reload does not replay old alerts
        report = await async_get_config_entry_diagnostics(hass, entry)
        assert "sample.3mf" not in str(report)
        assert "last_job" not in report
        read.side_effect = PrinterError("Offline")
        await entry.runtime_data.async_refresh()
        assert hass.states.get("sensor.creator_5_last_print").state == "completed"
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("end,outcome", [("ready", "unconfirmed"), ("cancel", "cancelled")])
async def test_missing_completion_and_cancel_are_not_success(hass, end, outcome):
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(BASE)),
    ) as read:
        entry = await setup(hass)
        await update(
            hass, entry, read, status="printing", printFileName="sample.3mf", printDuration=500
        )
        await update(hass, entry, read, status=end)
        state = hass.states.get("sensor.creator_5_last_print")
        assert state.state == outcome
        assert state.attributes["incomplete"] is True
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_active_restart_gap_disconnect_and_same_name_new_job_are_partial(hass):
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(BASE)),
    ) as read:
        entry = await setup(hass)
        await update(
            hass, entry, read, status="printing", printFileName="sample.3mf", printDuration=0
        )
        await update(
            hass, entry, read, status="printing", printFileName="sample.3mf", printDuration=100
        )
        assert await hass.config_entries.async_unload(entry.entry_id)
        read.return_value = PrinterStatus(
            {**BASE, "status": "printing", "printFileName": "sample.3mf", "printDuration": 110}
        )
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.history.active["incomplete"] is True
        await update(
            hass, entry, read, status="printing", printFileName="sample.3mf", printDuration=0
        )
        assert entry.runtime_data.history.last_job["outcome"] == "unconfirmed"
        assert entry.runtime_data.history.active["incomplete"] is True
        read.side_effect = PrinterError("Offline")
        await entry.runtime_data.async_refresh()
        assert entry.runtime_data.history.active["incomplete"] is True
        read.side_effect = None
        await update(hass, entry, read, status="completed")
        assert entry.runtime_data.history.last_job["incomplete"] is True
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_offline_and_pause_alerts_are_delayed_once_and_cancel_on_recovery(hass, freezer):
    events = listen(hass)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(BASE)),
    ) as read:
        entry = await setup(hass, {"offline_alert_minutes": 1, "pause_alert_minutes": 1})
        await update(
            hass, entry, read, status="paused", printFileName="sample.3mf", printDuration=10
        )
        freezer.tick(timedelta(seconds=59))
        async_fire_time_changed(hass, datetime.now(UTC))
        await hass.async_block_till_done()
        assert not events
        freezer.tick(timedelta(seconds=2))
        async_fire_time_changed(hass, datetime.now(UTC))
        await hass.async_block_till_done()
        assert [e["kind"] for e in events] == ["prolonged_pause"]
        freezer.tick(timedelta(minutes=2))
        async_fire_time_changed(hass, datetime.now(UTC))
        await hass.async_block_till_done()
        assert len(events) == 1
        read.side_effect = PrinterError("Offline")
        await entry.runtime_data.async_refresh()
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass, datetime.now(UTC))
        await hass.async_block_till_done()
        assert [e["kind"] for e in events] == ["prolonged_pause", "offline"]
        freezer.tick(timedelta(minutes=2))
        async_fire_time_changed(hass, datetime.now(UTC))
        await hass.async_block_till_done()
        assert len(events) == 2
        read.side_effect = None
        await update(hass, entry, read)
        read.side_effect = PrinterError("Offline")
        await entry.runtime_data.async_refresh()
        read.side_effect = None
        await update(hass, entry, read)
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass, datetime.now(UTC))
        await hass.async_block_till_done()
        assert len(events) == 2
        coordinator = entry.runtime_data
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert coordinator._pause_timer is None
        assert coordinator._offline_timer is None


async def test_error_hints_are_verified_and_notify_once_per_error_without_startup_replay(hass):
    events = listen(hass)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus({**BASE, "errorCode": "E0162"})),
    ) as read:
        entry = await setup(hass)
        assert not events
        state = hass.states.get("sensor.creator_5_error_explanation")
        assert "Filament" in state.state
        assert state.attributes["recognized"] is True
        for _ in range(3):
            await update(hass, entry, read, errorCode="E0162")
        assert not events
        await update(hass, entry, read, errorCode="E9998")
        assert len(events) == 1
        state = hass.states.get("sensor.creator_5_error_explanation")
        assert state.state == "Unrecognized printer error"
        assert state.attributes["code"] == "E9998"
        assert state.attributes["recognized"] is False
        await update(hass, entry, read, errorCode="E9998")
        assert len(events) == 1
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_maintenance_hours_reset_button_counter_reset_and_no_printer_writes(hass):
    events = listen(hass)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(BASE)),
    ) as read:
        entry = await setup(hass, {"bed_cleaning_hours": 2})
        assert hass.states.get("sensor.creator_5_bed_cleaning_remaining").state == "2.0"
        assert hass.states.get("binary_sensor.creator_5_rail_lubrication_due").state == "unknown"
        await update(hass, entry, read, cumulativePrintTime=720)
        assert hass.states.get("binary_sensor.creator_5_bed_cleaning_due").state == "on"
        assert [e["kind"] for e in events] == ["maintenance"]
        await update(hass, entry, read, cumulativePrintTime=721)
        assert len(events) == 1
        requests = read.await_count
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.creator_5_record_bed_cleaning"}, blocking=True
        )
        assert read.await_count == requests
        assert hass.states.get("sensor.creator_5_bed_cleaning_remaining").state == "2.0"
        assert hass.states.get("binary_sensor.creator_5_bed_cleaning_due").state == "off"
        await update(hass, entry, read, cumulativePrintTime=0)
        assert hass.states.get("sensor.creator_5_bed_cleaning_remaining").state == "unknown"
        assert (
            hass.states.get("sensor.creator_5_bed_cleaning_remaining").attributes["counter_reset"]
            is True
        )
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "options",
    [
        {"bed_cooled_c": 19},
        {"bed_cooled_c": 71},
        {"bed_cleaning_hours": -1},
        {"rail_lubrication_hours": 1.5},
        {"nozzle_inspection_hours": True},
        {"pause_alert_minutes": 0},
        {"offline_alert_minutes": 31},
    ],
)
def test_invalid_usability_preferences(options):
    with pytest.raises(ValueError):
        validated_options(options, DATA["host"])


@pytest.mark.parametrize(
    "code",
    ["E0162", "E0163", "E0166", "E0169", "E0051", "E0054", "E0063", "E0066", "E0077", "E0123"],
)
def test_verified_vendor_code_explanations(code):
    title, hint, known = explanation(PrinterStatus({"errorCode": code, "model": "Creator 5 Pro"}))
    assert known and title and hint


async def test_malformed_local_store_is_bounded_and_rejects_untrusted_job_data(hass):
    assert finite_number(10**400) is None
    history = PrintHistory(hass, "synthetic")
    await history.store.async_save(
        {
            "active": {"filename": "../../secret", "started_at": "invalid"},
            "last_job": {"filename": "x" * 300},
            "maintenance": {"bed_cleaning": {"baseline": 10**18}},
            "bed_cooled": "yes",
        }
    )
    restored = PrintHistory(hass, "synthetic")
    await restored.async_load()
    assert restored.active is None and restored.last_job is None
    assert restored.maintenance == {} and restored.bed_cooled is None


async def test_progress_checkpoints_are_throttled_without_postponing_forever(hass):
    history = PrintHistory(hass, "synthetic-throttling")
    options = validated_options({}, DATA["host"])
    now = datetime.now(UTC)
    with patch.object(history.store, "async_delay_save") as save:
        history.observe(
            PrinterStatus(
                {**BASE, "status": "printing", "printFileName": "sample.3mf", "printDuration": 0}
            ),
            now,
            options,
        )
        assert save.call_count == 1
        save.call_args.args[0]()  # initial checkpoint completes
        for second in range(10, 70, 10):
            history.observe(
                PrinterStatus(
                    {
                        **BASE,
                        "status": "printing",
                        "printFileName": "sample.3mf",
                        "printDuration": second,
                    }
                ),
                now + timedelta(seconds=second),
                options,
            )
        assert save.call_count == 2
        saved = save.call_args.args[0]()
        assert saved["active"]["duration_seconds"] == 60
        history.observe(
            PrinterStatus(
                {**BASE, "status": "printing", "printFileName": "sample.3mf", "printDuration": 70}
            ),
            now + timedelta(seconds=70),
            options,
        )
        assert save.call_count == 3


def test_known_code_without_creator_model_is_not_labeled_verified():
    assert explanation(PrinterStatus({"errorCode": "E0162"}))[2] is False


async def test_cooling_requires_completion_valid_readings_and_an_off_target(hass):
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(BASE)),
    ) as read:
        entry = await setup(hass)
        assert hass.states.get("binary_sensor.creator_5_bed_cooled_after_print").state == "unknown"
        await update(
            hass, entry, read, status="printing", printFileName="sample.3mf", printDuration=0
        )
        await update(hass, entry, read, status="completed", platTemp=30, platTargetTemp=60)
        assert hass.states.get("binary_sensor.creator_5_bed_cooled_after_print").state == "off"
        await update(hass, entry, read, platTemp=None)
        assert hass.states.get("binary_sensor.creator_5_bed_cooled_after_print").state == "unknown"
        await update(hass, entry, read, platTemp=30)
        assert hass.states.get("binary_sensor.creator_5_bed_cooled_after_print").state == "on"
        await update(hass, entry, read, status="heating", platTemp=30)
        assert hass.states.get("binary_sensor.creator_5_bed_cooled_after_print").state == "unknown"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_initial_already_printing_is_incomplete_even_with_a_small_elapsed_time(hass):
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(
            return_value=PrinterStatus(
                {**BASE, "status": "printing", "printFileName": "sample.3mf", "printDuration": 5}
            )
        ),
    ):
        entry = await setup(hass)
        assert entry.runtime_data.history.active["incomplete"] is True
        assert await hass.config_entries.async_unload(entry.entry_id)
