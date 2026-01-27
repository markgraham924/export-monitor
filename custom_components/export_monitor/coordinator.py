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
    ATTR_DISCHARGE_NEEDED,
    ATTR_EXPORT_ALLOWED,
    ATTR_EXPORT_HEADROOM,
    ATTR_EXPORTED_TODAY,
    ATTR_FORECAST_PV,
    ATTR_LAST_CALCULATION,
    CONF_CURRENT_SOC,
    CONF_GRID_FEED_TODAY,
    CONF_MIN_SOC,
    CONF_PV_ENERGY_TODAY,
    CONF_SAFETY_MARGIN,
    CONF_SOLCAST_FORECAST_SO_FAR,
    CONF_SOLCAST_TOTAL_TODAY,
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

    def _calculate_export_headroom(
        self,
        pv_energy_today: float,
        solcast_total_today: float,
        grid_feed_today: float,
        safety_margin_kwh: float,
    ) -> tuple[float, float]:
        """Calculate export allowance and remaining headroom (kWh)."""
        export_cap = max(pv_energy_today, solcast_total_today) + safety_margin_kwh
        headroom = export_cap - grid_feed_today
        _LOGGER.debug(
            "Export headroom: %.3f kWh (cap: %.3f kWh, exported: %.3f kWh)",
            headroom,
            export_cap,
            grid_feed_today,
        )
        return export_cap, headroom

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors and calculate discharge requirements."""
        config_data = {**self.entry.data, **self.entry.options}

        # Get sensor values (kWh)
        current_soc = self._get_sensor_value(config_data[CONF_CURRENT_SOC])
        pv_energy_today = self._get_sensor_value(config_data[CONF_PV_ENERGY_TODAY])
        grid_feed_today = self._get_sensor_value(config_data[CONF_GRID_FEED_TODAY])
        solcast_total_today = self._get_sensor_value(config_data[CONF_SOLCAST_TOTAL_TODAY])
        solcast_forecast_so_far = config_data.get(CONF_SOLCAST_FORECAST_SO_FAR)
        solcast_forecast_so_far_value = (
            self._get_sensor_value(solcast_forecast_so_far)
            if solcast_forecast_so_far
            else None
        )

        # Check for missing values
        required_values = [
            current_soc,
            pv_energy_today,
            grid_feed_today,
            solcast_total_today,
        ]
        if any(v is None for v in required_values):
            raise UpdateFailed("One or more sensors unavailable")

        # Get configuration values
        target_export = config_data.get(CONF_TARGET_EXPORT, DEFAULT_TARGET_EXPORT)
        min_soc = config_data.get(CONF_MIN_SOC, DEFAULT_MIN_SOC)
        safety_margin = config_data.get(CONF_SAFETY_MARGIN, DEFAULT_SAFETY_MARGIN)

        # Calculate export cap and headroom (kWh)
        export_cap_kwh, headroom_kwh = self._calculate_export_headroom(
            pv_energy_today,
            solcast_total_today,
            grid_feed_today,
            safety_margin,
        )

        # Recommended discharge power assumes 1 hour window
        recommended_discharge_w = 0.0
        if current_soc > min_soc and headroom_kwh > 0:
            recommended_discharge_w = headroom_kwh * 1000

        return {
            ATTR_EXPORT_HEADROOM: headroom_kwh,
            ATTR_EXPORT_ALLOWED: export_cap_kwh,
            ATTR_EXPORTED_TODAY: grid_feed_today,
            ATTR_DISCHARGE_NEEDED: recommended_discharge_w,
            ATTR_CURRENT_PV: pv_energy_today,
            ATTR_FORECAST_PV: solcast_total_today,
            ATTR_LAST_CALCULATION: self.hass.states.get("sensor.date_time_iso").state
            if self.hass.states.get("sensor.date_time_iso")
            else None,
            "current_soc": current_soc,
            "min_soc": min_soc,
            "target_export": target_export,
            "solcast_forecast_so_far": solcast_forecast_so_far_value,
        }

    @property
    def discharge_active(self) -> bool:
        """Return if discharge is currently active."""
        return self._discharge_active

    def set_discharge_active(self, active: bool) -> None:
        """Set discharge active state."""
        self._discharge_active = active
        _LOGGER.info("Discharge active state set to: %s", active)
