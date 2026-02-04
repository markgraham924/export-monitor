# Energy Export Monitor

Control your Alpha ESS battery discharge and charging based on Solcast PV forecasts and Carbon Intensity data to optimize grid exports and minimize environmental impact.

## Quick Start

1. Install via HACS
2. Add integration in Settings → Devices & Services
3. Select your Alpha ESS and Solcast entities
4. Configure battery capacity and charge/discharge settings
5. Use buttons, switches, or automations to control discharge

## Features

- **Smart Export Control**: Calculates safe export limits based on PV production and forecasts
- **Carbon Intensity Optimization**: Discharge during high-CI, charge during low-CI periods
- **Auto-Discharge**: Automatic discharge triggering at planned export windows
- **Battery Charge Planning**: Identifies lowest-CI periods for optimal charging
- **Safety Margin**: Keeps exports within 0.5kWh of generated/predicted (whichever is higher)
- **Real-time Monitoring**: Comprehensive sensors for export limits, discharge needs, charge plans, and system status
- **Automation Ready**: Services and switches for full automation control

## Configuration

Required entities:
- Alpha ESS discharge button, power, and cutoff SOC controls
- Battery SOC sensor (e.g., sensor.alphaess_soc_battery)
- Grid power sensor (negative when exporting)
- PV production sensor
- Solcast remaining forecast sensor

New Configuration Options:
- Battery capacity in kWh (required for charge planning)
- Charge window times (start/end)
- Charge power in kW
- Export window constraints for auto-discharge
- Carbon Intensity forecast sensor (optional)

Optional settings:
- Target grid export (default: 0W)
- Minimum battery SOC (default: 20%)
- Safety margin (default: 0.5 kWh)

## Services

- `export_monitor.start_discharge`: Start discharge with calculated power and duration
- `export_monitor.stop_discharge`: Stop discharge immediately
- `export_monitor.calculate_discharge`: Recalculate requirements

## New in v1.8.1

- Fixed diagnostic sensors display (Current SOC, Min SOC, Reserve SOC Target)
- Battery capacity configuration for accurate charge planning
- Charge plan generation for today and tomorrow
- Auto-discharge with time-based window constraints
- Carbon intensity optimization (high-CI discharge, low-CI charge)

[Full Documentation](https://github.com/markgraham924/export-monitor)
