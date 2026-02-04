# Smart CI-Based Battery Charging Implementation

## Summary

This implementation adds intelligent battery charging functionality to the Energy Export Monitor integration. The system automatically charges the battery during the lowest carbon intensity (CI) periods within user-defined charging windows, always targeting 100% SOC.

## Key Features

### 1. Automatic Charge Control
- **Auto-Charge Switch**: Enable/disable automatic charging via `switch.export_monitor_enable_auto_charge`
- **CI-Based Planning**: Charges during lowest CI periods to minimize carbon footprint
- **Configurable Windows**: User-defined charge windows (default: 00:00-06:00)
- **Target SOC**: Always charges to 100% for maximum battery capacity

### 2. Prevents Grid Draw During Charging
When force charging is enabled:
- Battery will NOT discharge to the house
- Prevents unwanted grid draw during charge periods
- Maintains battery charge exclusively from grid

### 3. Configuration
Four new required entities for charge control:
- `input_boolean.alphaess_helper_force_charging` - Charge toggle
- `number.alphaess_template_force_charging_power` - Charge power (kW)
- `input_number.alphaess_helper_force_charging_duration` - Duration (min)
- `input_number.alphaess_helper_force_charging_cutoff_soc` - Target SOC (%)

### 4. Services
Two new services for manual control:
- `export_monitor.start_charge` - Start charging using next charge session plan
- `export_monitor.stop_charge` - Stop active charging

## Implementation Details

### Files Modified
1. **const.py** - Added charge control constants and service names
2. **config_flow.py** - Added charge entity configuration to setup wizard
3. **coordinator.py** - Added charge logic and auto-trigger functionality
4. **switch.py** - Added EnableAutoChargeSwitch entity
5. **__init__.py** - Added charge service handlers
6. **services.yaml** - Added service definitions
7. **README.md** - Updated documentation

### Code Architecture

#### Charge State Tracking
```python
self._charge_active = False
self._charge_start_time = None
self._last_auto_charge_window = None
```

#### Auto-Charge Trigger Logic
- Monitors `next_charge_session` sensor every 10 seconds
- Triggers up to 5 minutes before charge window starts
- Prevents duplicate triggers per window
- Automatically sets power, duration, and SOC

#### Charge Execution Flow
1. Check if within 5 minutes before charge window starts (0 to 5 minutes)
2. Calculate total power from total energy across all windows / total duration
3. Set charge power via configured entity
4. Set total duration from all charge windows
5. Set cutoff SOC to 100%
6. Enable force charging button
7. Track charge state

## Testing

### Test Coverage
- **88 total tests** (all passing)
- **6 new auto-charge tests** added:
  - Charge window identifier format
  - Charge window timing calculation
  - Charge trigger window range
  - Charge session energy calculation
  - Charge duration from window
  - Charge power calculation

### Test Results
```
✅ 88 passed in 0.10s
✅ All Python files compile successfully
```

## Usage Examples

### Enable Auto-Charge
```yaml
service: switch.turn_on
target:
  entity_id: switch.export_monitor_enable_auto_charge
```

### Manual Charge Start
```yaml
service: export_monitor.start_charge
```

### Automation: Charge on Low SOC
```yaml
automation:
  - alias: "Auto Charge Low Battery"
    trigger:
      - platform: numeric_state
        entity_id: sensor.alphaess_battery_soc
        below: 20
    condition:
      - condition: time
        after: "00:00:00"
        before: "06:00:00"
    action:
      - service: export_monitor.start_charge
```

## Benefits

1. **Carbon Reduction**: Charges during greenest grid periods
2. **Cost Optimization**: Aligns with low-rate periods (typically low-CI)
3. **Battery Health**: Maintains optimal charge patterns
4. **Flexibility**: User controls windows and auto-charge toggle
5. **Integration**: Works seamlessly with existing discharge planning

## Next Steps

Users should:
1. Create the 4 required charging helper entities
2. Configure entities during integration setup
3. Enable CI planning for optimal charge windows
4. Enable auto-charge switch when ready
5. Monitor charge sessions via `sensor.energy_export_monitor_next_charge_session`

## Compatibility

- Home Assistant 2024.1.0+
- Alpha ESS systems via Hillview Lodge integration
- Requires CI forecast sensor for optimal planning
- Works with existing discharge control features

---

**Implementation Date**: 2026-02-04
**Version**: Adds to existing v1.8.1+
**Tests**: 88 passing (6 new)
**Status**: Complete ✅
