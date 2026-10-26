"""Bounded local job summary and maintenance records; never sent to diagnostics."""

from copy import deepcopy
from datetime import datetime, timedelta

from homeassistant.helpers.storage import Store

from .creator5py import PrinterStatus

MAINTENANCE = {
    "bed_cleaning": "Bed cleaning",
    "rail_lubrication": "Rail lubrication",
    "nozzle_inspection": "Nozzle inspection",
}
ACTIVE = ("printing", "paused", "pause")


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return value if parsed.tzinfo is not None else None
    except ValueError:
        return None


def finite_number(value, maximum=100_000_000):
    return float(value) if type(value) in (int, float) and 0 <= value <= maximum else None


def clean_job(value, *, active=False):
    if not isinstance(value, dict):
        return None
    filename = PrinterStatus(
        {"status": "printing", "printFileName": value.get("filename")}
    ).current_filename
    started = timestamp(value.get("started_at"))
    if filename is None or started is None:
        return None
    job = {
        "filename": filename,
        "started_at": started,
        "duration_seconds": finite_number(value.get("duration_seconds"), 366 * 86400),
        "incomplete": bool(value.get("incomplete", True)),
    }
    if not active:
        finished = timestamp(value.get("finished_at"))
        if finished is None or value.get("outcome") not in (
            "completed",
            "cancelled",
            "unconfirmed",
        ):
            return None
        job.update(finished_at=finished, outcome=value["outcome"])
    return job


