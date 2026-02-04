# Agent Instructions for Energy Export Monitor

This document provides guidance for AI coding assistants working on this project.

## Project Overview

**Energy Export Monitor** is a Home Assistant custom integration that intelligently controls Alpha ESS battery discharge and charging based on Solcast PV forecasts and Carbon Intensity data to optimize grid exports, minimize environmental impact, and comply with energy provider terms and conditions.

**Domain**: `export_monitor`  
**Type**: Custom Component  
**Platform**: Home Assistant  
**Current Version**: v1.8.1 (see `custom_components/export_monitor/manifest.json`)

## Architecture

### Component Structure

```
custom_components/export_monitor/
├── __init__.py          # Integration setup, coordinator initialization, service handlers
├── config_flow.py       # Configuration UI flow (user, reconfigure, options)
├── coordinator.py       # DataUpdateCoordinator for polling/updates, plan generation
├── const.py            # Constants and configuration keys
├── sensor.py           # Sensor entities (export headroom, status, charge plans, CI data)
├── button.py           # Button entities (manual discharge control)
├── number.py           # Number entities (configurable parameters)
├── switch.py           # Switch entities (auto-discharge toggle)
├── services.yaml       # Service definitions
├── strings.json        # UI strings and translations
└── manifest.json       # Integration metadata and version
```

### Key Concepts

1. **Export Monitoring**: Tracks grid export to prevent exceeding limits
2. **PV Forecasting**: Uses Solcast data to predict future production
3. **Battery Control**: Manages Alpha ESS discharge via helper entities
4. **Carbon Intensity Optimization**: 
   - **Discharge**: Prioritizes HIGH-CI periods (when grid is dirtiest) to help grid during peak carbon times
   - **Charge**: Prioritizes LOW-CI periods (cleanest grid) to minimize carbon impact during charging
5. **Auto-Discharge**: Automatic discharge triggering at planned export windows with time constraints
6. **Charge Planning**: Identifies lowest-CI periods within charge window for optimal battery charging
7. **Battery Capacity**: Explicit configuration for accurate energy calculations
8. **Safety Margin**: Configurable buffer (default 0.5kWh) for safe operation
9. **Polling**: Updates every 10 seconds via DataUpdateCoordinator

## Development Guidelines

### Code Style

- Follow Home Assistant coding standards
- Use type hints throughout
- Keep functions focused and testable
- Use `Final` for constants in `const.py`
- Prefer async/await over callbacks

### Key Dependencies

This integration depends on external entities provided by:
- **Alpha ESS (Hillview Lodge)**: Battery control helpers
  - `input_boolean.alphaess_helper_force_discharging`
  - `number.alphaess_template_force_discharging_power`
  - `number.alphaess_template_discharging_cutoff_soc`
- **Solcast**: PV forecast sensors
  - `sensor.solcast_pv_forecast_forecast_today`
  - `sensor.solcast_pv_forecast_forecast_so_far`

### Configuration Keys

All configuration keys are defined in `const.py`:
- **Required sensors**: SOC, PV production, grid feed, Solcast forecasts
- **Control entities**: discharge button, power, cutoff SOC
- **Parameters**: target export, min SOC, safety margin
- **Optional CI Planning**: Carbon Intensity forecast sensor, enable CI planning flag
- **Auto-Discharge**: Enable flag, export window start/end times
- **Charge Planning**: Enable flag, charge window start/end times, charge power kW, battery capacity kWh
- **Optional**: reserve SOC sensor and observe flag

### State Management

The integration uses a `DataUpdateCoordinator` pattern:
- `coordinator.py` handles polling and state updates
- All platforms (sensor, button, number) inherit from `CoordinatorEntity`
- State updates trigger entity refreshes automatically

## Making Changes

### Before You Start

1. Read [VERSIONING.md](VERSIONING.md) to understand version numbering
2. Check existing issues/PRs to avoid duplicate work
3. Test changes on local HA instance (192.168.0.202)

### Version Updates

**Always update version in `manifest.json` when making changes:**

- **MAJOR** (X.0.0): Breaking changes requiring reconfiguration or migration
- **MINOR** (0.X.0): New backward-compatible features (new sensors, switches, planning features)
- **PATCH** (0.0.X): Bug fixes, state class corrections, diagnostic improvements

**Recent Version History:**
- v1.8.1: Fixed diagnostic sensor display
- v1.8.0: Added battery capacity configuration
- v1.7.5-v1.7.3: Charge planning bug fixes
- v1.7.0: Battery charge planning with low-CI optimization
- v1.6.0: Auto-discharge feature with export windows

### Adding New Features

1. **New Sensors**: Add to `sensor.py`
   - Inherit from `ExportMonitorSensor` and `CoordinatorEntity`
   - Define `unique_id`, `name`, `native_value`, optional `device_class` and `state_class`
   - For energy sensors: Use `device_class=SensorDeviceClass.ENERGY` without `state_class` or with `TOTAL_INCREASING`
   - Add to platform setup in `async_setup_entry`
   - Expose data via `coordinator.data` dictionary

2. **New Switches**: Add to `switch.py`
   - Inherit from `ExportMonitorSwitch` and `CoordinatorEntity`
   - Implement `is_on`, `async_turn_on`, and `async_turn_off` methods
   - Update config entry and reload integration on state change

3. **New Services**: 
   - Define in `services.yaml`
   - Implement handler in `__init__.py`
   - Register in `async_setup_entry`

4. **New Configuration Options**:
   - Add constant to `const.py` (CONF_ prefix)
   - Add default value to `const.py` (DEFAULT_ prefix)
   - Update config schema in `config_flow.py` (all three steps: user, reconfigure, options)
   - Handle in coordinator initialization or `_async_update_data`

