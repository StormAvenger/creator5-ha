"""Local credentials are stored by Home Assistant in its config entry."""

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_CHECK_CODE, CONF_SERIAL, DOMAIN
from .creator5py import AuthenticationError, Creator5Client, PrinterError
from .creator5py.client import private_address
from .creator5py.discovery import discover_identity
from .settings import CONTROL_GROUPS, validated_options


class Creator5ConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return Creator5OptionsFlow()

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            data = {**entry.data, CONF_CHECK_CODE: user_input[CONF_CHECK_CODE].strip()}
            try:
                await Creator5Client(
                    async_get_clientsession(self.hass),
                    data[CONF_HOST],
                    data[CONF_SERIAL],
                    data[CONF_CHECK_CODE],
                ).get_status()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except PrinterError:
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_config"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CHECK_CODE): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                }
            ),
        )

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            check_code = user_input[CONF_CHECK_CODE].strip()
            try:
                private_address(host)
                if not check_code:
                    raise ValueError("Empty LAN code")
            except ValueError:
                errors["base"] = "invalid_config"
            else:
                try:
                    # One directed identity request; never scan or broadcast.
                    identity = await discover_identity(host)
                except PrinterError:
                    errors["base"] = "discovery_failed"
                else:
                    expected_model = {40: "Creator 5", 41: "Creator 5 Pro"}.get(identity.product_id)
                    if expected_model is None:
                        errors["base"] = "unsupported_model"
                    else:
                        await self.async_set_unique_id(identity.serial)
                        self._abort_if_unique_id_configured()
                        data = {
                            CONF_HOST: host,
                            CONF_SERIAL: identity.serial,
                            CONF_CHECK_CODE: check_code,
                        }
                        try:
                            status = await Creator5Client(
                                async_get_clientsession(self.hass),
                                host,
                                identity.serial,
                                check_code,
                            ).get_status()
                        except AuthenticationError:
                            errors["base"] = "invalid_auth"
                        except PrinterError:
                            errors["base"] = "cannot_connect"
                        except ValueError:
                            errors["base"] = "invalid_config"
                        else:
                            if status.model != expected_model:
                                errors["base"] = "model_mismatch"
                            else:
                                return self.async_create_entry(title=status.model, data=data)
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_CHECK_CODE): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                }
            ),
        )


class Creator5OptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                options = validated_options(user_input, self.config_entry.data[CONF_HOST])
            except ValueError:
                errors["base"] = "invalid_options"
            else:
                return self.async_create_entry(title="", data=options)
        current = validated_options(self.config_entry.options, self.config_entry.data[CONF_HOST])
        schema = {
            vol.Required("poll_seconds", default=current["poll_seconds"]): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5, max=300, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required("camera_enabled", default=current["camera_enabled"]): bool,
            vol.Required("show_setup_sidebar", default=current["show_setup_sidebar"]): bool,
            vol.Required("file_controls", default=current["file_controls"]): bool,
            vol.Optional("camera_stream_url", default=current["camera_stream_url"]): str,
        }
        for key, low, high in (
            ("bed_cooled_c", 20, 70),
            ("pause_alert_minutes", 1, 120),
            ("offline_alert_minutes", 1, 30),
            ("bed_cleaning_hours", 0, 10000),
            ("rail_lubrication_hours", 0, 10000),
            ("nozzle_inspection_hours", 0, 10000),
        ):
            schema[vol.Required(key, default=current[key])] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=low, max=high, step=1, mode=selector.NumberSelectorMode.BOX
                )
            )
        for group in CONTROL_GROUPS:
            schema[vol.Required(group, default=current[group])] = bool
        for tool in range(1, 5):
            schema[vol.Required(f"tool_{tool}_slot", default=str(current[f"tool_{tool}_slot"]))] = (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[{"value": "0", "label": "Unassigned"}]
                        + [{"value": str(slot), "label": f"Slot {slot}"} for slot in range(1, 5)]
                    )
                )
            )
            schema[vol.Optional(f"tool_{tool}_note", default=current[f"tool_{tool}_note"])] = str
        path = self.hass.data.get(DOMAIN, {}).get("setup_panel_path", "creator5-setup")
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={"setup_url": f"/{path}"},
        )