class PrintHistory:
    def __init__(self, hass, entry_id):
        self.store = Store(hass, 1, f"creator5.{entry_id}.history", serialize_in_event_loop=True)
        self.active = None
        self.last_job = None
        self.cooling_pending = False
        self.bed_cooled = None
        self.maintenance = {}
        self.cooling_notified = False
        self.last_lifetime = None
        self._previous_state = None
        self._dirty = False
        self._save_deadline = None
        self.hass = hass

    async def async_load(self):
        data = await self.store.async_load()
        if not isinstance(data, dict):
            return
        self.active = clean_job(data.get("active"), active=True)
        if self.active:
            self.active["incomplete"] = True  # HA could not observe the restart gap.
        self.last_job = clean_job(data.get("last_job"))
        self.cooling_pending = data.get("cooling_pending") is True
        self.cooling_notified = data.get("cooling_notified") is True
        self.last_lifetime = finite_number(data.get("last_lifetime"))
        self.bed_cooled = data.get("bed_cooled") if type(data.get("bed_cooled")) is bool else None
        marks = data.get("maintenance", {})
        for key in MAINTENANCE:
            mark = marks.get(key) if isinstance(marks, dict) else None
            if isinstance(mark, dict) and finite_number(mark.get("baseline")) is not None:
                self.maintenance[key] = {
                    "baseline": float(mark["baseline"]),
                    "recorded_at": timestamp(mark.get("recorded_at")),
                    "invalid": mark.get("invalid") is True,
                }

    def _snapshot(self):
        return deepcopy(
            {
                "active": self.active,
                "last_job": self.last_job,
                "cooling_pending": self.cooling_pending,
                "bed_cooled": self.bed_cooled,
                "maintenance": self.maintenance,
                "cooling_notified": self.cooling_notified,
                "last_lifetime": self.last_lifetime,
            }
        )

    def save_later(self, *, soon=False):
        self._dirty = True
        delay = 1 if soon else 60
        deadline = self.hass.loop.time() + delay
        if self._save_deadline is None or deadline < self._save_deadline:
            self._save_deadline = deadline
            self.store.async_delay_save(self._scheduled_snapshot, delay)

    def _scheduled_snapshot(self):
        self._save_deadline = None
        return self._snapshot()

    async def async_close(self):
        if self._dirty:
            await self.store.async_save(self._snapshot())

    def missed_update(self):
        self._previous_state = None
        if self.active and not self.active["incomplete"]:
            self.active["incomplete"] = True
            self.save_later(soon=True)

    def _finish(self, outcome, now):
        self.last_job = {**self.active, "outcome": outcome, "finished_at": now.isoformat()}
        if outcome == "unconfirmed":
            self.last_job["incomplete"] = True
        self.active = None
        self.cooling_pending = outcome == "completed"
        self.cooling_notified = False
        self.bed_cooled = False if self.cooling_pending else None
        self.save_later(soon=True)

    def observe(self, status, now, options):
        events = []
        filename = status.current_filename
        if self.active and status.state in ACTIVE and filename is None:
            self.missed_update()
        duration = status.nonnegative("printDuration", maximum=366 * 86400)
        if status.state in ACTIVE and filename is not None:
            old_duration = self.active["duration_seconds"] if self.active else None
            restarted = (
                old_duration is not None
                and duration is not None
                and duration + 2 * options["poll_seconds"] < old_duration
            )
            if self.active and (filename != self.active["filename"] or restarted):
                self._finish("unconfirmed", now)
            if self.active is None:
                self.active = {
                    "filename": filename,
                    "started_at": (now - timedelta(seconds=duration or 0)).isoformat(),
                    "duration_seconds": duration,
                    "incomplete": (
                        duration is None
                        or duration > 2 * options["poll_seconds"]
                        or restarted
                        or self._previous_state
                        not in ("ready", "heating", "completed", "cancel", "cancelled", "canceled")
                    ),
                }
                self.cooling_pending, self.bed_cooled = False, None
                self.save_later(soon=True)
            elif duration is not None:
                self.active["duration_seconds"] = duration
                self.save_later()
        elif self.active and status.state in (
            "completed",
            "cancel",
            "cancelled",
            "canceled",
            "ready",
        ):
            outcome = {"completed": "completed", "ready": "unconfirmed"}.get(
                status.state, "cancelled"
            )
            # Some firmware resets elapsed time to zero on completion. Preserve
            # the last active reading rather than reporting a zero-length job.
            if duration is not None and duration >= (self.active["duration_seconds"] or 0):
                self.active["duration_seconds"] = duration
            self._finish(outcome, now)
            if outcome == "completed":
                events.append("completed")
        # A new observed heating job invalidates the previous job's cool state.
        if status.state == "heating" and self.active is None and self.cooling_pending:
            self.cooling_pending, self.bed_cooled = False, None
            self.save_later(soon=True)
        if self.cooling_pending and status.state in ("completed", "ready"):
            bed = status.nonnegative("platTemp", maximum=150)
            target = status.nonnegative("platTargetTemp", maximum=150)
            if bed is None or target is None:
                if self.bed_cooled is not None:
                    self.bed_cooled = None
                    self.save_later()
            else:
                cooled = target == 0 and bed < options["bed_cooled_c"]
                # Alert once per completion while the indicator follows current readings.
                if cooled and not self.cooling_notified:
                    self.cooling_notified = True
                    events.append("bed_cooled")
                    self.save_later(soon=True)
                if cooled != self.bed_cooled:
                    self.bed_cooled = cooled
                    self.save_later()
        lifetime = status.lifetime_print_hours
        if lifetime is not None:
            if self.last_lifetime is not None and lifetime < self.last_lifetime:
                for mark in self.maintenance.values():
                    mark["invalid"] = True
                self.save_later(soon=True)
            if lifetime != self.last_lifetime:
                self.last_lifetime = lifetime
                self.save_later()
            for key in MAINTENANCE:
                if options[f"{key}_hours"] > 0 and key not in self.maintenance:
                    self.maintenance[key] = {
                        "baseline": lifetime,
                        "recorded_at": None,
                        "invalid": False,
                    }
                    self.save_later(soon=True)
        self._previous_state = status.state
        return events

    def remaining(self, key, lifetime, options):
        interval = options[f"{key}_hours"]
        mark = self.maintenance.get(key)
        if (
            not interval
            or lifetime is None
            or mark is None
            or mark.get("invalid")
            or lifetime < mark["baseline"]
        ):
            return None
        return max(0, interval - (lifetime - mark["baseline"]))

    def record_service(self, key, lifetime, now):
        if key not in MAINTENANCE or lifetime is None:
            raise ValueError("A valid printer lifetime reading is required to record maintenance")
        self.maintenance[key] = {
            "baseline": lifetime,
            "recorded_at": now.isoformat(),
            "invalid": False,
        }
        self.save_later(soon=True)
