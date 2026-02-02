"""Data update coordinator for Energy Export Monitor."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_CURRENT_CI_INDEX,
    ATTR_CURRENT_CI_VALUE,
    ATTR_CURRENT_PV,
    ATTR_DISCHARGE_NEEDED,
    ATTR_DISCHARGE_PLAN,
    ATTR_EXPORT_ALLOWED,
    ATTR_EXPORT_HEADROOM,
    ATTR_EXPORTED_TODAY,
    ATTR_FORECAST_PV,
    ATTR_LAST_CALCULATION,
    CONF_CI_FORECAST_SENSOR,
    CONF_CURRENT_SOC,
    CONF_ENABLE_CI_PLANNING,
    CONF_GRID_FEED_TODAY,
    CONF_MIN_SOC,
    CONF_OBSERVE_RESERVE_SOC,
    CONF_PV_ENERGY_TODAY,
    CONF_RESERVE_SOC_SENSOR,
    CONF_SAFETY_MARGIN,
    CONF_SOLCAST_FORECAST_SO_FAR,
    CONF_SOLCAST_TOTAL_TODAY,
    CONF_TARGET_EXPORT,
    DEFAULT_ENABLE_CI_PLANNING,
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

    def _parse_ci_forecast(
        self, sensor_state_str: str | None, attributes: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Parse Carbon Intensity forecast data from sensor state or attributes."""
        data: dict[str, Any] | None = None

        # Prefer JSON in state, if present
        if sensor_state_str:
            try:
                data = json.loads(sensor_state_str)
            except (json.JSONDecodeError, TypeError):
                data = None

        # Fallback: many sensors store forecast in attributes
        if data is None and attributes:
            attr_data = attributes.get("data")
            if isinstance(attr_data, dict):
                data = attr_data
            elif isinstance(attr_data, list):
                # Some integrations expose list of periods directly
                return {"periods": attr_data, "region": attributes.get("shortname")}

        if not isinstance(data, dict):
            _LOGGER.warning("Could not parse CI forecast sensor data")
            return None

        if "data" not in data or not isinstance(data.get("data"), dict):
            _LOGGER.warning("CI forecast data missing or invalid structure")
            return None

        # Extract time periods
        periods = data.get("data", {}).get("data", [])
        if not isinstance(periods, list) or len(periods) == 0:
            _LOGGER.warning("No CI forecast periods found")
            return None

        return {"periods": periods, "region": data.get("shortname")}

    def _find_highest_ci_periods(
        self, periods: list[dict], headroom_kwh: float, discharge_power_kw: float
    ) -> list[dict]:
        """Find and rank highest CI periods, build discharge plan within headroom."""
        if not periods or headroom_kwh <= 0 or discharge_power_kw <= 0:
            return []

        now = datetime.now(timezone.utc)
        future_periods = []

        for period in periods:
            try:
                from_time = datetime.fromisoformat(period["from"].replace("Z", "+00:00"))
                to_time = datetime.fromisoformat(period["to"].replace("Z", "+00:00"))
                intensity_forecast = period.get("intensity", {}).get("forecast", 0)
                intensity_index = period.get("intensity", {}).get("index", "unknown")

                # Only consider future periods
                if to_time > now:
                    future_periods.append(
                        {
                            "from": from_time,
                            "to": to_time,
                            "duration_minutes": (to_time - from_time).total_seconds() / 60,
                            "ci_value": intensity_forecast,
                            "ci_index": intensity_index,
                        }
                    )
            except (ValueError, KeyError) as err:
                _LOGGER.debug("Error parsing CI period: %s", err)
                continue

        # Sort by CI value (highest first)
        future_periods.sort(key=lambda x: x["ci_value"], reverse=True)

        # Build plan greedily within headroom
        plan = []
        remaining_headroom = headroom_kwh

        for period in future_periods:
            if remaining_headroom <= 0:
                break

            # Calculate max energy we can export in this period
            period_capacity_kwh = discharge_power_kw * (period["duration_minutes"] / 60)
            export_energy = min(period_capacity_kwh, remaining_headroom)

            # Calculate duration to discharge this energy
            export_duration = (export_energy / discharge_power_kw) * 60

            plan.append(
                {
                    "from": period["from"].isoformat(),
                    "to": period["to"].isoformat(),
                    "duration_minutes": export_duration,
                    "energy_kwh": export_energy,
                    "ci_value": period["ci_value"],
                    "ci_index": period["ci_index"],
                }
            )

            remaining_headroom -= export_energy

        return plan

    def _get_current_ci_index(self, periods: list[dict]) -> tuple[int | None, str | None]:
        """Get current CI intensity value and index."""
        now = datetime.now(timezone.utc)

        for period in periods:
            try:
                from_time = datetime.fromisoformat(period["from"].replace("Z", "+00:00"))
                to_time = datetime.fromisoformat(period["to"].replace("Z", "+00:00"))

                if from_time <= now < to_time:
                    ci_value = period.get("intensity", {}).get("forecast", None)
                    ci_index = period.get("intensity", {}).get("index", None)
                    return ci_value, ci_index
            except (ValueError, KeyError):
                continue

        return None, None

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
                # If no target_export configured, calculate based on headroom
                # Base: discharge over 1 hour. Duration will include 10% buffer via calculation.
                recommended_discharge_w = headroom_kwh * 1000
                calculated_duration_minutes = self._calculate_discharge_duration(
                    headroom_kwh, recommended_discharge_w
                )
        
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
        
        # Auto-stop discharge if any limit is reached
        should_stop_discharge = False
        stop_reason = ""
        
        if self._discharge_active:
            # Check headroom exhausted (most critical - prevents export limit breach)
            if headroom_kwh <= 0:
                should_stop_discharge = True
                stop_reason = f"Export headroom exhausted ({headroom_kwh:.3f} kWh)"
            # Check discharge target reached
            elif discharge_complete:
                should_stop_discharge = True
                stop_reason = "Discharge target reached"
            # Check reserve SOC limit
            elif reserve_limit_reached:
                should_stop_discharge = True
                stop_reason = f"Reserve SOC limit reached ({current_soc:.1f}% < {reserve_soc_target:.1f}%)"
            
            if should_stop_discharge:
                _LOGGER.warning("Auto-stopping discharge: %s", stop_reason)
                # Call the stop discharge service
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        DOMAIN,
                        "stop_discharge",
                        {},
                    )
                )

        # CI Planning (optional feature)
        discharge_plan = []
        current_ci_value = None
        current_ci_index = None

        ci_sensor = config_data.get(CONF_CI_FORECAST_SENSOR)
        enable_ci_planning = config_data.get(CONF_ENABLE_CI_PLANNING, DEFAULT_ENABLE_CI_PLANNING)

        if ci_sensor and enable_ci_planning and target_export > 0:
            ci_state = self.hass.states.get(ci_sensor)
            if ci_state:
                state_str = None
                if ci_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    state_str = ci_state.state
                ci_data = self._parse_ci_forecast(state_str, ci_state.attributes)
                if ci_data:
                    periods = ci_data.get("periods", [])
                    # Get current CI
                    current_ci_value, current_ci_index = self._get_current_ci_index(periods)
                    # Generate discharge plan for highest CI periods
                    if headroom_kwh > 0 and target_export > 0:
                        discharge_power_kw = target_export / 1000
                        discharge_plan = self._find_highest_ci_periods(
                            periods, headroom_kwh, discharge_power_kw
                        )
                        _LOGGER.debug(
                            "Generated CI discharge plan: %d periods, %.3f kWh total",
                            len(discharge_plan),
                            sum(p.get("energy_kwh", 0) for p in discharge_plan),
                        )

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
            ATTR_DISCHARGE_PLAN: discharge_plan,
            ATTR_CURRENT_CI_VALUE: current_ci_value,
            ATTR_CURRENT_CI_INDEX: current_ci_index,
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

