"""Synthetic wire tests: no command ever reaches a physical printer."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from creator5py import PrinterError, PrinterStatus
from test_client import SequenceSession, Session, client

READY = {"status": "ready", "model": "Creator 5 Pro", "firmwareVersion": "2.0.0"}


def detail(**values):
    return {"code": 0, "detail": {**READY, **values}}


def command(session):
    writes = [kwargs for url, kwargs in session.calls if url.endswith("/control")]
    assert len(writes) == 1
    assert writes[0]["allow_redirects"] is False
    return writes[0]["json"]["payload"]


@pytest.mark.parametrize(
    "action,before,after,cmd,args",
    [
        ("pause", "printing", "paused", "jobCtl_cmd", {"action": "pause", "jobID": ""}),
        ("resume", "paused", "printing", "jobCtl_cmd", {"action": "continue", "jobID": ""}),
        (
            "dismiss_completion",
            "completed",
            "ready",
            "stateCtrl_cmd",
            {"action": "setClearPlatform"},
        ),
    ],
)
async def test_job_action_checks_current_state_and_verified_result(
    action, before, after, cmd, args
):
    session = SequenceSession([detail(status=before), {"code": 0}, detail(status=after)])
    result = await getattr(client(session), action)()
    assert result.state == after
    assert command(session) == {"cmd": cmd, "args": args}


@pytest.mark.parametrize(
    "action,state",
    [
        ("pause", "ready"),
        ("resume", "printing"),
        ("dismiss_completion", "printing"),
        ("dismiss_completion", "ready"),
        ("pause", "heating"),
        ("resume", "completed"),
    ],
)
async def test_job_state_guards_prevent_writes(action, state):
    session = SequenceSession([detail(status=state)])
    with pytest.raises(PrinterError, match="current printer state"):
        await getattr(client(session), action)()
    assert len(session.calls) == 1
    assert session.calls[0][0].endswith("/detail")


@pytest.mark.parametrize("value", [True, 0, 49, 151, 500, 100.5, "100", float("nan")])
async def test_speed_validation_precedes_network(value):
    session = Session(None)
    with pytest.raises(ValueError):
        await client(session).set_speed(value)
    assert not session.calls


async def test_speed_changes_no_other_setting():
    session = SequenceSession(
        [detail(status="printing"), {"code": 0}, detail(status="printing", printSpeedAdjust=90)]
    )
    await client(session).set_speed(90)
    assert command(session) == {"cmd": "printerCtl_cmd", "args": {"speed": 90}}


@pytest.mark.parametrize(
    "heater,target,field,expected",
    [
        ("bed", 0, "platTargetTemp", -100),
        ("bed", 70, "platTargetTemp", 70),
        ("chamber", 0, "chamberTargetTemp", -100),
        ("chamber", 60, "chamberTargetTemp", 60),
    ],
)
async def test_scalar_temperature_off_sentinels_and_untouched_nozzles(
    heater, target, field, expected
):
    session = SequenceSession([detail(), {"code": 0}, detail(**{field: target})])
    await client(session).set_temperature(heater, target)
    args = command(session)["args"]
    assert args == {
        "platform": expected if heater == "bed" else -200,
        "chamber": expected if heater == "chamber" else -200,
        "nozzles": [-200] * 4,
    }


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("target", [0, 215])
async def test_four_tool_array_only_changes_requested_target(index, target):
    targets = [140] * 4
    targets[index] = target
    session = SequenceSession([detail(), {"code": 0}, detail(nozzleTargetTemps=targets)])
    await client(session).set_temperature(f"tool_{index + 1}", target)
    expected = [-200] * 4
    expected[index] = target
    assert command(session)["args"] == {"platform": -200, "chamber": -200, "nozzles": expected}


@pytest.mark.parametrize(
    "heater,target",
    [
        ("bed", 121),
        ("chamber", 66),
        ("tool_1", 321),
        ("tool_4", -100),
        ("tool_5", 100),
        ("bed", True),
        ("bed", 20.5),
        ("bed", float("inf")),
    ],
)
async def test_temperature_limits_reject_before_io(heater, target):
    session = Session(None)
    with pytest.raises(ValueError):
        await client(session).set_temperature(heater, target)
    assert not session.calls


async def test_chamber_control_requires_pro_identification():
    session = SequenceSession([detail(model="Creator 5")])
    with pytest.raises(PrinterError, match="model"):
        await client(session).set_temperature("chamber", 50)
    assert len(session.calls) == 1


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"enabled": True}, {"automaticShutdown": "open", "shutdownAfterTime": 30}),
        ({"enabled": False}, {"automaticShutdown": "close", "shutdownAfterTime": 30}),
        ({"minutes": 45}, {"automaticShutdown": "close", "shutdownAfterTime": 45}),
    ],
)
async def test_shutdown_edit_preserves_fresh_unedited_field(change, expected):
    session = SequenceSession(
        [
            detail(autoShutdown="close", autoShutdownTime=30),
            {"code": 0},
            detail(
                autoShutdown=expected["automaticShutdown"],
                autoShutdownTime=expected["shutdownAfterTime"],
            ),
        ]
    )
    await client(session).set_auto_shutdown(**change)
    assert command(session) == {"cmd": "delayClose_cmd", "args": expected}


@pytest.mark.parametrize("change", [{"enabled": True}, {"minutes": 45}])
async def test_shutdown_cannot_edit_printing_printer(change):
    session = SequenceSession([detail(status="printing")])
    with pytest.raises(PrinterError, match="state"):
        await client(session).set_auto_shutdown(**change)
    assert len(session.calls) == 1


def slot(material="PLA", color="#FFFFFF"):
    return {"slotId": 2, "materialName": material, "materialColor": color}


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"material": "PETG"}, {"slot": 2, "mt": "PETG", "rgb": "#FFFFFF"}),
        ({"color": "#1B1B1B"}, {"slot": 2, "mt": "PLA", "rgb": "#1B1B1B"}),
    ],
)
async def test_slot_metadata_preserves_other_field_and_exact_wire_palette(change, expected):
    session = SequenceSession(
        [
            detail(matlStationInfo={"slotInfos": [slot()]}),
            {"code": 0},
            detail(matlStationInfo={"slotInfos": [slot(expected["mt"], expected["rgb"])]}),
        ]
    )
    await client(session).set_slot(2, **change)
    assert command(session) == {"cmd": "msConfig_cmd", "args": expected}


@pytest.mark.parametrize(
    "slot_id,kwargs",
    [
        (True, {"material": "PLA"}),
        (5, {"material": "PLA"}),
        (1, {"color": "#ffffff"}),
        (1, {"color": "#123456"}),
        (1, {"material": "anything"}),
        (1, {}),
    ],
)
async def test_invalid_slot_inputs_never_reach_network(slot_id, kwargs):
    session = Session(None)
    with pytest.raises(ValueError):
        await client(session).set_slot(slot_id, **kwargs)
    assert not session.calls


async def test_unknown_slot_metadata_is_not_silently_overwritten():
    session = SequenceSession([detail(matlStationInfo={"slotInfos": [slot("NEW-MATERIAL")]})])
    with pytest.raises(PrinterError, match="unsupported"):
        await client(session).set_slot(2, color="#1B1B1B")
    assert len(session.calls) == 1


async def test_false_success_allows_only_read_rechecks_not_command_retries(monkeypatch):
    monkeypatch.setattr("creator5py.client.asyncio.sleep", AsyncMock())
    session = SequenceSession(
        [detail(status="completed"), {"code": 0}] + [detail(status="completed")] * 3
    )
    with pytest.raises(PrinterError, match="did not confirm"):
        await client(session).dismiss_completion()
    assert command(session)["cmd"] == "stateCtrl_cmd"
    assert len(session.calls) == 5


async def test_late_readback_confirms_once_without_resending(monkeypatch):
    monkeypatch.setattr("creator5py.client.asyncio.sleep", AsyncMock())
    session = SequenceSession(
        [detail(status="printing"), {"code": 0}, detail(status="pausing"), detail(status="paused")]
    )
    await client(session).pause()
    assert command(session)["args"]["action"] == "pause"
    assert len(session.calls) == 4


async def test_control_timeout_explains_uncertain_outcome_without_retry():
    session = SequenceSession([{"code": 0}])
    session.responses = iter([__import__("test_client").Response(TimeoutError())])
    with pytest.raises(PrinterError, match="outcome is unconfirmed"):
        await client(session).set_light(True)
    assert len(session.calls) == 1


async def test_poll_cannot_overlap_light_command_and_readback():
    printer = client(Session(None))
    entered, release = asyncio.Event(), asyncio.Event()
    events = []

    async def request(endpoint, body):
        events.append(endpoint)
        if endpoint == "/control":
            entered.set()
            await release.wait()
            return {"code": 0}
        return detail(lightStatus="open")

    printer._request = request
    task = asyncio.create_task(printer.set_light(True))
    await asyncio.wait_for(entered.wait(), 1)
    poll = asyncio.create_task(printer.get_status())
    await asyncio.sleep(0)
    assert events == ["/control"]
    release.set()
    await asyncio.wait_for(asyncio.gather(task, poll), 1)
    assert events == ["/control", "/detail", "/detail"]


@pytest.mark.parametrize("value", [True, -1, "2", 5, None])
def test_station_slot_validation(value):
    assert (
        PrinterStatus({"matlStationInfo": {"currentSlot": value}}).station_number("currentSlot")
        is None
    )


def test_station_fields_do_not_infer_active_tool_or_meaning_of_action_codes():
    status = PrinterStatus(
        {
            "matlStationInfo": {
                "currentSlot": 0,
                "currentLoadSlot": 4,
                "stateAction": 7,
                "stateStep": 12,
            }
        }
    )
    assert status.station_number("currentSlot") == 0
    assert status.station_number("currentLoadSlot") == 4
    assert status.station_number("stateAction") == 7
    assert status.station_number("stateStep") == 12


async def test_light_ack_followed_by_status_timeout_identifies_verification_stage():
    from creator5py.client import ControlError
    from test_client import Response

    session = SequenceSession([])
    session.responses = iter([Response({"code": 0}), Response(TimeoutError())])
    with pytest.raises(ControlError, match="status verification failed") as error:
        await client(session).set_light(True)
    assert error.value.stage == "readback"
    assert len(session.calls) == 2
    assert command(session)["cmd"] == "lightControl_cmd"


@pytest.mark.parametrize(
    "action", ["set_slot", "set_auto_shutdown", "set_speed", "set_temperature"]
)
async def test_new_controls_recheck_fresh_state_before_any_write(action):
    session = SequenceSession([detail(status="calibrating")])
    printer = client(session)
    with pytest.raises(PrinterError, match="current printer state"):
        if action == "set_slot":
            await printer.set_slot(1, material="PLA")
        elif action == "set_auto_shutdown":
            await printer.set_auto_shutdown(enabled=True)
        elif action == "set_speed":
            await printer.set_speed(100)
        else:
            await printer.set_temperature("bed", 60)
    assert len(session.calls) == 1
    assert session.calls[0][0].endswith("/detail")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"minutes": 0},
        {"minutes": 121},
        {"minutes": True},
        {"minutes": 1.5},
        {"enabled": "open"},
        {},
    ],
)
async def test_shutdown_invalid_arguments_never_send_a_request(kwargs):
    session = Session(None)
    with pytest.raises(ValueError):
        await client(session).set_auto_shutdown(**kwargs)
    assert not session.calls


@pytest.mark.parametrize("value", [None, True, -1, "12", float("nan"), float("inf")])
def test_invalid_lifetime_filament_remains_unknown(value):
    assert PrinterStatus({"cumulativeFilament": value}).lifetime_filament_m is None
