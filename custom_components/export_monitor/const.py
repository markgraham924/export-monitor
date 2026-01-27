"""Constants for Energy Export Monitor integration."""
from typing import Final

DOMAIN: Final = "export_monitor"

# Configuration keys
CONF_DISCHARGE_BUTTON: Final = "discharge_button"
CONF_DISCHARGE_POWER: Final = "discharge_power"
CONF_DISCHARGE_CUTOFF_SOC: Final = "discharge_cutoff_soc"
CONF_CURRENT_SOC: Final = "current_soc"
CONF_PV_ENERGY_TODAY: Final = "pv_energy_today"
CONF_GRID_FEED_TODAY: Final = "grid_feed_today"
CONF_SOLCAST_TOTAL_TODAY: Final = "solcast_total_today"
CONF_SOLCAST_FORECAST_SO_FAR: Final = "solcast_forecast_so_far"
CONF_TARGET_EXPORT: Final = "target_export"
CONF_MIN_SOC: Final = "min_soc"
CONF_SAFETY_MARGIN: Final = "safety_margin"
CONF_RESERVE_SOC_SENSOR: Final = "reserve_soc_sensor"  # Optional
CONF_OBSERVE_RESERVE_SOC: Final = "observe_reserve_soc"  # Boolean

# Service names
SERVICE_START_DISCHARGE: Final = "start_discharge"
SERVICE_STOP_DISCHARGE: Final = "stop_discharge"
SERVICE_CALCULATE_DISCHARGE: Final = "calculate_discharge"

# Default values
DEFAULT_TARGET_EXPORT: Final = 0  # Watts
DEFAULT_OBSERVE_RESERVE_SOC: Final = False  # Disabled by default
DEFAULT_MIN_SOC: Final = 20  # Percent
DEFAULT_SAFETY_MARGIN: Final = 0.5  # kWh (0.5 kWh margin)
DEFAULT_SCAN_INTERVAL: Final = 30  # Seconds

# Attributes
ATTR_EXPORT_HEADROOM: Final = "export_headroom_kwh"
ATTR_EXPORT_ALLOWED: Final = "export_allowed_kwh"
ATTR_EXPORTED_TODAY: Final = "exported_today_kwh"
ATTR_DISCHARGE_NEEDED: Final = "discharge_needed"
ATTR_CURRENT_PV: Final = "current_pv_kwh"
ATTR_FORECAST_PV: Final = "forecast_pv_kwh"
ATTR_LAST_CALCULATION: Final = "last_calculation"
