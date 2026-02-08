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
    CONF_ENABLE_AUTO_DISCHARGE,
    CONF_CHARGE_BUTTON,
    CONF_CHARGE_POWER_ENTITY,
    CONF_CHARGE_DURATION,
    CONF_CHARGE_CUTOFF_SOC,
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
    SERVICE_START_CHARGE,
    SERVICE_STOP_CHARGE,
)
from .coordinator import ExportMonitorCoordinator
from .error_handler import get_safe_sensor_value, safe_service_call

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

    async def _send_critical_notification(title: str, message: str, notification_id: str) -> None:
        """Send a persistent notification for critical errors."""
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"⚠️ Export Monitor: {title}",
                "message": message,
                "notification_id": f"export_monitor_{notification_id}",
            },
        )

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

        # Get current SOC with validation
        current_soc = get_safe_sensor_value(
            hass, current_soc_entity, "soc", default=None
        )
        if current_soc is None:
            _LOGGER.error(
                "Cannot start discharge: unable to read valid SOC from %s",
                current_soc_entity,
            )
            # Set error state in coordinator
            coordinator.set_error_state("soc_read_failed")
            # Send critical notification
            await _send_critical_notification(
                "SOC Sensor Failed",
                f"Unable to read valid battery SOC from {current_soc_entity}. "
                "Discharge cannot start until this is resolved. "
                "Check your battery sensor configuration.",
                "soc_read_failed",
            )
            return

        # Safety check - don't discharge if SOC too low
        if current_soc <= min_soc:
            _LOGGER.warning(
                "Cannot start discharge: SOC (%.1f%%) at or below minimum (%.1f%%)",
                current_soc,
                min_soc,
            )
            return

        # Check for stale coordinator data
        if coordinator.is_data_stale():
            _LOGGER.error(
                "Cannot start discharge: coordinator data is stale (age: %.1f seconds)",
                coordinator.get_data_age() or 0,
            )
            coordinator.set_error_state("stale_data")
            await _send_critical_notification(
                "Stale Data Detected",
                f"Coordinator data is stale (age: {coordinator.get_data_age():.1f}s). "
                "This indicates a problem with sensor updates. "
                "Discharge cannot start with outdated data to prevent export limit breaches. "
                "Check system health sensor for details.",
                "stale_data",
            )
            return

        # Get export headroom from coordinator
        if not coordinator.data:
            _LOGGER.error("Cannot start discharge: no coordinator data available")
            coordinator.set_error_state("no_data")
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
        auto_window_minutes = None
        if config_data.get(CONF_ENABLE_AUTO_DISCHARGE, False):
            auto_window_minutes = coordinator.get_auto_window_duration_minutes()

        if auto_window_minutes:
            duration_minutes = auto_window_minutes
            _LOGGER.info(
                "Using auto window duration: %.1f minutes",
                duration_minutes,
            )
        else:
            duration_hours = headroom / discharge_power_kw
            duration_minutes = duration_hours * 60
        
        if not auto_window_minutes:
            _LOGGER.info(
                "Calculated discharge duration: %.1f minutes (headroom: %.3f kWh ÷ power: %.3f kW)",
                duration_minutes,
                headroom,
                discharge_power_kw,
            )

        # Set discharge power to match target export power (in kW) with safe call
        discharge_power_entity = config_data[CONF_DISCHARGE_POWER]
        domain, service = _get_domain_and_service(discharge_power_entity, "set_value")
        
        success = await safe_service_call(
            hass,
            domain,
            service,
            {
                "entity_id": discharge_power_entity,
                "value": discharge_power_kw,
            },
            entity_id=discharge_power_entity,
            expected_value=discharge_power_kw,
        )
        
        if not success:
            _LOGGER.error("Failed to set discharge power, aborting start discharge")
            coordinator.set_error_state("discharge_power_set_failed")
            await _send_critical_notification(
                "Discharge Power Set Failed",
                f"Failed to set discharge power to {discharge_power_kw:.2f}kW on entity {discharge_power_entity}. "
                "This indicates a problem with the battery control system. "
                "Discharge has been aborted to prevent unpredictable behavior.",
                "discharge_power_failed",
            )
            return

        # Set cutoff SOC using the specific Alpha ESS helper entity
        cutoff_soc_entity = "input_number.alphaess_helper_force_discharging_cutoff_soc"
        if hass.states.get(cutoff_soc_entity):
            domain, service = _get_domain_and_service(cutoff_soc_entity, "set_value")
            success = await safe_service_call(
                hass,
                domain,
                service,
                {
                    "entity_id": cutoff_soc_entity,
                    "value": min_soc,
                },
                entity_id=cutoff_soc_entity,
                expected_value=min_soc,
            )
            if not success:
                _LOGGER.warning(
                    "Failed to set cutoff SOC, continuing anyway"
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
            success = await safe_service_call(
                hass,
                domain,
                service,
                {
                    "entity_id": duration_entity,
                    "value": duration_minutes,
                },
                entity_id=duration_entity,
                expected_value=duration_minutes,
            )
            if success:
                _LOGGER.info("Set discharge duration to %.1f minutes", duration_minutes)
            else:
                _LOGGER.warning("Failed to set discharge duration, continuing anyway")

        timer_entity = "timer.alphaess_helper_force_discharging_timer"
        if hass.states.get(timer_entity):
            total_seconds = max(int(round(duration_minutes * 60)), 1)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            await hass.services.async_call(
                "timer",
                "start",
                {
                    "entity_id": timer_entity,
                    "duration": duration_str,
                },
                blocking=True,
            )

        # Enable discharge button
        discharge_button_entity = config_data[CONF_DISCHARGE_BUTTON]
        domain, service = _get_domain_and_service(discharge_button_entity, "turn_on")
        success = await safe_service_call(
            hass,
            domain,
            service,
            {"entity_id": discharge_button_entity},
            entity_id=discharge_button_entity,
            expected_value="on",
        )
        
        if not success:
            _LOGGER.error("Failed to enable discharge button, discharge may not start")
            coordinator.set_error_state("discharge_start_failed")
            await _send_critical_notification(
                "Discharge Start Failed",
                f"Failed to enable discharge on entity {discharge_button_entity}. "
                "Battery discharge has not started. "
                "Check battery control system and entity configuration.",
                "discharge_start_failed",
            )
            return

        # Get current grid export for tracking with validation
        grid_feed_entity = config_data[CONF_GRID_FEED_TODAY]
        current_grid_export = get_safe_sensor_value(
            hass, grid_feed_entity, "energy", default=0.0
        )
        
        # Calculate target energy (headroom from coordinator data)
        target_energy = coordinator.data.get(ATTR_EXPORT_HEADROOM, 0.0) if coordinator.data else 0.0
        
        coordinator.set_discharge_active(True, current_grid_export, target_energy)
        coordinator.clear_error_state()
        
        # Clear any previous error notifications (best-effort cleanup)
        try:
            await hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {
                    "notification_id": "export_monitor_soc_read_failed",
                },
            )
            await hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {
                    "notification_id": "export_monitor_stale_data",
                },
            )
            await hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {
                    "notification_id": "export_monitor_discharge_power_failed",
                },
            )
            await hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {
                    "notification_id": "export_monitor_discharge_start_failed",
                },
            )
        except Exception as err:
            # Non-critical; log and continue
            _LOGGER.warning(
                "Failed to dismiss error notifications: %s",
                err,
            )

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

        # Disable discharge button with safe call
        domain, service = _get_domain_and_service(discharge_button_entity, "turn_off")
        success = await safe_service_call(
            hass,
            domain,
            service,
            {"entity_id": discharge_button_entity},
            entity_id=discharge_button_entity,
            expected_value="off",
        )
        
        if not success:
            _LOGGER.error("Failed to disable discharge button, discharge may still be active")
            coordinator.set_error_state("discharge_stop_failed")
            await _send_critical_notification(
                "Discharge Stop Failed",
                f"Failed to disable discharge on entity {discharge_button_entity}. "
                "Battery may still be discharging! "
                "Check battery immediately and stop discharge manually if needed.",
                "discharge_stop_failed",
            )
            return

        coordinator.set_discharge_active(False)
        coordinator.clear_error_state()
        
        # Clear stop failure notification if it exists (best-effort cleanup)
        try:
            await hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {
                    "notification_id": "export_monitor_discharge_stop_failed",
                },
            )
        except Exception as err:
            # Non-critical; log and continue
            _LOGGER.warning(
                "Failed to dismiss discharge stop failure notification: %s",
                err,
            )

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
    
    async def handle_start_charge(call: ServiceCall) -> None:
        """Handle start charge service call."""
        config_data = {**coordinator.entry.data, **coordinator.entry.options}
        
        # Get next charge session from coordinator
        if not coordinator.data or "next_charge_session" not in coordinator.data:
            _LOGGER.error("Cannot start charge: no charge session data available")
            return
        
        charge_session = coordinator.data.get("next_charge_session", [])
        if not charge_session:
            _LOGGER.info("No charge session planned, nothing to do")
            return
        
        # Calculate total energy needed from session
        total_energy_kwh = sum(p.get("energy_kwh", 0) for p in charge_session)
        
        # Get charge control entities
        charge_button_entity = config_data.get(CONF_CHARGE_BUTTON)
        charge_power_entity = config_data.get(CONF_CHARGE_POWER_ENTITY)
        charge_duration_entity = config_data.get(CONF_CHARGE_DURATION)
        charge_cutoff_soc_entity = config_data.get(CONF_CHARGE_CUTOFF_SOC)
        
        if not all([charge_button_entity, charge_power_entity, charge_duration_entity, charge_cutoff_soc_entity]):
            _LOGGER.error("Charge control entities not configured")
            return
        
        # Calculate total charge duration across all windows in chronological order
        from datetime import datetime
        
        # Sort windows chronologically by start time
        sorted_windows = sorted(
            charge_session,
            key=lambda w: datetime.fromisoformat(w.get("period_start", "9999-12-31T23:59:59+00:00"))
        )
        
        total_duration_hours = 0.0
        duration_minutes = 30  # Default fallback
        
        try:
            for window in sorted_windows:
                window_start = datetime.fromisoformat(window.get("period_start", ""))
                window_end = datetime.fromisoformat(window.get("period_end", ""))
                duration = (window_end - window_start).total_seconds() / 3600
                if duration > 0:
                    total_duration_hours += duration
            
            if total_duration_hours > 0:
                duration_minutes = total_duration_hours * 60
        except (ValueError, TypeError) as err:
            _LOGGER.error("Error calculating charge duration: %s", err)
            total_duration_hours = 0.5  # Default to 30 minutes / 0.5 hours
            duration_minutes = 30
        
        # Calculate charge power from total energy over total duration
        if total_duration_hours > 0:
            charge_power_kw = total_energy_kwh / total_duration_hours
        else:
            charge_power_kw = 3.68  # Default charge power
        
        _LOGGER.info(
            "Starting charge: %.2f kW for %.1f min (target: 100%% SOC, %.3f kWh total)",
            charge_power_kw,
            duration_minutes,
            total_energy_kwh,
        )
        
        # Set charge power
        domain, service = _get_domain_and_service(charge_power_entity, "set_value")
        await hass.services.async_call(
            domain,
            service,
            {
                "entity_id": charge_power_entity,
                "value": charge_power_kw,
            },
            blocking=True,
        )
        
        # Set charge duration
        domain, service = _get_domain_and_service(charge_duration_entity, "set_value")
        await hass.services.async_call(
            domain,
            service,
            {
                "entity_id": charge_duration_entity,
                "value": duration_minutes,
            },
            blocking=True,
        )
        
        # Set cutoff SOC to 100% (always charge to full)
        domain, service = _get_domain_and_service(charge_cutoff_soc_entity, "set_value")
        await hass.services.async_call(
            domain,
            service,
            {
                "entity_id": charge_cutoff_soc_entity,
                "value": 100,
            },
            blocking=True,
        )
        
        # Enable charge button
        domain, service = _get_domain_and_service(charge_button_entity, "turn_on")
        await hass.services.async_call(
            domain,
            service,
            {"entity_id": charge_button_entity},
            blocking=True,
        )
        
        coordinator.set_charge_active(True)
        
        _LOGGER.info(
            "Charge started: %.2f kW for %.1f min (target: 100%% SOC)",
            charge_power_kw,
            duration_minutes,
        )
    
    async def handle_stop_charge(call: ServiceCall) -> None:
        """Handle stop charge service call."""
        config_data = {**coordinator.entry.data, **coordinator.entry.options}
        charge_button_entity = config_data.get(CONF_CHARGE_BUTTON)
        
        if not charge_button_entity:
            _LOGGER.error("Charge button entity not configured")
            return
        
        # Disable charge button
        domain, service = _get_domain_and_service(charge_button_entity, "turn_off")
        await hass.services.async_call(
            domain,
            service,
            {"entity_id": charge_button_entity},
            blocking=True,
        )
        
        coordinator.set_charge_active(False)
        
        _LOGGER.info("Stopped charge")
    
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
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_CHARGE,
        handle_start_charge,
        schema=vol.Schema({}),
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_CHARGE,
        handle_stop_charge,
        schema=vol.Schema({}),
    )

    _LOGGER.info("Services registered")
