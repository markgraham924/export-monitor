# Agent Instructions for Energy Export Monitor

This document provides guidance for AI coding assistants working on this project.

## Project Overview

**Energy Export Monitor** is a Home Assistant custom integration that intelligently controls Alpha ESS battery discharge based on Solcast PV forecasts to keep grid exports within safe limits and comply with energy provider terms and conditions.

**Domain**: `export_monitor`  
**Type**: Custom Component  
**Platform**: Home Assistant  
**Current Version**: See `custom_components/export_monitor/manifest.json`

## Architecture

### Component Structure

```
custom_components/export_monitor/
├── __init__.py          # Integration setup, coordinator initialization
├── config_flow.py       # Configuration UI flow
├── coordinator.py       # DataUpdateCoordinator for polling/updates
├── const.py            # Constants and configuration keys
├── sensor.py           # Sensor entities (export headroom, status)
├── button.py           # Button entities (manual discharge control)
├── number.py           # Number entities (configurable parameters)
├── services.yaml       # Service definitions
├── strings.json        # UI strings and translations
└── manifest.json       # Integration metadata and version
```

### Key Concepts

1. **Export Monitoring**: Tracks grid export to prevent exceeding limits
2. **PV Forecasting**: Uses Solcast data to predict future production
3. **Battery Control**: Manages Alpha ESS discharge via helper entities
4. **Safety Margin**: Configurable buffer (default 0.5kWh) for safe operation
5. **Polling**: Updates every 10 seconds via DataUpdateCoordinator

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
- Required sensors: SOC, PV production, grid feed, Solcast forecasts
- Control entities: discharge button, power, cutoff SOC
- Parameters: target export, min SOC, safety margin
- Optional: reserve SOC sensor and observe flag

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

- **MAJOR** (X.0.0): Breaking changes requiring reconfiguration
- **MINOR** (0.X.0): New backward-compatible features
- **PATCH** (0.0.X): Bug fixes and improvements

### Adding New Features

1. **New Sensors**: Add to `sensor.py`
   - Inherit from `ExportMonitorEntity`
   - Define `unique_id`, `name`, `native_value`
   - Add to platform setup in `async_setup_entry`

2. **New Services**: 
   - Define in `services.yaml`
   - Implement handler in `__init__.py`
   - Register in `async_setup_entry`

3. **New Configuration Options**:
   - Add constant to `const.py`
   - Update config flow in `config_flow.py`
   - Handle in coordinator initialization

4. **New Calculations**:
   - Add to `coordinator.py` in `_async_update_data`
   - Make available via coordinator.data
   - Expose via sensor entities

### Testing Checklist

- [ ] Integration loads without errors in HA
- [ ] Configuration flow works (initial setup + reconfigure)
- [ ] All sensors update correctly
- [ ] Services execute as expected
- [ ] Handles missing/unavailable entities gracefully
- [ ] Logs are clear and helpful (not spammy)
- [ ] No breaking changes (or version bumped to MAJOR)

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

- **README.md**: User documentation, installation, setup
- **CHANGELOG.md**: Version history and changes
- **VERSIONING.md**: Semantic versioning guide and workflow
- **manifest.json**: Integration metadata (version, domain, requirements)
- **const.py**: All constants and configuration keys
- **coordinator.py**: Core logic and calculations

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

1. Add constant to `const.py`
2. Update config schema in `config_flow.py` (both initial and reconfigure)
3. Use in coordinator or entity logic
4. Update version (MINOR if optional, MAJOR if required)
5. Update README.md with new option

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

- **Repository**: https://github.com/markg/export-monitor
- **Issues**: https://github.com/markg/export-monitor/issues
- **Code Owner**: @markg

---

**Remember**: When in doubt, prefer smaller, focused changes. Test thoroughly before committing. Update documentation for user-facing changes.
