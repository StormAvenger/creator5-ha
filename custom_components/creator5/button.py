"""Explicit pause, resume and completion acknowledgement; no automatic actions."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_SERIAL
from .control import Creator5Control
from .entity import Creator5Entity
from .history import MAINTENANCE


async def async_setup_entry(hass, entry, async_add_entities):
    c, serial = entry.runtime_data, entry.data[CONF_SERIAL]
    entities = [Creator5RecordService(c, serial, key) for key in MAINTENANCE]
    if c.options["job_controls"]:
        entities += [
            Creator5Button(c, serial, action, name, states)
            for action, name, states in (
                ("pause", "Pause print", ("printing",)),
                ("resume", "Resume print", ("paused", "pause")),
                ("dismiss_completion", "Acknowledge completed print", ("completed",)),
            )
        ]
    async_add_entities(entities)


class Creator5Button(Creator5Control, ButtonEntity):
    def __init__(self, coordinator, serial, action, name, states):
        super().__init__(coordinator, serial, action, name, "job_controls", states)
        self._action = action

    async def async_press(self):
        await self._run(self._action)


class Creator5RecordService(Creator5Entity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, serial, key):
        super().__init__(coordinator, serial, f"record_{key}", f"Record {MAINTENANCE[key].lower()}")
        self._key = key

    @property
    def available(self):
        return super().available and self.coordinator.data.lifetime_print_hours is not None

    async def async_press(self):
        try:
            self.coordinator.record_service(self._key)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
