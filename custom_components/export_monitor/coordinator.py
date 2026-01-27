"""Data update coordinator for Energy Export Monitor."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_CURRENT_PV,
    ATTR_CURRENT_THRESHOLD,
    ATTR_DISCHARGE_NEEDED,
    ATTR_FORECAST_PV,
    ATTR_GRID_EXPORT,
    ATTR_LAST_CALCULATION,
    ATTR_SAFE_EXPORT_LIMIT,
    CONF_CURRENT_PV,
    CONF_CURRENT_SOC,
    CONF_GRID_POWER,
    CONF_MIN_SOC,
    CONF_SAFETY_MARGIN,
    CONF_SOLCAST_REMAINING,
    CONF_TARGET_EXPORT,
    DEFAULT_MIN_SOC,
    DEFAULT_SAFETY_MARGIN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TARGET_EXPORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ExportMonitorCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self._discharge_active = False

    def _get_sensor_value(self, entity_id: str) -> float | None:
        """Get sensor value as float."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
            _LOGGER.warning("Sensor %s is unavailable", entity_id)
            return None

        try:
            return float(state.state)
        except (ValueError, TypeError) as err:
            _LOGGER.error("Cannot convert %s state to float: %s", entity_id, err)
            return None

    def _calculate_safe_export_limit(
        self,
        current_pv: float,
        forecast_pv: float,
        safety_margin: float,
    ) -> float:
        """
        Calculate safe export limit.
        
        Returns the maximum allowed grid export in watts, calculated as:
        max(current_pv, forecast_pv) + safety_margin
        """
        base_limit = max(current_pv, forecast_pv)
        safe_limit = base_limit + safety_margin
        _LOGGER.debug(
            "Safe export limit: %.0f W (PV: %.0f W, Forecast: %.0f W, Margin: %.0f W)",
            safe_limit,
            current_pv,
            forecast_pv,
            safety_margin,
        )
        return safe_limit

    def _calculate_discharge_needed(
        self,
        grid_power: float,
        safe_export_limit: float,
        current_soc: float,
        min_soc: float,
    ) -> float:
        """
        Calculate discharge power needed.
        
        Returns the amount of discharge power (in watts) needed to stay within
        the safe export limit. Returns 0 if no discharge needed or battery too low.
        
        Note: grid_power is negative when exporting to grid.
        """
        # Check if battery has enough charge
        if current_soc <= min_soc:
            _LOGGER.debug("Battery SOC (%.1f%%) at or below minimum (%.1f%%)", current_soc, min_soc)
            return 0

        # Calculate current grid export (make positive for easier logic)
        current_export = abs(grid_power) if grid_power < 0 else 0

        # Check if we're exceeding the safe limit
        if current_export <= safe_export_limit:
            _LOGGER.debug(
                "Current export (%.0f W) within safe limit (%.0f W)",
                current_export,
                safe_export_limit,
            )
            return 0

        # Calculate how much we need to discharge to stay within limit
        discharge_needed = current_export - safe_export_limit
        _LOGGER.info(
            "Discharge needed: %.0f W (Export: %.0f W, Limit: %.0f W)",
            discharge_needed,
            current_export,
            safe_export_limit,
        )
        return discharge_needed

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors and calculate discharge requirements."""
        config_data = {**self.entry.data, **self.entry.options}

        # Get sensor values
        current_soc = self._get_sensor_value(config_data[CONF_CURRENT_SOC])
        grid_power = self._get_sensor_value(config_data[CONF_GRID_POWER])
        current_pv = self._get_sensor_value(config_data[CONF_CURRENT_PV])
        solcast_remaining = self._get_sensor_value(config_data[CONF_SOLCAST_REMAINING])

        # Check for missing values
        if any(v is None for v in [current_soc, grid_power, current_pv, solcast_remaining]):
            raise UpdateFailed("One or more sensors unavailable")

        # Get configuration values
        target_export = config_data.get(CONF_TARGET_EXPORT, DEFAULT_TARGET_EXPORT)
        min_soc = config_data.get(CONF_MIN_SOC, DEFAULT_MIN_SOC)
        safety_margin = config_data.get(CONF_SAFETY_MARGIN, DEFAULT_SAFETY_MARGIN)

        # Convert Solcast remaining forecast from kWh to W (assuming over 1 hour)
        forecast_pv_watts = solcast_remaining * 1000

        # Calculate safe export limit
        safe_export_limit = self._calculate_safe_export_limit(
            current_pv,
            forecast_pv_watts,
            safety_margin,
        )

        # Calculate discharge needed
        discharge_needed = self._calculate_discharge_needed(
            grid_power,
            safe_export_limit,
            current_soc,
            min_soc,
        )

        # Calculate current grid export (positive value)
        current_export = abs(grid_power) if grid_power < 0 else 0

        return {
            ATTR_CURRENT_THRESHOLD: safe_export_limit,
            ATTR_GRID_EXPORT: current_export,
            ATTR_DISCHARGE_NEEDED: discharge_needed,
            ATTR_SAFE_EXPORT_LIMIT: safe_export_limit,
            ATTR_CURRENT_PV: current_pv,
            ATTR_FORECAST_PV: forecast_pv_watts,
            ATTR_LAST_CALCULATION: self.hass.states.get("sensor.date_time_iso").state
            if self.hass.states.get("sensor.date_time_iso")
            else None,
            "current_soc": current_soc,
            "min_soc": min_soc,
            "target_export": target_export,
        }

    @property
    def discharge_active(self) -> bool:
        """Return if discharge is currently active."""
        return self._discharge_active

    def set_discharge_active(self, active: bool) -> None:
        """Set discharge active state."""
        self._discharge_active = active
        _LOGGER.info("Discharge active state set to: %s", active)
