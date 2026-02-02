# Energy Export Monitor

Control your Alpha ESS battery discharge based on Solcast PV forecasts to keep grid exports within safe limits.

## Quick Start

1. Install via HACS
2. Add integration in Settings → Devices & Services
3. Select your Alpha ESS and Solcast entities
4. Use buttons or automations to control discharge

## Features

- **Smart Export Control**: Calculates safe export limits based on PV production and forecasts
- **Safety Margin**: Keeps exports within 0.5kWh of generated/predicted (whichever is higher)
- **Real-time Monitoring**: Sensors show safe limits, discharge needs, and system status
- **Automation Ready**: Services for full automation control

## Configuration

Required entities:
- Alpha ESS discharge button, power, and cutoff SOC controls
- Battery SOC sensor
- Grid power sensor (negative when exporting)
- PV production sensor
- Solcast remaining forecast sensor

Optional settings:
- Target grid export (default: 0W)
- Minimum battery SOC (default: 20%)
- Safety margin (default: 500W)

## Services

- `export_monitor.start_discharge`: Start discharge with specified power
- `export_monitor.stop_discharge`: Stop discharge immediately
- `export_monitor.calculate_discharge`: Recalculate requirements

[Full Documentation](https://github.com/markgraham924/export-monitor)