5. **New Calculations or Planning Logic**:
   - Add methods to `coordinator.py`
   - Make data available via `coordinator.data` dictionary return
   - Expose via sensor entities for UI visibility

### Testing Checklist

- [ ] Integration loads without errors in HA
- [ ] Configuration flow works (initial setup + reconfigure + options)
- [ ] All sensors update correctly and show expected values
- [ ] Switches toggle correctly and persist state
- [ ] Services execute as expected
- [ ] Charge planning generates valid plans with battery capacity
- [ ] Auto-discharge triggers at correct window times
- [ ] CI planning prioritizes correctly (high-CI discharge, low-CI charge)
- [ ] Diagnostic sensors display current_soc, min_soc, reserve_soc_target
- [ ] Handles missing/unavailable entities gracefully
- [ ] Logs are clear and helpful (not spammy)
- [ ] State class warnings resolved (energy sensors use proper state_class)
- [ ] No breaking changes (or version bumped to MAJOR)
- [ ] All 78+ unit tests pass

### Common Patterns

**Entity State Access**:
```python
# Via hass.states
state = self.hass.states.get("sensor.example")
if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
    value = float(state.state)
```

**Entity Control**:
```python
# Via service calls
await self.hass.services.async_call(
    "input_boolean",
    "turn_on",
    {"entity_id": "input_boolean.example"},
    blocking=True,
)
```

**Coordinator Updates**:
```python
# Force coordinator refresh
await self.coordinator.async_request_refresh()

# Access coordinator data
value = self.coordinator.data.get("key")
```

## Deployment Process

### Local Development

1. Edit code in this workspace
2. Update version in `manifest.json`
3. Test on local HA instance

### Git Workflow

Use the provided script for commits:

```powershell
.\sync-and-tag.ps1 -Message "Your commit message"
```

This creates a feature branch and pushes to GitHub.

### Release via Pull Request

1. Script pushes feature branch to GitHub
2. Create PR via GitHub CLI or web interface
3. Review changes and merge to main
4. GitHub Actions handles release (if configured)

See [VERSIONING.md](VERSIONING.md) for detailed workflow.

## Important Files

- **README.md**: User documentation, installation, setup, features, configuration, services
- **CHANGELOG.md**: Version history and changes (v1.8.1 current)
- **VERSIONING.md**: Semantic versioning guide and workflow
- **AGENT_INSTRUCTIONS.md**: This file - guidance for AI assistants
- **IMPLEMENTATION_SUMMARY.md**: Historical implementation notes
- **manifest.json**: Integration metadata (version, domain, requirements)
- **const.py**: All constants, configuration keys, and defaults
- **coordinator.py**: Core logic, calculations, charge/discharge plan generation
- **config_flow.py**: UI configuration (user, reconfigure, options flows)
- **sensor.py**: All sensor entities (export, discharge, charge plans, CI, diagnostics)
- **switch.py**: Switch entities (auto-discharge toggle)
- **button.py**: Button entities (start/stop discharge, calculate)
- **number.py**: Number entities (target export, min SOC, safety margin)

## Common Tasks

### Adding a New Sensor

1. Open `sensor.py`
2. Create class inheriting from `ExportMonitorEntity` and `SensorEntity`
3. Define required properties (`unique_id`, `name`, etc.)
4. Add to `SENSOR_TYPES` or platform setup
5. Update version (MINOR)

### Fixing a Calculation Bug

1. Locate calculation in `coordinator.py`
2. Fix the logic/formula
3. Update version (PATCH)
4. Document fix in commit message

### Adding a Configuration Option

1. Add constant to `const.py` with `CONF_` prefix
2. Add default value to `const.py` with `DEFAULT_` prefix
3. Update config schema in `config_flow.py` in all three methods:
   - `async_step_user()` - initial setup
   - `async_step_reconfigure()` - reconfiguration
   - `OptionsFlowHandler.async_step_init()` - options flow
4. Use in coordinator or entity logic via `config_data.get(CONF_KEY, DEFAULT_KEY)`
5. Update version (MINOR if optional, MAJOR if required)
6. Update README.md with new option documentation
7. Add to CHANGELOG.md

Example: Adding battery capacity (v1.8.0)
- Added `CONF_BATTERY_CAPACITY_KWH` and `DEFAULT_BATTERY_CAPACITY_KWH` 
- Added NumberSelector in all three config flows
- Used in charge plan methods for energy calculations
- Documented in README and CHANGELOG

### Handling Missing Entities

Always check for `STATE_UNAVAILABLE` and `STATE_UNKNOWN`:

```python
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

state = self.hass.states.get(entity_id)
if not state or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
    _LOGGER.warning("Entity %s is unavailable", entity_id)
    return None
```

## Debugging Tips

- Use `_LOGGER.debug()` for frequent updates
- Use `_LOGGER.info()` for important state changes
- Use `_LOGGER.warning()` for recoverable issues
- Use `_LOGGER.error()` for critical problems
- Check Home Assistant logs: Settings → System → Logs
- Enable debug logging: `logger: custom_components.export_monitor: debug`

## Resources

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Integration Setup](https://developers.home-assistant.io/docs/integration_setup_failures)
- [Entity Platform](https://developers.home-assistant.io/docs/core/entity)
- [Config Flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler)
- [Coordinator Pattern](https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities)

## Contact

- **Repository**: https://github.com/markgraham924/export-monitor
- **Issues**: https://github.com/markgraham924/export-monitor/issues
- **Code Owner**: @markgraham924

---

**Remember**: When in doubt, prefer smaller, focused changes. Test thoroughly before committing. Update documentation for user-facing changes.
