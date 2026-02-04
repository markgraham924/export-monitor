"""Data update coordinator for Energy Export Monitor."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
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
    ATTR_DISCHARGE_PLAN_TODAY,
    ATTR_DISCHARGE_PLAN_TOMORROW,
    ATTR_CHARGE_PLAN_TODAY,
    ATTR_CHARGE_PLAN_TOMORROW,
    ATTR_EXPORT_ALLOWED,
    ATTR_EXPORT_HEADROOM,
    ATTR_EXPORTED_TODAY,
    ATTR_FORECAST_PV,
    ATTR_LAST_CALCULATION,
    CONF_CHARGE_WINDOW_END,
    CONF_CHARGE_WINDOW_START,
    CONF_CHARGE_POWER_KW,
    CONF_BATTERY_CAPACITY_KWH,
    CONF_CI_FORECAST_SENSOR,
    CONF_CURRENT_SOC,
    CONF_DISCHARGE_CUTOFF_SOC,
    CONF_ENABLE_AUTO_DISCHARGE,
    CONF_ENABLE_AUTO_CHARGE,
    CONF_ENABLE_CHARGE_PLANNING,
    CONF_ENABLE_CI_PLANNING,
    CONF_EXPORT_WINDOW_START,
    CONF_EXPORT_WINDOW_END,
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
    DEFAULT_CHARGE_WINDOW_END,
    DEFAULT_CHARGE_WINDOW_START,
    DEFAULT_CHARGE_POWER_KW,
    DEFAULT_BATTERY_CAPACITY_KWH,
    DEFAULT_ENABLE_CI_PLANNING,
    DEFAULT_EXPORT_WINDOW_START,
    DEFAULT_EXPORT_WINDOW_END,
    DEFAULT_MIN_SOC,
    DEFAULT_OBSERVE_RESERVE_SOC,
    DEFAULT_SAFETY_MARGIN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TARGET_EXPORT,
    DOMAIN,
    SERVICE_START_DISCHARGE,
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
        self._last_auto_discharge_window = None  # Track which window was last auto-discharged
        self._charge_active = False  # Track if charging is active
        self._charge_start_time = None  # When charge started
        self._last_auto_charge_window = None  # Track which window was last auto-charged

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

        if "data" not in data:
            _LOGGER.warning("CI forecast data missing or invalid structure")
            return None

        # Extract time periods
        periods: list[dict] | None = None
        raw_periods = data.get("data")
        if isinstance(raw_periods, list):
            periods = raw_periods
        elif isinstance(raw_periods, dict):
            nested = raw_periods.get("data", [])
            if isinstance(nested, list):
                periods = nested

        if not periods:
            _LOGGER.warning("No CI forecast periods found")
            return None

        return {"periods": periods, "region": data.get("shortname")}

    def _generate_today_plan(
        self, 
        periods: list[dict], 
        headroom_kwh: float, 
        discharge_power_kw: float,
        solar_generated: float,
        solar_predicted: float,
        export_window_start: str = "00:00",
        export_window_end: str = "23:59",
    ) -> list[dict]:
        """Generate discharge plan for today (remaining slots until midnight).
        
        Args:
            periods: CI forecast periods from CI sensor
            headroom_kwh: Available energy headroom for export
            discharge_power_kw: Discharge power in kW
            solar_generated: Solar generated today so far (kWh)
            solar_predicted: Predicted solar for today (kWh)
            export_window_start: Start time for export window (HH:MM)
            export_window_end: End time for export window (HH:MM)
            
        Returns:
            List of discharge windows for today
        """
        if not periods or headroom_kwh <= 0 or discharge_power_kw <= 0:
            return []

        now = datetime.now(timezone.utc)
        today_midnight = now.replace(hour=23, minute=59, second=59)
        today_energy_budget = max(solar_generated, solar_predicted)
        
        # Parse export window times
        try:
            window_start_parts = export_window_start.split(":") if isinstance(export_window_start, str) else export_window_start
            window_start_time = datetime.strptime(f"{window_start_parts[0]}:{window_start_parts[1]}", "%H:%M").time()
            window_end_parts = export_window_end.split(":") if isinstance(export_window_end, str) else export_window_end
            window_end_time = datetime.strptime(f"{window_end_parts[0]}:{window_end_parts[1]}", "%H:%M").time()
        except (ValueError, IndexError, AttributeError):
            _LOGGER.warning("Invalid export window times, using full day")
            window_start_time = datetime.strptime("00:00", "%H:%M").time()
            window_end_time = datetime.strptime("23:59", "%H:%M").time()
        
        # Find periods remaining today
        future_periods = []
        for period in periods:
            try:
                from_time = datetime.fromisoformat(period["from"].replace("Z", "+00:00"))
                to_time = datetime.fromisoformat(period["to"].replace("Z", "+00:00"))
                
                # Only consider periods that occur today and haven't ended
                if to_time > now and from_time.date() == now.date():
                    intensity_forecast = period.get("intensity", {}).get("forecast", 0)
                    intensity_index = period.get("intensity", {}).get("index", "unknown")
                    
                    # Adjust from_time if it's before now
                    effective_from = max(from_time, now)
                    
                    # Check if period overlaps with export window
                    from_time_local = effective_from.astimezone().time()
                    to_time_local = to_time.astimezone().time()
                    
                    if from_time_local <= window_end_time and to_time_local >= window_start_time:
                        future_periods.append({
                            "from": effective_from,
                            "to": to_time,
                            "duration_minutes": (to_time - effective_from).total_seconds() / 60,
                            "ci_value": intensity_forecast,
                            "ci_index": intensity_index,
                        })
            except (ValueError, KeyError) as err:
                _LOGGER.debug("Error parsing CI period: %s", err)
                continue

        # Sort by CI value (highest first - we want to export during high CI periods)
        future_periods.sort(key=lambda x: x["ci_value"], reverse=True)

        # Build plan greedily within headroom
        plan = []
        remaining_headroom = min(headroom_kwh, today_energy_budget)

        for period in future_periods:
            if remaining_headroom <= 0:
                break

            # Calculate max energy we can export in this period
            period_capacity_kwh = discharge_power_kw * (period["duration_minutes"] / 60)
            export_energy = min(period_capacity_kwh, remaining_headroom)

            # Calculate duration to discharge this energy
            export_duration = (export_energy / discharge_power_kw) * 60

            plan.append({
                "from": period["from"].isoformat(),
                "to": period["to"].isoformat(),
                "duration_minutes": export_duration,
                "energy_kwh": export_energy,
                "ci_value": period["ci_value"],
                "ci_index": period["ci_index"],
            })

            remaining_headroom -= export_energy

        return plan

    def _generate_tomorrow_plan(
        self,
        periods: list[dict],
        solar_predicted_tomorrow: float,
        discharge_power_kw: float,
        export_window_start: str = "00:00",
        export_window_end: str = "23:59",
    ) -> list[dict]:
        """Generate discharge plan for tomorrow (full 24hrs using predicted solar).
        
        Args:
            periods: CI forecast periods from CI sensor
            solar_predicted_tomorrow: Predicted solar for tomorrow from Solcast (kWh)
            discharge_power_kw: Discharge power in kW
            export_window_start: Start time for export window (HH:MM)
            export_window_end: End time for export window (HH:MM)
            
        Returns:
            List of discharge windows for tomorrow
        """
        if not periods or solar_predicted_tomorrow <= 0 or discharge_power_kw <= 0:
            return []

        now = datetime.now(timezone.utc)
        tomorrow = now.date() + timedelta(days=1)
        tomorrow_start = datetime.combine(tomorrow, datetime.min.time()).replace(tzinfo=timezone.utc)
        tomorrow_midnight = tomorrow_start.replace(hour=23, minute=59, second=59)

        # Parse export window times
        try:
            window_start_parts = export_window_start.split(":") if isinstance(export_window_start, str) else export_window_start
            window_start_time = datetime.strptime(f"{window_start_parts[0]}:{window_start_parts[1]}", "%H:%M").time()
            window_end_parts = export_window_end.split(":") if isinstance(export_window_end, str) else export_window_end
            window_end_time = datetime.strptime(f"{window_end_parts[0]}:{window_end_parts[1]}", "%H:%M").time()
        except (ValueError, IndexError, AttributeError):
            _LOGGER.warning("Invalid export window times, using full day")
            window_start_time = datetime.strptime("00:00", "%H:%M").time()
            window_end_time = datetime.strptime("23:59", "%H:%M").time()

        # Find periods for tomorrow
        future_periods = []
        for period in periods:
            try:
                from_time = datetime.fromisoformat(period["from"].replace("Z", "+00:00"))
                to_time = datetime.fromisoformat(period["to"].replace("Z", "+00:00"))

                # Only consider periods that occur on tomorrow's date
                if from_time.date() == tomorrow:
                    intensity_forecast = period.get("intensity", {}).get("forecast", 0)
                    intensity_index = period.get("intensity", {}).get("index", "unknown")
                    
                    # Check if period overlaps with export window
                    from_time_local = from_time.astimezone().time()
                    to_time_local = to_time.astimezone().time()
                    
                    if from_time_local <= window_end_time and to_time_local >= window_start_time:
                        future_periods.append({
                            "from": from_time,
                            "to": to_time,
                            "duration_minutes": (to_time - from_time).total_seconds() / 60,
                            "ci_value": intensity_forecast,
                            "ci_index": intensity_index,
                        })
            except (ValueError, KeyError) as err:
                _LOGGER.debug("Error parsing CI period: %s", err)
                continue

        # Sort by CI value (highest first - export during high CI periods)
        future_periods.sort(key=lambda x: x["ci_value"], reverse=True)

        # Build plan greedily using tomorrow's predicted solar as headroom
        plan = []
        remaining_headroom = solar_predicted_tomorrow

        for period in future_periods:
            if remaining_headroom <= 0:
                break

            # Calculate max energy we can export in this period
            period_capacity_kwh = discharge_power_kw * (period["duration_minutes"] / 60)
            export_energy = min(period_capacity_kwh, remaining_headroom)

            # Calculate duration to discharge this energy
            export_duration = (export_energy / discharge_power_kw) * 60

            plan.append({
                "from": period["from"].isoformat(),
                "to": period["to"].isoformat(),
                "duration_minutes": export_duration,
                "energy_kwh": export_energy,
                "ci_value": period["ci_value"],
                "ci_index": period["ci_index"],
            })

            remaining_headroom -= export_energy

        return plan

    def _find_highest_ci_periods(
        self, periods: list[dict], headroom_kwh: float, discharge_power_kw: float,
        export_window_start: str = "00:00", export_window_end: str = "23:59"
    ) -> list[dict]:
        """Find and rank highest CI periods, build discharge plan within headroom and export window."""
        if not periods or headroom_kwh <= 0 or discharge_power_kw <= 0:
            return []

        now = datetime.now(timezone.utc)
        future_periods = []

        # Parse export window times
        try:
            window_start_parts = export_window_start.split(":") if isinstance(export_window_start, str) else export_window_start
            window_start_time = datetime.strptime(f"{window_start_parts[0]}:{window_start_parts[1]}", "%H:%M").time()
            window_end_parts = export_window_end.split(":") if isinstance(export_window_end, str) else export_window_end
            window_end_time = datetime.strptime(f"{window_end_parts[0]}:{window_end_parts[1]}", "%H:%M").time()
        except (ValueError, IndexError, AttributeError):
            _LOGGER.warning("Invalid export window times, using full day")
            window_start_time = datetime.strptime("00:00", "%H:%M").time()
            window_end_time = datetime.strptime("23:59", "%H:%M").time()

        for period in periods:
            try:
                from_time = datetime.fromisoformat(period["from"].replace("Z", "+00:00"))
                to_time = datetime.fromisoformat(period["to"].replace("Z", "+00:00"))
                intensity_forecast = period.get("intensity", {}).get("forecast", 0)
                intensity_index = period.get("intensity", {}).get("index", "unknown")

                # Only consider future periods within export window
                if to_time > now:
                    from_time_local = from_time.astimezone().time()
                    to_time_local = to_time.astimezone().time()
                    
                    # Check if period overlaps with export window
                    if from_time_local <= window_end_time and to_time_local >= window_start_time:
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

        # Sort by CI value (highest first) - prioritize high CI periods
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

    def _generate_next_charge_session(
        self,
        periods: list[dict],
        current_soc: float,
        charge_power_kw: float,
        charge_window_start: str,
        charge_window_end: str,
        battery_capacity_kwh: float,
    ) -> list[dict]:
        """Generate charge plan for the next upcoming charge session.
        
        Unlike discharge planning which has T&Cs restrictions, charge planning
        is simpler: charge during the greenest (lowest CI) periods in the next
        charge window. Since charge windows are typically overnight (00:00-07:00),
        we look forward to find the next charge window and plan for that session.
        
        Args:
            periods: CI forecast periods
            current_soc: Current battery state of charge (%)
            charge_power_kw: Charge power in kW
            charge_window_start: Charge window start time (HH:MM)
            charge_window_end: Charge window end time (HH:MM)
            battery_capacity_kwh: Battery total capacity in kWh
            
        Returns:
            List of charge plan windows with start/end times and energy
        """
        if not periods or charge_power_kw <= 0 or battery_capacity_kwh <= 0:
            return []
        
        # Calculate energy needed to reach 100% SOC
        if current_soc >= 100:
            return []  # Already fully charged
        
        soc_to_charge = 100 - current_soc  # Percentage to charge
        energy_needed_kwh = (soc_to_charge / 100) * battery_capacity_kwh
        
        if energy_needed_kwh <= 0:
            return []
        
        # Parse charge window times (handle both HH:MM and HH:MM:SS formats)
        try:
            start_parts = charge_window_start.split(":")
            end_parts = charge_window_end.split(":")
            window_start_hour, window_start_min = int(start_parts[0]), int(start_parts[1])
            window_end_hour, window_end_min = int(end_parts[0]), int(end_parts[1])
        except (ValueError, AttributeError, IndexError):
            _LOGGER.error("Invalid charge window times: %s - %s", charge_window_start, charge_window_end)
            return []
        
        now = datetime.now(timezone.utc)
        window_start_time = time(window_start_hour, window_start_min)
        window_end_time = time(window_end_hour, window_end_min)
        
        # Determine when the next charge window starts
        # If charge window is overnight (e.g., 00:00-07:00) and it's currently 17:31,
        # the next charge window starts tonight at 00:00 (which is tomorrow's date)
        current_time = now.time()
        
        # Check if we're currently in a charge window
        in_window = False
        if window_start_time <= window_end_time:
            # Normal window (e.g., 08:00-16:00)
            in_window = window_start_time <= current_time <= window_end_time
        else:
            # Overnight window (e.g., 23:00-06:00)
            in_window = current_time >= window_start_time or current_time <= window_end_time
        
        # Find the next charge window start datetime
        if in_window:
            # We're in the window now, so "next" session is happening now
            next_window_start = now
        else:
            # Find when the next window starts
            if window_start_time <= window_end_time:
                # Normal window
                if current_time < window_start_time:
                    # Window is later today
                    next_window_start = datetime.combine(now.date(), window_start_time, tzinfo=timezone.utc)
                else:
                    # Window is tomorrow
                    next_window_start = datetime.combine(now.date() + timedelta(days=1), window_start_time, tzinfo=timezone.utc)
            else:
                # Overnight window (e.g., 00:00-07:00)
                if current_time > window_end_time and current_time < window_start_time:
                    # We're between end and start (e.g., 08:00-23:59), so next window starts tonight
                    next_window_start = datetime.combine(now.date(), window_start_time, tzinfo=timezone.utc)
                else:
                    # We're either before end or after start
                    # If we're before end (00:00-07:00), next is tomorrow
                    # If we're after start (00:00-23:59), we need tonight's window
                    if current_time < window_start_time:
                        # We're in the early morning (00:00-00:59) before end, next is tonight
                        next_window_start = datetime.combine(now.date(), window_start_time, tzinfo=timezone.utc)
                    else:
                        # We're after start but technically before it wraps (shouldn't happen)
                        # So assume next is tonight
                        next_window_start = datetime.combine(now.date(), window_start_time, tzinfo=timezone.utc)
        
        # Calculate next window end
        if window_start_time <= window_end_time:
            # Normal window
            next_window_end = datetime.combine(next_window_start.date(), window_end_time, tzinfo=timezone.utc)
        else:
            # Overnight window - end is next day
            next_window_end = datetime.combine(next_window_start.date() + timedelta(days=1), window_end_time, tzinfo=timezone.utc)
        
        _LOGGER.debug(
            "Next charge window: %s to %s (current time: %s, window config: %s-%s)",
            next_window_start.isoformat(),
            next_window_end.isoformat(),
            now.isoformat(),
            charge_window_start,
            charge_window_end,
        )
        
        # Filter periods to those within the next charge window
        filtered_periods = []
        _LOGGER.debug("Total periods available: %d", len(periods))
        for period in periods:
            try:
                from_time = datetime.fromisoformat(period["from"].replace("Z", "+00:00"))
                to_time = datetime.fromisoformat(period["to"].replace("Z", "+00:00"))
                
                # Check if period overlaps with next charge window
                if to_time < next_window_start or from_time > next_window_end:
                    _LOGGER.debug(
                        "Period %s-%s outside window (window: %s-%s)",
                        from_time.isoformat(),
                        to_time.isoformat(),
                        next_window_start.isoformat(),
                        next_window_end.isoformat(),
                    )
                    continue
                
                # Trim period to window boundaries
                actual_start = max(from_time, next_window_start)
                actual_end = min(to_time, next_window_end)
                
                if actual_start >= actual_end:
                    _LOGGER.debug("Period trimmed to zero duration")
                    continue
                
                ci_value = period.get("intensity", {}).get("forecast", 0)
                _LOGGER.debug("Including period %s-%s CI:%d", actual_start.isoformat(), actual_end.isoformat(), ci_value)
                filtered_periods.append({
                    "from": actual_start,
                    "to": actual_end,
                    "ci": ci_value,
                })
            except (ValueError, KeyError) as err:
                _LOGGER.debug("Skipping invalid period: %s", err)
                continue
        
        _LOGGER.info(
            "Charge window %s-%s: found %d matching periods out of %d total (energy needed: %.2f kWh)",
            charge_window_start,
            charge_window_end,
            len(filtered_periods),
            len(periods),
            energy_needed_kwh,
        )
        
        if not filtered_periods:
            _LOGGER.info("No charge periods found in next window %s - %s", charge_window_start, charge_window_end)
            return []
        
        # Sort by CI ascending (lowest first for charging - greenest power)
        filtered_periods.sort(key=lambda p: p["ci"])
        
        # Allocate energy to lowest CI periods
        plan = []
        remaining_energy = energy_needed_kwh
        
        for period in filtered_periods:
            if remaining_energy <= 0:
                break
            
            # Calculate period duration
            period_duration_hours = (period["to"] - period["from"]).total_seconds() / 3600
            
            # Energy that can be charged in this period
            period_energy = charge_power_kw * period_duration_hours
            
            # Allocate energy (limited by what's needed)
            allocated_energy = min(period_energy, remaining_energy)
            
            plan.append({
                "period_start": period["from"].isoformat(),
                "period_end": period["to"].isoformat(),
                "energy_kwh": round(allocated_energy, 3),
                "ci_value": period["ci"],
            })
            
            remaining_energy -= allocated_energy
        
        _LOGGER.info(
            "Generated next charge session plan: %d periods, %.3f kWh total (needed %.3f kWh)",
            len(plan),
            sum(p["energy_kwh"] for p in plan),
            energy_needed_kwh,
        )
        
        return plan

    def _generate_charge_plan_today(
        self,
        periods: list[dict],
        current_soc: float,
        discharge_cutoff_soc: float,
        charge_power_kw: float,
        charge_window_start: str,
        charge_window_end: str,
        battery_capacity_kwh: float,
    ) -> list[dict]:
        """Generate charge plan for today based on LOWEST CI periods.
        
        Args:
            periods: CI forecast periods
            current_soc: Current battery state of charge (%)
            discharge_cutoff_soc: Discharge cutoff SOC (%)
            charge_power_kw: Charge power in kW
            charge_window_start: Charge window start time (HH:MM)
            charge_window_end: Charge window end time (HH:MM)
            battery_capacity_kwh: Battery total capacity in kWh
            
        Returns:
            List of charge plan windows with start/end times and energy
        """
        if not periods or charge_power_kw <= 0 or battery_capacity_kwh <= 0:
            return []
        
        # Calculate energy needed to reach 100% SOC
        if current_soc >= 100:
            return []  # Already fully charged
        
        soc_to_charge = 100 - current_soc  # Percentage to charge
        energy_needed_kwh = (soc_to_charge / 100) * battery_capacity_kwh
        
        if energy_needed_kwh <= 0:
            return []
        
        # Parse charge window times (handle both HH:MM and HH:MM:SS formats)
        try:
            start_parts = charge_window_start.split(":")
            end_parts = charge_window_end.split(":")
            window_start_hour, window_start_min = int(start_parts[0]), int(start_parts[1])
            window_end_hour, window_end_min = int(end_parts[0]), int(end_parts[1])
        except (ValueError, AttributeError, IndexError):
            _LOGGER.error("Invalid charge window times: %s - %s", charge_window_start, charge_window_end)
            return []
        
        now = datetime.now(timezone.utc)
        today = now.date()
        
        # Filter periods to today and within charge window
        filtered_periods = []
        for period in periods:
            try:
                from_time = datetime.fromisoformat(period["from"].replace("Z", "+00:00"))
                to_time = datetime.fromisoformat(period["to"].replace("Z", "+00:00"))
                
                # Only today's periods
                if from_time.date() != today:
                    continue
                
                # Check if period overlaps with charge window
                period_start_time = from_time.time()
                period_end_time = to_time.time()
                window_start_time = time(window_start_hour, window_start_min)
                window_end_time = time(window_end_hour, window_end_min)
                
                # Handle overnight window (e.g., 23:00 - 06:00)
                if window_start_time <= window_end_time:
                    # Normal window within same day
                    if period_end_time < window_start_time or period_start_time > window_end_time:
                        continue
                else:
                    # Overnight window
                    if period_end_time < window_start_time and period_start_time > window_end_time:
                        continue
                
                ci_value = period.get("intensity", {}).get("forecast", 0)
                filtered_periods.append({
                    "from": from_time,
                    "to": to_time,
                    "ci": ci_value,
                })
            except (ValueError, KeyError) as err:
                _LOGGER.debug("Skipping invalid period: %s", err)
                continue
        
        if not filtered_periods:
            _LOGGER.info("No charge periods found in window %s - %s", charge_window_start, charge_window_end)
            return []
        
        # Sort by CI ascending (lowest first for charging)
        filtered_periods.sort(key=lambda p: p["ci"])
        
        # Allocate energy to lowest CI periods
        plan = []
        remaining_energy = energy_needed_kwh
        
        for period in filtered_periods:
            if remaining_energy <= 0:
                break
            
            # Calculate period duration
            period_duration_hours = (period["to"] - period["from"]).total_seconds() / 3600
            
            # Energy that can be charged in this period
            period_energy = charge_power_kw * period_duration_hours
            
            # Allocate energy (limited by what's needed)
            allocated_energy = min(period_energy, remaining_energy)
            
            plan.append({
                "period_start": period["from"].isoformat(),
                "period_end": period["to"].isoformat(),
                "energy_kwh": round(allocated_energy, 3),
                "ci_value": period["ci"],
            })
            
            remaining_energy -= allocated_energy
        
        _LOGGER.info(
            "Generated charge plan: %d periods, %.3f kWh total (needed %.3f kWh)",
            len(plan),
            sum(p["energy_kwh"] for p in plan),
            energy_needed_kwh,
        )
        
        return plan

    def _generate_charge_plan_tomorrow(
        self,
        periods: list[dict],
        discharge_cutoff_soc: float,
        charge_power_kw: float,
        charge_window_start: str,
        charge_window_end: str,
        battery_capacity_kwh: float,
    ) -> list[dict]:
        """Generate charge plan for tomorrow based on LOWEST CI periods.
        
        Similar to today's plan but for tomorrow.
        """
        if not periods or charge_power_kw <= 0 or battery_capacity_kwh <= 0:
            return []
        
        # For tomorrow, assume we want to reach 100% SOC
        # This gives maximum flexibility for the next day
        energy_needed_kwh = battery_capacity_kwh
        
        # Parse charge window times (handle both HH:MM and HH:MM:SS formats)
        try:
            start_parts = charge_window_start.split(":")
            end_parts = charge_window_end.split(":")
            window_start_hour, window_start_min = int(start_parts[0]), int(start_parts[1])
            window_end_hour, window_end_min = int(end_parts[0]), int(end_parts[1])
        except (ValueError, AttributeError, IndexError):
            _LOGGER.error("Invalid charge window times: %s - %s", charge_window_start, charge_window_end)
            return []
        
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).date()
        
        # Filter periods to tomorrow and within charge window
        filtered_periods = []
        for period in periods:
            try:
                from_time = datetime.fromisoformat(period["from"].replace("Z", "+00:00"))
                to_time = datetime.fromisoformat(period["to"].replace("Z", "+00:00"))
                
                # Only tomorrow's periods
                if from_time.date() != tomorrow:
                    continue
                
                # Check if period overlaps with charge window
                period_start_time = from_time.time()
                period_end_time = to_time.time()
                window_start_time = time(window_start_hour, window_start_min)
                window_end_time = time(window_end_hour, window_end_min)
                
                # Handle overnight window
                if window_start_time <= window_end_time:
                    if period_end_time < window_start_time or period_start_time > window_end_time:
                        continue
                else:
                    if period_end_time < window_start_time and period_start_time > window_end_time:
                        continue
                
                ci_value = period.get("intensity", {}).get("forecast", 0)
                filtered_periods.append({
                    "from": from_time,
                    "to": to_time,
                    "ci": ci_value,
                })
            except (ValueError, KeyError) as err:
                _LOGGER.debug("Skipping invalid period: %s", err)
                continue
        
        if not filtered_periods:
            return []
        
        # Sort by CI ascending (lowest first)
        filtered_periods.sort(key=lambda p: p["ci"])
        
        # Allocate energy to lowest CI periods
        plan = []
        remaining_energy = energy_needed_kwh
        
        for period in filtered_periods:
            if remaining_energy <= 0:
                break
            
            period_duration_hours = (period["to"] - period["from"]).total_seconds() / 3600
            period_energy = charge_power_kw * period_duration_hours
            allocated_energy = min(period_energy, remaining_energy)
            
            plan.append({
                "period_start": period["from"].isoformat(),
                "period_end": period["to"].isoformat(),
                "energy_kwh": round(allocated_energy, 3),
                "ci_value": period["ci"],
            })
            
            remaining_energy -= allocated_energy
        
        return plan

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors and calculate discharge requirements."""
        config_data = {**self.entry.data, **self.entry.options}

        # Get sensor values (kWh)
        current_soc_sensor = config_data.get(CONF_CURRENT_SOC)
        current_soc = self._get_sensor_value(current_soc_sensor) if current_soc_sensor else None
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

        # CI Planning (optional feature) - generate today and tomorrow plans
        discharge_plan_today = []
        discharge_plan_tomorrow = []
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
                    
                    discharge_power_kw = target_export / 1000
                    
                    # Get export window from config
                    export_window_start = config_data.get(CONF_EXPORT_WINDOW_START, DEFAULT_EXPORT_WINDOW_START)
                    export_window_end = config_data.get(CONF_EXPORT_WINDOW_END, DEFAULT_EXPORT_WINDOW_END)
                    
                    # Generate plan for today (remaining hours until midnight)
                    if headroom_kwh > 0:
                        discharge_plan_today = self._generate_today_plan(
                            periods,
                            headroom_kwh,
                            discharge_power_kw,
                            pv_energy_today,
                            solcast_total_today,
                            export_window_start,
                            export_window_end,
                        )
                        _LOGGER.debug(
                            "Generated today's CI discharge plan: %d periods, %.3f kWh total",
                            len(discharge_plan_today),
                            sum(p.get("energy_kwh", 0) for p in discharge_plan_today),
                        )
                    
                    # Generate plan for tomorrow using predicted solar
                    solcast_tomorrow = config_data.get(CONF_SOLCAST_TOMORROW)
                    solcast_tomorrow_value = (
                        self._get_sensor_value(solcast_tomorrow)
                        if solcast_tomorrow
                        else None
                    )
                    if solcast_tomorrow_value and solcast_tomorrow_value > 0:
                        discharge_plan_tomorrow = self._generate_tomorrow_plan(
                            periods,
                            solcast_tomorrow_value,
                            discharge_power_kw,
                            export_window_start,
                            export_window_end,
                        )
                        _LOGGER.debug(
                            "Generated tomorrow's CI discharge plan: %d periods, %.3f kWh total",
                            len(discharge_plan_tomorrow),
                            sum(p.get("energy_kwh", 0) for p in discharge_plan_tomorrow),
                        )

        # Generate charge plan for next charge session if charge planning is enabled
        next_charge_session = []
        enable_charge_planning = config_data.get(CONF_ENABLE_CHARGE_PLANNING, False)
        
        # Fetch CI data for charge planning if needed
        if enable_charge_planning and current_soc is not None:
            ci_data = None
            ci_sensor = config_data.get(CONF_CI_FORECAST_SENSOR)
            if ci_sensor:
                ci_state = self.hass.states.get(ci_sensor)
                if ci_state:
                    state_str = None
                    if ci_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                        state_str = ci_state.state
                    ci_data = self._parse_ci_forecast(state_str, ci_state.attributes)
            
            if ci_data:
                periods = ci_data.get("periods", [])
                if periods:
                    charge_power_kw = config_data.get(CONF_CHARGE_POWER_KW, DEFAULT_CHARGE_POWER_KW)
                    charge_window_start = config_data.get(CONF_CHARGE_WINDOW_START, DEFAULT_CHARGE_WINDOW_START)
                    charge_window_end = config_data.get(CONF_CHARGE_WINDOW_END, DEFAULT_CHARGE_WINDOW_END)
                    battery_capacity_kwh = config_data.get(CONF_BATTERY_CAPACITY_KWH, DEFAULT_BATTERY_CAPACITY_KWH)
                    
                    # Generate charge plan for next charge session
                    next_charge_session = self._generate_next_charge_session(
                        periods,
                        current_soc,
                        charge_power_kw,
                        charge_window_start,
                        charge_window_end,
                        battery_capacity_kwh,
                    )
                    _LOGGER.debug(
                        "Generated next charge session plan: %d periods, %.3f kWh total",
                        len(next_charge_session),
                        sum(p.get("energy_kwh", 0) for p in next_charge_session),
                    )

        # Check for auto-discharge trigger
        enable_auto_discharge = config_data.get(CONF_ENABLE_AUTO_DISCHARGE, False)
        if enable_auto_discharge and discharge_plan_today:
            await self._check_and_trigger_auto_discharge(
                discharge_plan_today,
                current_soc,
                solcast_total_today,
                target_export_kwh,
                min_soc,
                safety_margin,
                discharge_power_kw,
            )

        # Check for auto-charge trigger
        enable_auto_charge = config_data.get(CONF_ENABLE_AUTO_CHARGE, False)
        if enable_auto_charge and next_charge_session:
            await self._check_and_trigger_auto_charge(
                next_charge_session,
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
            ATTR_DISCHARGE_PLAN: discharge_plan_today,  # Keep backward compatibility
            ATTR_DISCHARGE_PLAN_TODAY: discharge_plan_today,
            ATTR_DISCHARGE_PLAN_TOMORROW: discharge_plan_tomorrow,
            "next_charge_session": next_charge_session,
            ATTR_CURRENT_CI_VALUE: current_ci_value,
            ATTR_CURRENT_CI_INDEX: current_ci_index,
            "reserve_limit_reached": reserve_limit_reached,
            "observe_reserve_soc": observe_reserve_soc,
            "current_soc": current_soc,
            "min_soc": min_soc,
            "reserve_soc_target": reserve_soc_target,
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

    @property
    def charge_active(self) -> bool:
        """Return if charge is currently active."""
        return self._charge_active

    def set_charge_active(self, active: bool) -> None:
        """Set charge active state and tracking parameters.
        
        Args:
            active: Whether charge is active
        """
        self._charge_active = active
        if active:
            import datetime
            self._charge_start_time = datetime.datetime.now()
            _LOGGER.info("Charge started at %s", self._charge_start_time)
        else:
            self._charge_start_time = None
            _LOGGER.info("Charge stopped")
            _LOGGER.info("Discharge stopped")

    async def _check_and_trigger_auto_discharge(
        self,
        discharge_plan: list[dict],
        current_soc: float,
        solcast_total_today: float,
        target_export_kwh: float,
        min_soc_percent: float,
        safety_margin: float,
        discharge_power_kw: float,
    ) -> None:
        """Check if we should auto-trigger discharge and call service if needed.
        
        Args:
            discharge_plan: List of discharge plan windows with start/end times
            current_soc: Current battery state of charge (%)
            solcast_total_today: Predicted solar for today (kWh)
            target_export_kwh: Target energy to export (kWh)
            min_soc_percent: Minimum SOC to maintain (%)
            safety_margin: Safety margin in kWh
            discharge_power_kw: Discharge power (kW)
        """
        import datetime
        
        if not discharge_plan or len(discharge_plan) == 0:
            return
        
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # Reset auto-discharge window tracking at midnight
        if self._last_auto_discharge_window and today_str not in self._last_auto_discharge_window:
            self._last_auto_discharge_window = None
        
        # Check each window in the plan
        for window in discharge_plan:
            window_start_str = window.get("period_start", "")
            window_end_str = window.get("period_end", "")
            window_energy = window.get("energy_kwh", 0)
            
            if not window_start_str:
                continue
            
            try:
                # Parse window start time
                window_start = datetime.datetime.fromisoformat(window_start_str)
                window_end = datetime.datetime.fromisoformat(window_end_str)
                
                # Create a window identifier for tracking
                window_id = f"{today_str}_{window_start_str}"
                
                # Skip if we've already triggered this window today
                if self._last_auto_discharge_window == window_id:
                    continue
                
                # Check if we're within the window start +/- 5 minutes
                time_until_start = (window_start - now).total_seconds() / 60
                
                # Trigger if we're within 5 minutes before start or already in the window
                if -5 <= time_until_start <= 0 and not self._discharge_active:
                    _LOGGER.info(
                        "Auto-discharge triggered for window %s - %s (%.3f kWh)",
                        window_start.strftime("%H:%M"),
                        window_end.strftime("%H:%M"),
                        window_energy,
                    )
                    
                    # Track this window as triggered
                    self._last_auto_discharge_window = window_id
                    
                    # Mark discharge as active
                    self.set_discharge_active(
                        True,
                        grid_export=0.0,  # Will be updated by button
                        target_energy=window_energy,
                    )
                    
                    # Call the discharge service
                    try:
                        await self.hass.services.async_call(
                            DOMAIN,
                            SERVICE_START_DISCHARGE,
                        )
                        _LOGGER.info("Auto-discharge service call executed")
                    except Exception as err:
                        _LOGGER.error("Failed to call discharge service: %s", err)
                        self.set_discharge_active(False)
                    
                    break  # Only trigger one window per update
            
            except (ValueError, TypeError) as err:
                _LOGGER.debug("Error parsing window times: %s", err)
                continue

    async def _check_and_trigger_auto_charge(
        self,
        charge_session: list[dict],
    ) -> None:
        """Check if we should auto-trigger charge and call service if needed.
        
        Args:
            charge_session: Next charge session plan with start/end times and energy
        """
        import datetime
        
        if not charge_session or len(charge_session) == 0:
            return
        
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # Reset auto-charge window tracking at midnight
        if self._last_auto_charge_window and today_str not in self._last_auto_charge_window:
            self._last_auto_charge_window = None
        
        # Check each window in the charge session
        for window in charge_session:
            window_start_str = window.get("period_start", "")
            window_end_str = window.get("period_end", "")
            window_energy = window.get("energy_kwh", 0)
            
            if not window_start_str:
                continue
            
            try:
                # Parse window start time
                window_start = datetime.datetime.fromisoformat(window_start_str)
                window_end = datetime.datetime.fromisoformat(window_end_str)
                
                # Create a window identifier for tracking
                window_id = f"{today_str}_{window_start_str}"
                
                # Skip if we've already triggered this window today
                if self._last_auto_charge_window == window_id:
                    continue
                
                # Check if we're within the window start +/- 5 minutes
                time_until_start = (window_start - now).total_seconds() / 60
                
                # Trigger if we're within 5 minutes before start or already in the window
                if -5 <= time_until_start <= 0 and not self._charge_active:
                    _LOGGER.info(
                        "Auto-charge triggered for window %s - %s (%.3f kWh)",
                        window_start.strftime("%H:%M"),
                        window_end.strftime("%H:%M"),
                        window_energy,
                    )
                    
                    # Track this window as triggered
                    self._last_auto_charge_window = window_id
                    
                    # Mark charge as active
                    self.set_charge_active(True)
                    
                    # Call the charge service
                    try:
                        await self.hass.services.async_call(
                            DOMAIN,
                            "start_charge",
                        )
                        _LOGGER.info("Auto-charge service call executed")
                    except Exception as err:
                        _LOGGER.error("Failed to call charge service: %s", err)
                        self.set_charge_active(False)
                    
                    break  # Only trigger one window per update
            
            except (ValueError, TypeError) as err:
                _LOGGER.debug("Error parsing charge window times: %s", err)
                continue
