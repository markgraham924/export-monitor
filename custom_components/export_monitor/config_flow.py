"""Config flow for Energy Export Monitor integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_CURRENT_SOC,
    CONF_DISCHARGE_BUTTON,
    CONF_DISCHARGE_CUTOFF_SOC,
    CONF_DISCHARGE_POWER,
    CONF_CI_FORECAST_SENSOR,
    CONF_ENABLE_CI_PLANNING,
    CONF_GRID_FEED_TODAY,
    CONF_MIN_SOC,
    CONF_OBSERVE_RESERVE_SOC,
    CONF_PV_ENERGY_TODAY,
    CONF_RESERVE_SOC_SENSOR,
    CONF_SAFETY_MARGIN,
    CONF_SOLCAST_FORECAST_SO_FAR,
    CONF_SOLCAST_TOMORROW,
    CONF_SOLCAST_TOTAL_TODAY,
    CONF_TARGET_EXPORT,
    DEFAULT_ENABLE_CI_PLANNING,
    DEFAULT_MIN_SOC,
    DEFAULT_OBSERVE_RESERVE_SOC,
    DEFAULT_SAFETY_MARGIN,
    DEFAULT_TARGET_EXPORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _validate_entity(hass: HomeAssistant, entity_id: str) -> bool:
    """Validate that entity exists (availability check is lenient)."""
    try:
        state = hass.states.get(entity_id)
        # Just check if entity exists; don't require it to be available
        # (startup dependencies may not be loaded yet)
        if state is None:
            _LOGGER.debug("Entity %s not found", entity_id)
            return False
        return True
    except Exception as err:
        _LOGGER.debug("Error validating entity %s: %s", entity_id, err)
        return False


class ExportMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Energy Export Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""
        return await self._async_handle_step(user_input)

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle YAML import."""
        return await self._async_handle_step(user_input)

    async def _async_handle_step(
        self, user_input: dict[str, Any] | None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate all required entities
            for key in [
                CONF_DISCHARGE_BUTTON,
                CONF_DISCHARGE_POWER,
                CONF_DISCHARGE_CUTOFF_SOC,
                CONF_CURRENT_SOC,
                CONF_PV_ENERGY_TODAY,
                CONF_GRID_FEED_TODAY,
                CONF_SOLCAST_TOTAL_TODAY,
            ]:
                if not _validate_entity(self.hass, user_input[key]):
                    errors[key] = "entity_not_found"

            if not errors:
                return self.async_create_entry(
                    title="Energy Export Monitor",
                    data=user_input,
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_DISCHARGE_BUTTON): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["input_boolean", "switch"],
                    )
                ),
                vol.Required(CONF_DISCHARGE_POWER): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["number", "input_number"],
                    )
                ),
                vol.Required(CONF_DISCHARGE_CUTOFF_SOC): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["number", "input_number"],
                    )
                ),
                vol.Required(CONF_CURRENT_SOC): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="battery",
                    )
                ),
                vol.Required(CONF_PV_ENERGY_TODAY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="energy",
                    )
                ),
                vol.Required(CONF_GRID_FEED_TODAY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="energy",
                    )
                ),
                vol.Required(CONF_SOLCAST_TOTAL_TODAY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                    )
                ),
                vol.Optional(CONF_SOLCAST_FORECAST_SO_FAR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                    )
                ),
                vol.Optional(CONF_SOLCAST_TOMORROW): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                    )
                ),
                vol.Optional(
                    CONF_TARGET_EXPORT, default=DEFAULT_TARGET_EXPORT
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=10000,
                        step=100,
                        unit_of_measurement="W",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_MIN_SOC, default=DEFAULT_MIN_SOC
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=1,
                        unit_of_measurement="%",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_SAFETY_MARGIN, default=DEFAULT_SAFETY_MARGIN
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=20,
                        step=0.1,
                        unit_of_measurement="kWh",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_RESERVE_SOC_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                    )
                ),
                vol.Optional(
                    CONF_OBSERVE_RESERVE_SOC, default=DEFAULT_OBSERVE_RESERVE_SOC
                ): selector.BooleanSelector(),
                vol.Optional(CONF_CI_FORECAST_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                    )
                ),
                vol.Optional(
                    CONF_ENABLE_CI_PLANNING, default=DEFAULT_ENABLE_CI_PLANNING
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle reconfiguration of entities."""
        errors: dict[str, str] = {}

        # Get the config entry being reconfigured
        try:
            entry = self.hass.config_entries.async_get_entry(self.context.get("entry_id"))
            if entry is None:
                return self.async_abort(reason="entry_not_found")
        except (KeyError, AttributeError) as err:
            _LOGGER.error("Error getting config entry for reconfiguration: %s", err)
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            # Validate all required entities
            for key in [
                CONF_DISCHARGE_BUTTON,
                CONF_DISCHARGE_POWER,
                CONF_DISCHARGE_CUTOFF_SOC,
                CONF_CURRENT_SOC,
                CONF_PV_ENERGY_TODAY,
                CONF_GRID_FEED_TODAY,
                CONF_SOLCAST_TOTAL_TODAY,
            ]:
                if not _validate_entity(self.hass, user_input[key]):
                    errors[key] = "entity_not_found"

            if not errors:
                # Update the config entry with new data
                self.hass.config_entries.async_update_entry(
                    entry,
                    data=user_input,
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        # Get current values from config entry
        current_data = entry.data

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_DISCHARGE_BUTTON,
                    default=current_data.get(CONF_DISCHARGE_BUTTON),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["input_boolean", "switch"],
                    )
                ),
                vol.Required(
                    CONF_DISCHARGE_POWER,
                    default=current_data.get(CONF_DISCHARGE_POWER),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["number", "input_number"],
                    )
                ),
                vol.Required(
                    CONF_DISCHARGE_CUTOFF_SOC,
                    default=current_data.get(CONF_DISCHARGE_CUTOFF_SOC),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["number", "input_number"],
                    )
                ),
                vol.Required(
                    CONF_CURRENT_SOC,
                    default=current_data.get(CONF_CURRENT_SOC),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="battery",
                    )
                ),
                vol.Required(
                    CONF_PV_ENERGY_TODAY,
                    default=current_data.get(CONF_PV_ENERGY_TODAY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="energy",
                    )
                ),
                vol.Required(
                    CONF_GRID_FEED_TODAY,
                    default=current_data.get(CONF_GRID_FEED_TODAY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="energy",
                    )
                ),
                vol.Required(
                    CONF_SOLCAST_TOTAL_TODAY,
                    default=current_data.get(CONF_SOLCAST_TOTAL_TODAY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="energy",
                    )
                ),
                vol.Optional(
                    CONF_SOLCAST_FORECAST_SO_FAR,
                    default=current_data.get(CONF_SOLCAST_FORECAST_SO_FAR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                    )
                ),
                vol.Optional(
                    CONF_SOLCAST_TOMORROW,
                    default=current_data.get(CONF_SOLCAST_TOMORROW),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                    )
                ),
                vol.Optional(
                    CONF_TARGET_EXPORT,
                    default=current_data.get(CONF_TARGET_EXPORT, DEFAULT_TARGET_EXPORT),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=10000,
                        step=100,
                        unit_of_measurement="W",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_MIN_SOC,
                    default=current_data.get(CONF_MIN_SOC, DEFAULT_MIN_SOC),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=1,
                        unit_of_measurement="%",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_SAFETY_MARGIN,
                    default=current_data.get(CONF_SAFETY_MARGIN, DEFAULT_SAFETY_MARGIN),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=20,
                        step=0.1,
                        unit_of_measurement="kWh",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_RESERVE_SOC_SENSOR,
                    default=current_data.get(CONF_RESERVE_SOC_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                    )
                ),
                vol.Optional(
                    CONF_OBSERVE_RESERVE_SOC,
                    default=current_data.get(CONF_OBSERVE_RESERVE_SOC, DEFAULT_OBSERVE_RESERVE_SOC),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_CI_FORECAST_SENSOR,
                    default=current_data.get(CONF_CI_FORECAST_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                    )
                ),
                vol.Optional(
                    CONF_ENABLE_CI_PLANNING,
                    default=current_data.get(CONF_ENABLE_CI_PLANNING, DEFAULT_ENABLE_CI_PLANNING),
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for the integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current values
        current_data = {**self.config_entry.data, **self.config_entry.options}

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TARGET_EXPORT,
                    default=current_data.get(CONF_TARGET_EXPORT, DEFAULT_TARGET_EXPORT),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=10000,
                        step=100,
                        unit_of_measurement="W",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_MIN_SOC,
                    default=current_data.get(CONF_MIN_SOC, DEFAULT_MIN_SOC),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=1,
                        unit_of_measurement="%",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_SAFETY_MARGIN,
                    default=current_data.get(CONF_SAFETY_MARGIN, DEFAULT_SAFETY_MARGIN),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=20,
                        step=0.1,
                        unit_of_measurement="kWh",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_RESERVE_SOC_SENSOR,
                    default=current_data.get(CONF_RESERVE_SOC_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                    )
                ),
                vol.Optional(
                    CONF_OBSERVE_RESERVE_SOC,
                    default=current_data.get(CONF_OBSERVE_RESERVE_SOC, DEFAULT_OBSERVE_RESERVE_SOC),
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )
