"""The Energy Export Monitor integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CURRENT_SOC,
    CONF_DISCHARGE_BUTTON,
    CONF_DISCHARGE_CUTOFF_SOC,
    CONF_DISCHARGE_POWER,
    CONF_MIN_SOC,
    DEFAULT_MIN_SOC,
    DOMAIN,
    SERVICE_CALCULATE_DISCHARGE,
    SERVICE_START_DISCHARGE,
    SERVICE_STOP_DISCHARGE,
)
from .coordinator import ExportMonitorCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Energy Export Monitor from a config entry."""
    coordinator = ExportMonitorCoordinator(hass, entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await async_setup_services(hass, coordinator)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_setup_services(
    hass: HomeAssistant, coordinator: ExportMonitorCoordinator
) -> None:
    """Set up services for the integration."""

    async def handle_start_discharge(call: ServiceCall) -> None:
        """Handle start discharge service call."""
        power = call.data.get("power")
        cutoff_soc = call.data.get("cutoff_soc")

        config_data = {**coordinator.entry.data, **coordinator.entry.options}
        current_soc_entity = config_data[CONF_CURRENT_SOC]
        min_soc = config_data.get(CONF_MIN_SOC, DEFAULT_MIN_SOC)

        # Get current SOC
        soc_state = hass.states.get(current_soc_entity)
        if soc_state is None:
            _LOGGER.error("Cannot read current SOC from %s", current_soc_entity)
            return

        try:
            current_soc = float(soc_state.state)
        except (ValueError, TypeError):
            _LOGGER.error("Invalid SOC value: %s", soc_state.state)
            return

        # Safety check - don't discharge if SOC too low
        if current_soc <= min_soc:
            _LOGGER.warning(
                "Cannot start discharge: SOC (%.1f%%) at or below minimum (%.1f%%)",
                current_soc,
                min_soc,
            )
            return

        # Set discharge power
        discharge_power_entity = config_data[CONF_DISCHARGE_POWER]
        await hass.services.async_call(
            "number",
            "set_value",
            {
                "entity_id": discharge_power_entity,
                "value": power / 1000,  # Convert W to kW
            },
            blocking=True,
        )

        # Set cutoff SOC
        if cutoff_soc is not None:
            discharge_cutoff_entity = config_data[CONF_DISCHARGE_CUTOFF_SOC]
            await hass.services.async_call(
                "number",
                "set_value",
                {
                    "entity_id": discharge_cutoff_entity,
                    "value": cutoff_soc,
                },
                blocking=True,
            )

        # Enable discharge button
        discharge_button_entity = config_data[CONF_DISCHARGE_BUTTON]
        await hass.services.async_call(
            "input_boolean",
            "turn_on",
            {"entity_id": discharge_button_entity},
            blocking=True,
        )

        coordinator.set_discharge_active(True)

        _LOGGER.info(
            "Started discharge: %.0f W until %.0f%% SOC",
            power,
            cutoff_soc if cutoff_soc else min_soc,
        )

    async def handle_stop_discharge(call: ServiceCall) -> None:
        """Handle stop discharge service call."""
        config_data = {**coordinator.entry.data, **coordinator.entry.options}
        discharge_button_entity = config_data[CONF_DISCHARGE_BUTTON]

        # Disable discharge button
        await hass.services.async_call(
            "input_boolean",
            "turn_off",
            {"entity_id": discharge_button_entity},
            blocking=True,
        )

        coordinator.set_discharge_active(False)

        _LOGGER.info("Stopped discharge")

    async def handle_calculate_discharge(call: ServiceCall) -> None:
        """Handle calculate discharge service call."""
        await coordinator.async_request_refresh()
        
        if coordinator.data:
            discharge_needed = coordinator.data.get("discharge_needed", 0)
            safe_limit = coordinator.data.get("safe_export_limit", 0)
            
            _LOGGER.info(
                "Discharge calculation: %.0f W needed (safe limit: %.0f W)",
                discharge_needed,
                safe_limit,
            )

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_DISCHARGE,
        handle_start_discharge,
        schema=vol.Schema(
            {
                vol.Required("power"): cv.positive_int,
                vol.Optional("cutoff_soc"): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=100)
                ),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_DISCHARGE,
        handle_stop_discharge,
        schema=vol.Schema({}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CALCULATE_DISCHARGE,
        handle_calculate_discharge,
        schema=vol.Schema({}),
    )

    _LOGGER.info("Services registered")
