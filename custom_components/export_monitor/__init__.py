"""The Energy Export Monitor integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_EXPORT_HEADROOM,
    CONF_CURRENT_SOC,
    CONF_DISCHARGE_BUTTON,
    CONF_DISCHARGE_CUTOFF_SOC,
    CONF_DISCHARGE_POWER,
    CONF_GRID_FEED_TODAY,
    CONF_MIN_SOC,
    CONF_PV_ENERGY_TODAY,
    CONF_SAFETY_MARGIN,
    CONF_SOLCAST_FORECAST_SO_FAR,
    CONF_SOLCAST_TOTAL_TODAY,
    CONF_TARGET_EXPORT,
    DEFAULT_MIN_SOC,
    DEFAULT_SAFETY_MARGIN,
    DEFAULT_TARGET_EXPORT,
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
    Platform.SWITCH,
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


# YAML configuration support (import flow)
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_DISCHARGE_BUTTON): cv.entity_id,
                        vol.Required(CONF_DISCHARGE_POWER): cv.entity_id,
                        vol.Required(CONF_DISCHARGE_CUTOFF_SOC): cv.entity_id,
                        vol.Required(CONF_CURRENT_SOC): cv.entity_id,
                        vol.Required(CONF_PV_ENERGY_TODAY): cv.entity_id,
                        vol.Required(CONF_GRID_FEED_TODAY): cv.entity_id,
                        vol.Required(CONF_SOLCAST_TOTAL_TODAY): cv.entity_id,
                        vol.Optional(CONF_SOLCAST_FORECAST_SO_FAR): cv.entity_id,
                        vol.Optional(CONF_TARGET_EXPORT, default=DEFAULT_TARGET_EXPORT): cv.positive_int,
                        vol.Optional(CONF_MIN_SOC, default=DEFAULT_MIN_SOC): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=100)
                        ),
                        vol.Optional(CONF_SAFETY_MARGIN, default=DEFAULT_SAFETY_MARGIN): vol.Coerce(float),
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration via YAML by importing into config entries."""
    if DOMAIN not in config:
        return True

    for entry_conf in config[DOMAIN]:
        # Prevent duplicate imports
        existing = hass.config_entries.async_entries(DOMAIN)
        if any(e.data.get(CONF_DISCHARGE_BUTTON) == entry_conf[CONF_DISCHARGE_BUTTON] for e in existing):
            continue

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=entry_conf,
            )
        )

    return True


async def async_setup_services(
    hass: HomeAssistant, coordinator: ExportMonitorCoordinator
) -> None:
    """Set up services for the integration."""

    def _get_domain_and_service(entity_id: str, service_type: str) -> tuple[str, str]:
        """Get the correct domain and service for an entity."""
        domain = entity_id.split(".")[0]
        if service_type == "set_value":
            return domain, "set_value"
        elif service_type == "turn_on":
            return domain, "turn_on"
        elif service_type == "turn_off":
            return domain, "turn_off"
        return domain, service_type

    async def handle_start_discharge(call: ServiceCall) -> None:
        """Handle start discharge service call."""
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

        # Get export headroom from coordinator
        if not coordinator.data:
            _LOGGER.error("Cannot start discharge: no coordinator data available")
            return
            
        headroom = coordinator.data.get(ATTR_EXPORT_HEADROOM, 0)
        if headroom <= 0:
            _LOGGER.error(
                "Cannot start discharge: no export headroom available (%.3f kWh)",
                headroom
            )
            return

        # Use target export power as the fixed discharge power
        target_export_w = config_data.get(CONF_TARGET_EXPORT, DEFAULT_TARGET_EXPORT)
        if target_export_w <= 0:
            _LOGGER.error("Cannot start discharge: target export power must be > 0 W")
            return

        discharge_power_kw = target_export_w / 1000

        # Calculate duration: time (hours) = energy (kWh) / power (kW)
        duration_hours = headroom / discharge_power_kw
        duration_minutes = duration_hours * 60
        
        _LOGGER.info(
            "Calculated discharge duration: %.1f minutes (headroom: %.3f kWh ÷ power: %.3f kW)",
            duration_minutes,
            headroom,
            discharge_power_kw,
        )

        # Set discharge power to match target export power (in kW)
        discharge_power_entity = config_data[CONF_DISCHARGE_POWER]
        domain, service = _get_domain_and_service(discharge_power_entity, "set_value")
        await hass.services.async_call(
            domain,
            service,
            {
                "entity_id": discharge_power_entity,
                "value": discharge_power_kw,
            },
            blocking=True,
        )

        # Set cutoff SOC using the specific Alpha ESS helper entity
        cutoff_soc_entity = "input_number.alphaess_helper_force_discharging_cutoff_soc"
        if hass.states.get(cutoff_soc_entity):
            domain, service = _get_domain_and_service(cutoff_soc_entity, "set_value")
            await hass.services.async_call(
                domain,
                service,
                {
                    "entity_id": cutoff_soc_entity,
                    "value": min_soc,
                },
                blocking=True,
            )
        else:
            _LOGGER.warning("Cutoff SOC entity %s not found, skipping", cutoff_soc_entity)

        # Set discharge duration (if entity exists)
        # Look for duration entity - common patterns
        duration_entity = None
        for pattern in [
            "input_number.alphaess_helper_force_discharging_duration",
            "number.alphaess_template_force_discharging_duration",
        ]:
            if hass.states.get(pattern):
                duration_entity = pattern
                break

        if duration_entity:
            domain, service = _get_domain_and_service(duration_entity, "set_value")
            await hass.services.async_call(
                domain,
                service,
                {
                    "entity_id": duration_entity,
                    "value": duration_minutes,
                },
                blocking=True,
            )
            _LOGGER.info("Set discharge duration to %.1f minutes", duration_minutes)

        # Enable discharge button
        discharge_button_entity = config_data[CONF_DISCHARGE_BUTTON]
        domain, service = _get_domain_and_service(discharge_button_entity, "turn_on")
        await hass.services.async_call(
            domain,
            service,
            {"entity_id": discharge_button_entity},
            blocking=True,
        )

        # Get current grid export for tracking
        grid_feed_entity = config_data[CONF_GRID_FEED_TODAY]
        grid_feed_state = hass.states.get(grid_feed_entity)
        current_grid_export = float(grid_feed_state.state) if grid_feed_state else 0.0
        
        # Calculate target energy (headroom from coordinator data)
        target_energy = coordinator.data.get(ATTR_EXPORT_HEADROOM, 0.0) if coordinator.data else 0.0
        
        coordinator.set_discharge_active(True, current_grid_export, target_energy)

        _LOGGER.info(
            "Started discharge: %.3f kW for %.1f min (cutoff SOC: %.0f%%, target: %.3f kWh)",
            discharge_power_kw,
            duration_minutes,
            min_soc,
            target_energy,
        )

    async def handle_stop_discharge(call: ServiceCall) -> None:
        """Handle stop discharge service call."""
        config_data = {**coordinator.entry.data, **coordinator.entry.options}
        discharge_button_entity = config_data[CONF_DISCHARGE_BUTTON]

        # Disable discharge button
        domain, service = _get_domain_and_service(discharge_button_entity, "turn_off")
        await hass.services.async_call(
            domain,
            service,
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
        schema=vol.Schema({}),  # No parameters - duration calculated automatically
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
