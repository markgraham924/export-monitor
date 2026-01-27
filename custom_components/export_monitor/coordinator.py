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
    CONF_OBSERVE_RESERVE_SOC,
    CONF_PV_ENERGY_TODAY,
    CONF_RESERVE_SOC_SENSOR,
    CONF_SAFETY_MARGIN,
    CONF_SOLCAST_FORECAST_SO_FAR,
    CONF_SOLCAST_TOTAL_TODAY,
    CONF_TARGET_EXPORT,
    DEFAULT_MIN_SOC,
    DEFAULT_OBSERVE_RESERVE_SOC,
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
        self._discharge_start_export = None  # Grid export when discharge started
        self._discharge_target_energy = None  # Energy to discharge (kWh)
        self._discharge_start_time = None  # When discharge started
        self._calculated_duration = None  # Calculated discharge duration (minutes)
        self._stop_discharge_callback = None  # Callback to stop discharge

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

    def _calculate_discharge_duration(
        self,
        headroom_kwh: float,
        target_export_w: float,
        background_load_buffer: float = 0.1,
    ) -> float:
        """Calculate discharge duration in minutes.
        
        Args:
            headroom_kwh: Energy headroom available (kWh)
            target_export_w: Target export power (W)
            background_load_buffer: Buffer factor for background load (default 10%)
            
        Returns:
            Duration in minutes
        """
        if target_export_w <= 0 or headroom_kwh <= 0:
            return 0.0
        
        # Convert target export to kW
        target_export_kw = target_export_w / 1000
        
        # Calculate base duration in hours, then convert to minutes
        base_duration_hours = headroom_kwh / target_export_kw
        
        # Add buffer for background load (increases duration)
        duration_with_buffer_hours = base_duration_hours * (1 + background_load_buffer)
        
        # Convert to minutes
        duration_minutes = duration_with_buffer_hours * 60
        
        _LOGGER.debug(
            "Calculated discharge duration: %.1f minutes (headroom: %.3f kWh, target: %.0f W, buffer: %.0f%%)",
            duration_minutes,
            headroom_kwh,
            target_export_w,
            background_load_buffer * 100,
        )
        
        return round(duration_minutes, 1)

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
        
        # Get reserve SOC configuration
        reserve_soc_sensor = config_data.get(CONF_RESERVE_SOC_SENSOR)
        observe_reserve_soc = config_data.get(CONF_OBSERVE_RESERVE_SOC, DEFAULT_OBSERVE_RESERVE_SOC)
        reserve_soc_target = None
        reserve_limit_reached = False
        
        if reserve_soc_sensor and observe_reserve_soc:
            reserve_soc_target = self._get_sensor_value(reserve_soc_sensor)
            if reserve_soc_target is not None and current_soc < reserve_soc_target:
                reserve_limit_reached = True
                _LOGGER.warning(
                    "Reserve SOC limit reached: current %.1f%% < reserve target %.1f%%",
                    current_soc,
                    reserve_soc_target,
                )

        # Calculate export cap and headroom (kWh)
        export_cap_kwh, headroom_kwh = self._calculate_export_headroom(
            pv_energy_today,
            solcast_total_today,
            grid_feed_today,
            safety_margin,
        )

        # Calculate discharge power and duration
        recommended_discharge_w = 0.0
        calculated_duration_minutes = 0.0
        
        if current_soc > min_soc and headroom_kwh > 0:
            if target_export > 0:
                # Use target_export as the discharge power
                recommended_discharge_w = target_export
                # Calculate duration based on headroom and target power
                calculated_duration_minutes = self._calculate_discharge_duration(
                    headroom_kwh, target_export
                )
            else:
                # Fallback: assume 1 hour if no target_export configured
                recommended_discharge_w = headroom_kwh * 1000
                calculated_duration_minutes = 60.0
        
        # Store calculated duration for service use
        self._calculated_duration = calculated_duration_minutes
        
        # Check if discharge is active and we've exported enough
        discharge_complete = False
        if self._discharge_active and self._discharge_start_export is not None:
            energy_exported_since_start = grid_feed_today - self._discharge_start_export
            if self._discharge_target_energy and energy_exported_since_start >= self._discharge_target_energy:
                discharge_complete = True
                _LOGGER.info(
                    "Discharge target reached: exported %.3f kWh (target: %.3f kWh)",
                    energy_exported_since_start,
                    self._discharge_target_energy,
                )
        
        # Check if discharge should be stopped due to reserve limit
        if self._discharge_active and reserve_limit_reached:
            _LOGGER.warning(
                "Stopping discharge: reserve SOC limit reached (%.1f%% < %.1f%%)",
                current_soc,
                reserve_soc_target if reserve_soc_target else 0,
            )
            # Trigger stop discharge callback if set
            if self._stop_discharge_callback:
                self.hass.async_create_task(self._stop_discharge_callback())

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
            "calculated_duration": calculated_duration_minutes,
            "discharge_complete": discharge_complete,
            "reserve_soc_target": reserve_soc_target,
            "reserve_limit_reached": reserve_limit_reached,
            "observe_reserve_soc": observe_reserve_soc,
        }

    @property
    def discharge_active(self) -> bool:
        """Return if discharge is currently active."""
        return self._discharge_active

    def set_discharge_active(self, active: bool, grid_export: float | None = None, target_energy: float | None = None) -> None:
        """Set discharge active state and tracking parameters.
        
        Args:
            active: Whether discharge is active
            grid_export: Current grid export when starting (kWh)
            target_energy: Target energy to discharge (kWh)
        """
        self._discharge_active = active
        if active:
            self._discharge_start_export = grid_export
            self._discharge_target_energy = target_energy
            import datetime
            self._discharge_start_time = datetime.datetime.now()
            _LOGGER.info(
                "Discharge started: initial export %.3f kWh, target %.3f kWh",
                grid_export if grid_export else 0,
                target_energy if target_energy else 0,
            )
        else:
            self._discharge_start_export = None
            self._discharge_target_energy = None
            self._discharge_start_time = None
            _LOGGER.info("Discharge stopped")
    
    def set_stop_discharge_callback(self, callback) -> None:
        """Set callback to be called when discharge should be stopped."""
        self._stop_discharge_callback = callback

