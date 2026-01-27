"""Constants for Energy Export Monitor integration."""
from typing import Final

DOMAIN: Final = "export_monitor"

# Configuration keys
CONF_DISCHARGE_BUTTON: Final = "discharge_button"
CONF_DISCHARGE_POWER: Final = "discharge_power"
CONF_DISCHARGE_CUTOFF_SOC: Final = "discharge_cutoff_soc"
CONF_CURRENT_SOC: Final = "current_soc"
CONF_GRID_POWER: Final = "grid_power"
CONF_CURRENT_PV: Final = "current_pv"
CONF_SOLCAST_REMAINING: Final = "solcast_remaining"
CONF_TARGET_EXPORT: Final = "target_export"
CONF_MIN_SOC: Final = "min_soc"
CONF_SAFETY_MARGIN: Final = "safety_margin"

# Service names
SERVICE_START_DISCHARGE: Final = "start_discharge"
SERVICE_STOP_DISCHARGE: Final = "stop_discharge"
SERVICE_CALCULATE_DISCHARGE: Final = "calculate_discharge"

# Default values
DEFAULT_TARGET_EXPORT: Final = 0  # Watts
DEFAULT_MIN_SOC: Final = 20  # Percent
DEFAULT_SAFETY_MARGIN: Final = 500  # Watts (0.5 kWh over 1 hour)
DEFAULT_SCAN_INTERVAL: Final = 30  # Seconds

# Attributes
ATTR_CURRENT_THRESHOLD: Final = "current_threshold"
ATTR_GRID_EXPORT: Final = "grid_export"
ATTR_DISCHARGE_NEEDED: Final = "discharge_needed"
ATTR_SAFE_EXPORT_LIMIT: Final = "safe_export_limit"
ATTR_CURRENT_PV: Final = "current_pv"
ATTR_FORECAST_PV: Final = "forecast_pv"
ATTR_LAST_CALCULATION: Final = "last_calculation"
