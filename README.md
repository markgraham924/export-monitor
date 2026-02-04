<p align="center">
  <img src="logo@2x.png" alt="Energy Export Monitor" width="256" height="256">
</p>

# Energy Export Monitor for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/markgraham924/export-monitor.svg)](https://github.com/markgraham924/export-monitor/releases)
[![GitHub stars](https://img.shields.io/github/stars/markgraham924/export-monitor.svg)](https://github.com/markgraham924/export-monitor/stargazers)

A Home Assistant custom integration that intelligently controls Alpha ESS battery discharge based on Solcast PV forecasts to keep grid exports within safe limits and comply with energy provider terms and conditions.

## ⚠️ Important Safety Notice

**This is a critical service that controls battery discharge.** Incorrect operation can result in financial penalties from your energy provider if export limits are exceeded. 

### Production Readiness Features (v1.10.0+)

✅ **Comprehensive Error Handling**: All service calls protected with 5-second timeouts  
✅ **Sensor Validation**: All values validated against reasonable ranges  
✅ **Stale Data Detection**: Blocks discharge with outdated sensor data (>30s)  
✅ **Circuit Breaker Protection**: Prevents cascade failures after 5 consecutive errors  
✅ **System Health Monitoring**: 4 diagnostic sensors track system status  
✅ **Persistent Notifications**: Critical failures notify user immediately  
✅ **Emergency Procedures**: Documented recovery and failure scenarios  

**📖 Before deploying to production, read [PRODUCTION_GUIDE.md](PRODUCTION_GUIDE.md)**

This guide covers:
- Pre-deployment checklist
- Monitoring and health checks
- 5 common failure scenarios with resolution steps
- Emergency stop procedures
- Logging and diagnostics
- Compliance and safety considerations

## Features

- **Smart Export Control**: Automatically calculates safe grid export limits based on PV production and forecasts
- **Carbon Intensity Optimization**: Intelligent discharge planning during high-CI periods and charge planning during low-CI periods
- **Auto-Discharge**: Automatic discharge triggering at planned export windows with configurable time constraints
- **Battery Charge Planning**: Identifies lowest carbon intensity periods for optimal battery charging
- **Alpha ESS Integration**: Works with Alpha ESS systems via the Hillview Lodge custom integration
- **Solcast Forecasting**: Uses Solcast PV forecast data to predict production and optimize discharge
- **Safety Margin**: Configurable safety margin (default 500W = 0.5kWh) to stay within T&C limits
- **Automated Services**: Control discharge via services, automations, or manual buttons
- **Real-time Monitoring**: Comprehensive sensors showing export limits, discharge requirements, charge plans, and system status
- **Production-Ready Safety**: Error handling, validation, circuit breakers, and health monitoring

## How It Works

The integration monitors your system every 10 seconds and:

1. **Reads current values**: Battery SOC, PV energy produced today, grid feed today, and Solcast forecast
2. **Calculates export headroom**: `max(pv_energy_today, solcast_total_today) + safety_margin - grid_feed_today`
3. **Calculates discharge duration**: `duration = headroom (kWh) ÷ discharge_power (kW) × 60 minutes`
4. **Controls discharge**: Sets discharge power, duration, and cutoff SOC via Alpha ESS helper entities
5. **Monitors progress**: Tracks discharge to ensure it stays within safe export limits

This keeps your grid export within the safe limit while maximizing self-consumption and preventing breaches of your energy provider's terms and conditions. **Duration scales linearly with available headroom while discharge power remains fixed.**

## Prerequisites

Before installing this integration, you must have:

1. **Home Assistant** 2024.1.0 or later
2. **Alpha ESS System** with [Hillview Lodge Alpha ESS integration](https://projects.hillviewlodge.ie/alphaess/) configured
3. **Solcast PV Forecast** integration installed from HACS
4. **Alpha ESS Helper Entities** configured:
   - `input_boolean.alphaess_helper_force_discharging`
   - `number.alphaess_template_force_discharging_power`
   - `input_number.alphaess_helper_force_discharging_cutoff_soc` (or number entity equivalent)
   - `input_number.alphaess_helper_force_discharging_duration` (optional, for duration control)

### Setting Up Alpha ESS Helper Entities

If you haven't set up the Alpha ESS helper automation, follow the Hillview Lodge guide to create:

```yaml
# configuration.yaml or helpers.yaml
input_boolean:
  alphaess_helper_force_discharging:
    name: Alpha ESS Force Discharging
    icon: mdi:battery-arrow-up

input_number:
  alphaess_template_force_discharging_power:
    name: Alpha ESS Discharge Power Capacity
    min: 0
    max: 10
    step: 0.1
    unit_of_measurement: kW
    icon: mdi:flash
    
  alphaess_helper_force_discharging_cutoff_soc:
    name: Alpha ESS Cutoff SOC
    min: 0
    max: 100
    step: 1
    unit_of_measurement: "%"
    icon: mdi:battery-low
    
  alphaess_helper_force_discharging_duration:
    name: Alpha ESS Discharge Duration
    min: 1
    max: 1440
    step: 1
    unit_of_measurement: min
    icon: mdi:timer
```

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add the repository URL: `https://github.com/markgraham924/export-monitor`
6. Select category: "Integration"
7. Click "Add"
8. Click "Install" on the Energy Export Monitor card
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/markgraham924/export-monitor/releases)
2. Extract the `custom_components/export_monitor` folder
3. Copy it to your Home Assistant `custom_components` directory
4. Restart Home Assistant

## Configuration

### Via UI (Recommended)

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Energy Export Monitor"
4. Follow the setup wizard:

  **Required Entities:**
  - **Alpha ESS Discharge Button**: Select `input_boolean.alphaess_helper_force_discharging`
  - **Alpha ESS Discharge Power Capacity**: Select `number.alphaess_template_force_discharging_power` (set to your max discharge capacity in kW)
  - **Alpha ESS Cutoff SOC**: Select `input_number.alphaess_helper_force_discharging_cutoff_soc`
  - **Current Battery SOC**: Select your Alpha ESS SOC sensor (e.g., `sensor.alphaess_battery_soc`)
  - **Today's PV Energy (kWh)**: `sensor.alphaess_today_s_energy_from_pv`
  - **Today's Grid Feed (kWh)**: `sensor.alphaess_today_s_energy_feed_to_grid_meter`
  - **Solcast Forecast Total Today (kWh)**: `sensor.solcast_pv_forecast_forecast_today`
  - **Solcast Forecast So Far (kWh, optional)**: `sensor.solcast_forecast_so_far`

  **Optional Settings:**
  - **Target Grid Export**: Target maximum export power in watts (default: 0)
  - **Minimum Battery SOC**: Minimum battery level before discharge stops (default: 20%)
  - **Safety Margin**: Additional margin in kWh to prevent T&C breaches (default: 0.5 kWh)
  - **Carbon Intensity Forecast Sensor**: Optional sensor for CI-based planning
  - **Enable CI Planning**: Toggle for carbon intensity discharge planning
  - **Enable Auto-Discharge**: Toggle for automatic discharge at planned windows
  - **Export Window Start/End**: Time constraints for discharge windows (default: 00:00 - 23:59)
  - **Enable Charge Planning**: Toggle for intelligent charge planning
  - **Charge Window Start/End**: Time constraints for charging windows (default: 00:00 - 06:00)
  - **Charge Power**: Charge power in kW (default: 3.68 kW)
  - **Battery Capacity**: Total battery capacity in kWh (default: 10 kWh)

5. Click **Submit**

### Adjusting Settings

To change configuration options after setup:

1. Go to **Settings** → **Devices & Services**
2. Find "Energy Export Monitor"
3. Click **Configure**
4. Adjust target export, minimum SOC, or safety margin
5. Click **Submit**

## Entities Created

After setup, the integration creates the following entities:

### Buttons
- **Start Discharge**: Manually trigger discharge based on current calculations
- **Stop Discharge**: Stop active discharge immediately
- **Calculate Discharge**: Recalculate discharge requirements

### Switches
- **Enable Auto-Discharge**: Toggle automatic discharge at planned export windows

### Numbers
- **Target Export**: Set maximum grid export target (W)
- **Minimum SOC**: Set minimum battery level before discharge stops (%)
- **Safety Margin**: Set safety buffer to prevent T&C breaches (kWh)

### Sensors & Controls

#### Primary Monitoring Sensors
- **Export Headroom** (kWh): Safe export capacity remaining today before exceeding target
- **Discharge Needed** (W): Discharge power required to stay within export limits
- **Discharge Status** (string): Current discharge state (Idle/Needed/Active)
- **Calculated Duration** (minutes): Estimated discharge time based on headroom and discharge power
- **Discharge Complete** (string): Whether discharge target has been reached
- **Exported Today** (kWh): Total energy exported to grid today (cumulative)

#### Reserve SOC Monitoring
- **Reserve SOC Target** (%): Configured minimum battery level reserve
- **Reserve SOC Status** (string): Reserve monitoring state (Normal/Limit Reached/Monitoring Disabled)

#### Carbon Intensity Planning (Optional)
- **Current Carbon Intensity** (gCO2/kWh): Current grid carbon intensity value
- **Current Carbon Intensity Index** (string): CI intensity category (very_low/low/moderate/high)
- **Discharge Plan** (string): Summary of planned discharge windows (count and energy)
- **Discharge Plan Today** (string): Discharge plan for remainder of today
- **Discharge Plan Tomorrow** (string): Full 24-hour discharge plan for tomorrow

#### Plan Detail Sensors
- **Plan Energy Today** (kWh): Total energy from planned discharge today
- **Plan Energy Tomorrow** (kWh): Total energy from planned discharge tomorrow
- **Plan Windows Today** (count): Number of discharge windows available today
- **Plan Windows Tomorrow** (count): Number of discharge windows available tomorrow
- **Plan Windows Total** (count): Total windows across all planned periods
- **Total Plan Energy** (kWh): Combined energy across all planned windows

#### System Health & Monitoring (Diagnostic)
Located in the **Diagnostic** entity category - essential for production monitoring:

- **System Health** (string): Overall system status
  - `Healthy`: All systems operational
  - `Error`: Critical error occurred (check Error State sensor)
  - `Stale Data`: Sensor data too old (>30s)
  - `Circuit Breaker Open`: Too many failures, system paused

- **Error State** (string): Current error condition
  - `none`: No errors
  - `soc_read_failed`: Cannot read battery SOC
  - `stale_data`: Coordinator data too old
  - `discharge_power_set_failed`: Cannot set discharge power
  - `discharge_start_failed`: Cannot start discharge
  - `discharge_stop_failed`: **CRITICAL** - Cannot stop discharge
  - `no_data`: No coordinator data available

- **Data Staleness** (seconds): Age of coordinator data
  - Normal: 0-15s
  - Warning: 15-30s
  - Critical: >30s (discharge blocked)

- **Circuit Breaker Status** (string): Failure protection state
  - `Closed`: Normal operation
  - `Open`: Paused due to repeated failures (auto-resets after 60s)
  - **Attributes**: failure_count, last_failure_time, can_attempt

**⚠️ Monitor these sensors regularly in production!** See [PRODUCTION_GUIDE.md](PRODUCTION_GUIDE.md) for details.

#### Charge Planning Sensors
- **Charge Plan Today** (string): Formatted charge windows for today (HH:MM - HH:MM X.XXkWh)
- **Charge Plan Tomorrow** (string): Formatted charge windows for tomorrow

#### Diagnostic Sensors
Located in the **Diagnostic** entity category:
- **Current PV** (W): Current solar production power
- **Forecast PV Today** (kWh): Expected total solar production for today
- **Current SOC** (%): Current battery state of charge (from configured sensor)
- **Minimum SOC** (%): Configured minimum SOC threshold
- **Export Allowed** (kWh): Calculated maximum export capacity
- **Observe Reserve SOC** (boolean): Whether reserve SOC monitoring is active
- **Reserve Limit Reached** (boolean): Whether battery reserve limit has been breached

## Services

The integration provides three services for automation:

### `export_monitor.start_discharge`

Start battery discharge. Power and duration are calculated automatically based on configured discharge capacity and available export headroom.

```yaml
service: export_monitor.start_discharge
# No parameters required - all calculated automatically
```

**How it works:**
- Reads discharge power capacity from configured entity (e.g., 3.0 kW)
- Calculates available export headroom (e.g., 1.5 kWh)
- Calculates duration: 1.5 kWh ÷ 3.0 kW × 60 = 30 minutes
- Sets discharge power to 3.0 kW for 30 minutes

### `export_monitor.stop_discharge`

Stop battery discharge immediately.

```yaml
service: export_monitor.stop_discharge
```

### `export_monitor.calculate_discharge`

Recalculate discharge requirements based on current conditions.

```yaml
service: export_monitor.calculate_discharge
```

## Automation Examples

### Auto-Start Discharge When Needed

```yaml
automation:
  - alias: "Auto Start Export Control"
    trigger:
      - platform: state
        entity_id: sensor.export_monitor_discharge_status
        to: "Needed"
        for:
          minutes: 2
    condition:
      - condition: numeric_state
        entity_id: sensor.export_monitor_discharge_needed
        above: 500
    action:
      - service: button.press
        target:
          entity_id: button.export_monitor_start_discharge
```

### Stop Discharge at Night

```yaml
automation:
  - alias: "Stop Export Control at Night"
    trigger:
      - platform: sun
        event: sunset
    action:
      - service: export_monitor.stop_discharge
```

### Adjust Safety Margin During Peak Hours

```yaml
automation:
  - alias: "Increase Safety Margin Peak Hours"
    trigger:
      - platform: time
        at: "16:00:00"
    action:
      - service: number.set_value
        target:
          entity_id: number.export_monitor_safety_margin
        data:
          value: 1000
          
  - alias: "Reset Safety Margin Off-Peak"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: number.set_value
        target:
          entity_id: number.export_monitor_safety_margin
        data:
          value: 500
```

## Dashboard Card Examples

### Primary Monitoring Card

```yaml
type: entities
title: Energy Export Monitor
entities:
  - entity: sensor.export_monitor_discharge_status
    name: Status
  - entity: sensor.export_monitor_export_headroom
    name: Safe Export Capacity
  - entity: sensor.export_monitor_discharge_needed
    name: Discharge Needed
  - entity: sensor.export_monitor_calculated_duration
    name: Duration Available
  - entity: sensor.export_monitor_exported_today
    name: Exported Today
  - entity: button.export_monitor_start_discharge
  - entity: button.export_monitor_stop_discharge
```

### Carbon Intensity Planning Card

```yaml
type: entities
title: Carbon Intensity Planning
entities:
  - entity: sensor.export_monitor_current_carbon_intensity
    name: Current CI
  - entity: sensor.export_monitor_current_carbon_intensity_index
    name: Intensity Level
  - entity: sensor.export_monitor_discharge_plan_today
    name: Plan (Today)
  - entity: sensor.export_monitor_plan_energy_today
    name: Energy Today
  - entity: sensor.export_monitor_plan_windows_today
    name: Windows Today
  - entity: sensor.export_monitor_discharge_plan_tomorrow
    name: Plan (Tomorrow)
  - entity: sensor.export_monitor_plan_energy_tomorrow
    name: Energy Tomorrow
  - entity: sensor.export_monitor_plan_windows_tomorrow
    name: Windows Tomorrow
```

### Custom Dashboard Card

For a beautiful, integrated 36-hour timeline view of your charge and discharge plans, install the **Export Monitor Card** custom card:

#### Installation via HACS

1. Open HACS → Frontend → Custom repositories
2. Add: `https://github.com/markgraham924/export-monitor-card`
3. Search for "Export Monitor Card" and install
4. Restart Home Assistant

#### Using in Dashboard

```yaml
type: custom:export-monitor-card
charge_session_entity: sensor.energy_export_monitor_next_charge_session
discharge_today_entity: sensor.energy_export_monitor_discharge_plan_today
discharge_tomorrow_entity: sensor.energy_export_monitor_discharge_plan_tomorrow
ci_entity: sensor.energy_export_monitor_current_carbon_intensity
soc_entity: sensor.alphaess_battery_soc
pv_entity: sensor.energy_export_monitor_current_pv
headroom_entity: sensor.energy_export_monitor_export_headroom
```

#### Card Features

- 📊 **36-Hour Timeline**: Visual timeline of all charge (green) and discharge (red) windows
- ⚡ **Energy Visualization**: Color-coded bars showing kWh allocation per window
- 🌍 **Carbon Intensity**: CI values displayed for each charge window
- 📈 **Summary Stats**: Total charge/discharge energy, current PV, battery SOC
- 🎨 **Responsive Design**: Works on mobile, tablet, and desktop with dark/light mode support
- 📱 **Interactive**: Hover effects and smooth animations for better UX

See [Export Monitor Card Repository](https://github.com/markgraham924/export-monitor-card) for full documentation.

### Configuration Card

```yaml
type: entities
title: Energy Export Monitor Settings
entities:
  - entity: number.export_monitor_target_export
  - entity: number.export_monitor_minimum_soc
  - entity: number.export_monitor_safety_margin
  - entity: sensor.export_monitor_reserve_soc_status
    name: Reserve SOC Status
  - entity: sensor.export_monitor_reserve_soc_target
    name: Reserve SOC Target
  - entity: button.export_monitor_calculate_discharge
```

## How the Calculation Works

### Export Headroom Formula (Energy-Based)

```
export_cap_kwh = max(pv_energy_today_kwh, solcast_total_today_kwh) + safety_margin_kwh
export_headroom_kwh = export_cap_kwh - grid_feed_today_kwh
```

### Discharge Duration Calculation

The integration uses a **fixed discharge power** (set by user) and **calculates duration** based on available headroom:

```
duration_hours = export_headroom_kwh ÷ discharge_power_kw
duration_minutes = duration_hours × 60
```

**Example:**
- Export headroom: 1.5 kWh
- Discharge power capacity: 3.0 kW (configured by user)
- Calculated duration: 1.5 ÷ 3.0 × 60 = **30 minutes**

The battery will discharge at 3.0 kW for 30 minutes to consume the 1.5 kWh of available headroom. **Duration scales linearly with headroom while power remains constant.**

The headroom keeps exported energy within 0.5kWh (default safety margin) of the higher of actual or forecast PV for the day.

## Troubleshooting

### Entities Not Found

Ensure all required entities exist and are available:
- Check Alpha ESS integration is properly configured
- Verify Solcast integration is installed and has recent data
- Confirm helper entities are created in Configuration → Helpers

### Discharge Not Starting

Check the following:
- Battery SOC is above minimum level (default 20%)
- Grid export is actually exceeding the safe limit
- Alpha ESS system is not controlled by VPP (Virtual Power Plant)
- Check Home Assistant logs for errors

### Inaccurate Calculations

- Verify grid power sensor reports negative values when exporting
- Check Solcast forecast is updating regularly
- Ensure PV production sensor includes all arrays
- Review safety margin setting (500W = 0.5kWh over 1 hour)

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.export_monitor: debug
```

## Known Limitations

- **Alpha ESS Specific**: Currently only works with Alpha ESS systems using the Hillview Lodge integration
- **Solcast Required**: Requires Solcast PV Forecast integration
- **No VPP Override**: Cannot override Virtual Power Plant control if active
- **10-Second Polling**: Updates every 10 seconds (not real-time)
- **Fixed Power**: Discharge power is fixed; duration varies based on headroom
- **Country Limitations**: Some Alpha ESS features vary by country

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

- **Issues**: [GitHub Issues](https://github.com/markgraham924/export-monitor/issues)
- **Discussions**: [GitHub Discussions](https://github.com/markgraham924/export-monitor/discussions)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Hillview Lodge Alpha ESS Integration](https://projects.hillviewlodge.ie/alphaess/) for Alpha ESS Modbus integration
- [Solcast PV Forecast](https://github.com/BJReplay/ha-solcast-solar) for solar forecasting
- Home Assistant community for feedback and testing

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for full version history.

### Recent Versions

**1.10.0** (2026-02-04) - **Production Readiness Update**
- ✅ Added comprehensive error handling with 5-second timeouts for all service calls
- ✅ Implemented sensor value validation with reasonable ranges (SOC: 0-100%, Energy: 0-1000kWh)
- ✅ Added stale data detection (blocks discharge when data >30s old)
- ✅ Implemented circuit breaker pattern (opens after 5 failures, auto-resets after 60s)
- ✅ Created 4 system health diagnostic sensors (System Health, Error State, Data Staleness, Circuit Breaker)
- ✅ Added persistent notifications for critical failures with recovery guidance
- ✅ Created comprehensive [PRODUCTION_GUIDE.md](PRODUCTION_GUIDE.md) (500+ lines)
- ✅ CodeQL security scan passed (0 vulnerabilities)
- 📖 See [PRODUCTION_GUIDE.md](PRODUCTION_GUIDE.md) for deployment best practices

**1.8.1** (2026-02-04)
- Fixed diagnostic sensors (Current SOC, Min SOC, Reserve SOC Target) showing Unknown

**1.8.0** (2026-02-04)
- Added battery capacity configuration for accurate charge planning
- Energy calculations now use explicit battery capacity (0.5-100 kWh)

**1.7.0** (2026-02-04)
- Added battery charge planning with lowest-CI optimization
- Charge plan sensors for today/tomorrow
- Charge window and power configuration

**1.6.0** (2026-02-04)
- Added auto-discharge feature with export window constraints
- Fixed CI prioritization (high-CI for discharge, low-CI for charge)

**1.0.0** (2026-01-27)
- Initial release
