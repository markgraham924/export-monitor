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
CONF_SOLCAST_TOMORROW: Final = "solcast_tomorrow"  # Optional - for tomorrow's plan
CONF_TARGET_EXPORT: Final = "target_export"
CONF_MIN_SOC: Final = "min_soc"
CONF_SAFETY_MARGIN: Final = "safety_margin"
CONF_RESERVE_SOC_SENSOR: Final = "reserve_soc_sensor"  # Optional
CONF_OBSERVE_RESERVE_SOC: Final = "observe_reserve_soc"  # Boolean
CONF_CI_FORECAST_SENSOR: Final = "ci_forecast_sensor"  # Optional - Carbon Intensity
CONF_ENABLE_CI_PLANNING: Final = "enable_ci_planning"  # Boolean
CONF_ENABLE_AUTO_DISCHARGE: Final = "enable_auto_discharge"  # Boolean
CONF_EXPORT_WINDOW_START: Final = "export_window_start"  # Time (HH:MM)
CONF_EXPORT_WINDOW_END: Final = "export_window_end"  # Time (HH:MM)
CONF_ENABLE_CHARGE_PLANNING: Final = "enable_charge_planning"  # Boolean
CONF_CHARGE_WINDOW_START: Final = "charge_window_start"  # Time (HH:MM)
CONF_CHARGE_WINDOW_END: Final = "charge_window_end"  # Time (HH:MM)
CONF_CHARGE_POWER_KW: Final = "charge_power_kw"  # Charge power in kW
CONF_BATTERY_CAPACITY_KWH: Final = "battery_capacity_kwh"  # Battery capacity in kWh

# Service names
SERVICE_START_DISCHARGE: Final = "start_discharge"
SERVICE_STOP_DISCHARGE: Final = "stop_discharge"
SERVICE_CALCULATE_DISCHARGE: Final = "calculate_discharge"
SERVICE_EXECUTE_DISCHARGE_PLAN: Final = "execute_discharge_plan"

# Default values
DEFAULT_TARGET_EXPORT: Final = 0  # Watts
DEFAULT_OBSERVE_RESERVE_SOC: Final = False  # Disabled by default
DEFAULT_ENABLE_CI_PLANNING: Final = False  # Disabled by default
DEFAULT_ENABLE_AUTO_DISCHARGE: Final = False  # Disabled by default
DEFAULT_EXPORT_WINDOW_START: Final = "00:00"  # Full day by default
DEFAULT_EXPORT_WINDOW_END: Final = "23:59"  # Full day by default
DEFAULT_ENABLE_CHARGE_PLANNING: Final = False  # Disabled by default
DEFAULT_CHARGE_WINDOW_START: Final = "00:00"  # Full day by default
DEFAULT_CHARGE_WINDOW_END: Final = "06:00"  # Overnight charging by default
DEFAULT_CHARGE_POWER_KW: Final = 3.68  # Default charge power in kW
DEFAULT_BATTERY_CAPACITY_KWH: Final = 10.0  # Default battery capacity in kWh
DEFAULT_MIN_SOC: Final = 20  # Percent
DEFAULT_SAFETY_MARGIN: Final = 0.5  # kWh (0.5 kWh margin)
DEFAULT_SCAN_INTERVAL: Final = 10  # Seconds

# Attributes
ATTR_EXPORT_HEADROOM: Final = "export_headroom_kwh"
ATTR_EXPORT_ALLOWED: Final = "export_allowed_kwh"
ATTR_EXPORTED_TODAY: Final = "exported_today_kwh"
ATTR_DISCHARGE_NEEDED: Final = "discharge_needed"
ATTR_CURRENT_PV: Final = "current_pv_kwh"
ATTR_FORECAST_PV: Final = "forecast_pv_kwh"
ATTR_LAST_CALCULATION: Final = "last_calculation"
ATTR_DISCHARGE_PLAN: Final = "discharge_plan"
ATTR_DISCHARGE_PLAN_TODAY: Final = "discharge_plan_today"
ATTR_DISCHARGE_PLAN_TOMORROW: Final = "discharge_plan_tomorrow"
ATTR_CHARGE_PLAN_TODAY: Final = "charge_plan_today"
ATTR_CHARGE_PLAN_TOMORROW: Final = "charge_plan_tomorrow"
ATTR_CURRENT_CI_INDEX: Final = "current_ci_index"
ATTR_CURRENT_CI_VALUE: Final = "current_ci_value"
