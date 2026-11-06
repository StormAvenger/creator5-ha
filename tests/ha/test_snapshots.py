"""Alert pictures: light on, wait, capture, alert, restore; never a stuck light."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import callback
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import PrinterStatus
from custom_components.creator5.creator5py.client import ControlError
from custom_components.creator5.setup_panel import alert_config
from custom_components.creator5.snapshots import KEEP, async_save_snapshot

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
BASE = {"status": "ready", "model": "Creator 5 Pro", "errorCode": "", "lightStatus": "close"}
JPEG = b"\xff\xd8synthetic-frame\xff\xd9"
OPTIONS = {"alert_snapshots": True, "camera_enabled": True}


@pytest.fixture
def media(hass, tmp_path):
    hass.config.media_dirs = {"local": str(tmp_path)}
    return tmp_path


@pytest.fixture
def printer():
    """Synthetic printer whose light follows the commands sent to it."""
    state = dict(BASE)
    calls = []

    async def get_status():
        return PrinterStatus(dict(state))

    async def set_light(on):
        calls.append(on)
        state["lightStatus"] = "open" if on else "close"
        return PrinterStatus(dict(state))

    with (
        patch("custom_components.creator5.Creator5Client.get_status", side_effect=get_status),
        patch(
            "custom_components.creator5.Creator5Client.set_light", side_effect=set_light
        ) as light,
        patch(
            "custom_components.creator5.camera.Creator5Camera.async_camera_image",
            new=AsyncMock(return_value=JPEG),
        ) as camera,
        patch("custom_components.creator5._light_warmup", new=AsyncMock()) as warmup,
    ):
        yield state, calls, light, camera, warmup


def listen(hass):
    events = []

    @callback
    def record(event):
        events.append(dict(event.data))

    hass.bus.async_listen("creator5_event", record)
    return events


async def setup(hass, options=OPTIONS):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, options=options, minor_version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def complete_print(hass, entry, state):
    for fields in (
        {"status": "printing", "printFileName": "a.3mf", "printDuration": 0},
        {"status": "printing", "printFileName": "a.3mf", "printDuration": 60},
        {"status": "completed"},
    ):
        state.update(fields)
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done(wait_background_tasks=True)


async def test_light_on_wait_capture_alert_then_light_restored(hass, media, printer):
    state, calls, _light, camera, warmup = printer
    events = listen(hass)
    entry = await setup(hass)
    order = []
    warmup.side_effect = lambda seconds: order.append(("wait", seconds, list(calls)))
    camera.side_effect = lambda *a, **k: order.append(("capture", list(calls))) or JPEG
    await complete_print(hass, entry, state)
    assert order == [("wait", 10, [True]), ("capture", [True])]
    assert calls == [True, False]
    assert state["lightStatus"] == "close"
    (event,) = events
    assert event["kind"] == "completed"
    assert event["image"].startswith(f"/media/local/creator5/{entry.entry_id}/")
    assert event["image"].endswith("-completed.jpg")
    saved = list((media / "creator5" / entry.entry_id).glob("*.jpg"))
    assert [p.read_bytes() for p in saved] == [JPEG]
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("reported", ["open", None])
async def test_light_on_or_unknown_is_left_alone_and_not_waited_for(hass, media, printer, reported):
    state, calls, _light, _camera, warmup = printer
    state["lightStatus"] = reported
    events = listen(hass)
    entry = await setup(hass)
    await complete_print(hass, entry, state)
    assert calls == []
    warmup.assert_not_awaited()
    assert events[0]["image"] is not None
    assert state["lightStatus"] == reported
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("actually_on,expected_calls", [(False, [True]), (True, [True, False])])
async def test_unconfirmed_light_still_takes_picture_and_restores_only_if_on(
    hass, media, printer, actually_on, expected_calls
):
    state, calls, light, _camera, warmup = printer

    async def failing(on):
        calls.append(on)
        if on:
            # Firmware 2.0.0 style: no confirmation, but the LED may have changed.
            state["lightStatus"] = "open" if actually_on else "close"
            raise ControlError("request", "Control request failed; outcome unconfirmed")
        state["lightStatus"] = "close"
        return PrinterStatus(dict(state))

    light.side_effect = failing
    events = listen(hass)
    entry = await setup(hass)
    await complete_print(hass, entry, state)
    warmup.assert_not_awaited()
    assert events[0]["image"] is not None
    assert calls == expected_calls
    assert state["lightStatus"] == "close"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "options",
    [
        {"camera_enabled": True},  # pictures not enabled
        {"camera_enabled": False, "alert_snapshots": True},  # no camera entity
    ],
)
async def test_alert_without_pictures_is_immediate_and_never_touches_light(
    hass, media, printer, options
):
    state, calls, _light, camera, _warmup = printer
    events = listen(hass)
    entry = await setup(hass, options)
    await complete_print(hass, entry, state)
    assert [(e["kind"], e["image"]) for e in events] == [("completed", None)]
    assert calls == []
    camera.assert_not_awaited()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_zero_light_seconds_takes_picture_without_switching(hass, media, printer):
    state, calls, _light, _camera, warmup = printer
    events = listen(hass)
    entry = await setup(hass, {**OPTIONS, "snapshot_light_seconds": 0})
    await complete_print(hass, entry, state)
    assert calls == []
    warmup.assert_not_awaited()
    assert events[0]["image"] is not None
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_failed_capture_still_alerts_and_restores_light(hass, media, printer):
    state, calls, _light, camera, _warmup = printer
    camera.return_value = None
    events = listen(hass)
    entry = await setup(hass)
    await complete_print(hass, entry, state)
    assert [(e["kind"], e["image"]) for e in events] == [("completed", None)]
    assert calls == [True, False]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_snapshot_folder_keeps_only_recent_pictures(hass, media):
    for second in range(KEEP + 5):
        with patch(
            "custom_components.creator5.snapshots.dt_util.now",
            return_value=__import__("datetime").datetime(2026, 11, 6, 12, 0, second),
        ):
            await async_save_snapshot(hass, "entry", "error", JPEG)
    names = sorted(p.name for p in (media / "creator5" / "entry").glob("*.jpg"))
    assert len(names) == KEEP
    assert names[0] == "20261106-120005-error.jpg"
    assert await async_save_snapshot(hass, "entry", "offline", JPEG) is None
    assert await async_save_snapshot(hass, "entry", "error", b"not a jpeg") is None


async def test_generated_alerts_attach_picture_only_when_present(hass, media, printer):
    entry = await setup(hass)
    phone, panel = [], []

    async def record(call):
        phone.append(call.data)

    hass.services.async_register("notify", "mobile_app_synthetic_phone", record)
    hass.services.async_register(
        "persistent_notification", "create", lambda call: panel.append(call.data)
    )
    configs = [
        alert_config(entry, "notify.mobile_app_synthetic_phone", ["completed", "offline"]),
        alert_config(entry, "persistent_notification.create", ["completed"]),
    ]
    for index, config in enumerate(configs):
        config["id"] = f"synthetic-{index}"
    assert await async_setup_component(hass, "automation", {"automation": configs})
    image = f"/media/local/creator5/{entry.entry_id}/20261106-120000-completed.jpg"
    hass.bus.async_fire(
        "creator5_event",
        {"entry_id": entry.entry_id, "kind": "completed", "message": "Done.", "image": image},
    )
    hass.bus.async_fire(
        "creator5_event",
        {"entry_id": entry.entry_id, "kind": "offline", "message": "Lost.", "image": None},
    )
    await hass.async_block_till_done()
    assert phone[0]["data"] == {
        "image": image,
        "attachment": {"url": image, "content-type": "jpeg"},
    }
    assert phone[1]["message"] == "Lost."
    assert phone[1]["data"] == {}
    assert panel[0]["message"] == "Done. A camera picture was saved in Media → creator5."
    assert await hass.config_entries.async_unload(entry.entry_id)
