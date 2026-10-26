"""Explicit pause, resume and completion acknowledgement; no automatic actions."""

from homeassistant.components.button import ButtonEntity

from .const import CONF_SERIAL
from .control import Creator5Control


async def async_setup_entry(hass, entry, async_add_entities):
    if not entry.runtime_data.options["job_controls"]:
        return
    async_add_entities(
        [
            Creator5Button(entry.runtime_data, entry.data[CONF_SERIAL], action, name, states)
            for action, name, states in (
                ("pause", "Pause print", ("printing",)),
                ("resume", "Resume print", ("paused", "pause")),
                ("dismiss_completion", "Acknowledge completed print", ("completed",)),
            )
        ]
    )


class Creator5Button(Creator5Control, ButtonEntity):
    def __init__(self, coordinator, serial, action, name, states):
        super().__init__(coordinator, serial, action, name, "job_controls", states)
        self._action = action

    async def async_press(self):
        await self._run(self._action)
