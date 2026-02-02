# Implementation Summary: Major Updates to CI Planning and Plan Display

## Overview
This implementation addresses multiple issues with the Energy Export Monitor integration:
1. Fixed config flow 500 error when configuring/reconfiguring
2. Redesigned discharge plan generation logic (separate today/tomorrow plans)
3. Changed from attribute-based plan display to dedicated sensor entities
4. Added Solcast tomorrow solar prediction integration

## Issues Fixed

### 1. Config Flow 500 Error
**Problem**: When clicking the cog to configure the integration or reconfigure, users received a 500 Internal Server Error. Reconfiguration also wouldn't show new entities.

**Root Cause**: 
- The `_validate_entity()` function was checking if entities were available at configuration time
- Many entities (especially AlphaESS/Solcast) may not be available yet at startup
- Missing error handling in `async_step_reconfigure()` when accessing `self.context["entry_id"]`

**Solution**:
- Made entity validation more lenient - only checks if entity exists, not if it's available
- Added try/except error handling in `async_step_reconfigure()` with `.get()` instead of direct key access
- Added debug logging instead of warnings for missing entities during config flow

### 2. Plan Generation Logic Redesigned
**Problem**: Single monolithic plan that exported during highest CI periods without time awareness or solar constraints.

**Solution**: Created separate plans for today and tomorrow:

#### Today's Plan (`_generate_today_plan`)
- Considers only remaining time slots until midnight (now to 23:59:59)
- Energy budget = max(solar_generated_today, solar_predicted_today)
- Respects actual headroom constraints
- Exports during **lowest** CI periods (saves money) within available headroom
- Greedy algorithm fills lowest CI slots first

#### Tomorrow's Plan (`_generate_tomorrow_plan`)
- Full 24-hour planning window for tomorrow's date
- Energy budget = predicted solar from Solcast (for tomorrow)
- Exports during **lowest** CI periods within predicted solar capacity
- Allows planning ahead knowing next day's solar generation

**Key Changes**:
- Both plans now optimize for **low CI values** (cheapest to export) instead of high
- Today's plan respects actual export headroom (current grid_feed vs cap)
- Tomorrow's plan uses Solcast prediction without headroom constraints (planning only)
- Plans are calculated independently; today is executable, tomorrow is planning guide

### 3. Plan Display - From Attributes to Entities
**Problem**: Home Assistant hides attributes in UI, making plans invisible to users.

**Solution**: Created three discharge plan sensor entities:

#### Sensor Entities Created:
1. **`sensor.discharge_plan`** (legacy backward compatibility)
   - Shows overall plan summary
   - Attributes contain full plan details

2. **`sensor.discharge_plan_today`** (NEW)
   - State shows summary: `"N windows, X.XX kWh, avg CI Y"`
   - Attributes show full plan array with timestamps, CI values, durations, energy

3. **`sensor.discharge_plan_tomorrow`** (NEW)
   - Same format as today's plan
   - Shows planning guidance for next 24 hours

**Data Structure** (in attributes):
```json
{
  "plan": [
    {
      "from": "2026-02-04T09:30:00+00:00",
      "to": "2026-02-04T10:00:00+00:00",
      "duration_minutes": 7.2,
      "energy_kwh": 0.442,
      "ci_value": 89,
      "ci_index": "low"
    }
  ],
  "total_energy_kwh": 0.442,
  "windows": 1
}
```

### 4. Solcast Tomorrow Integration
**Problem**: Tomorrow's plan had no solar data to work with.

**Solution**: 
- Added new config parameter `CONF_SOLCAST_TOMORROW` (optional)
- Users can select which sensor entity provides tomorrow's predicted solar
- Added to both initial setup and reconfigure flows
- Tomorrow's plan only generates if Solcast tomorrow value is available and > 0

**Configuration**:
- In initial setup: Optional selector for Solcast Tomorrow sensor
- In reconfigure: Can add/change which sensor provides tomorrow's forecast
- If not configured: Tomorrow's plan will be empty but won't cause errors

## Code Changes

### Constants (`const.py`)
```python
# New configuration key
CONF_SOLCAST_TOMORROW: Final = "solcast_tomorrow"

# New attribute keys
ATTR_DISCHARGE_PLAN_TODAY: Final = "discharge_plan_today"
ATTR_DISCHARGE_PLAN_TOMORROW: Final = "discharge_plan_tomorrow"
```

### Config Flow (`config_flow.py`)
- Enhanced `_validate_entity()` to be lenient about availability
- Added error handling in `async_step_reconfigure()`
- Added `CONF_SOLCAST_TOMORROW` selector to user and reconfigure steps

### Coordinator (`coordinator.py`)
- Added `_generate_today_plan()` method for remaining-day planning
- Added `_generate_tomorrow_plan()` method for next-day planning
- Updated `_async_update_data()` to call both plan generators
- Returns both `ATTR_DISCHARGE_PLAN_TODAY` and `ATTR_DISCHARGE_PLAN_TOMORROW`
- Maintains backward compatibility with `ATTR_DISCHARGE_PLAN` (set to today's plan)

### Sensors (`sensor.py`)
- Added `DischargePlanTodaySensor` entity
- Added `DischargePlanTomorrowSensor` entity
- Both display plan summary in state and full details in attributes
- Registered both sensors in `async_setup_entry()`

## User Interface Changes

### New Entities
Users will see these new sensors in Home Assistant:
1. `sensor.energy_export_monitor_discharge_plan_today`
2. `sensor.energy_export_monitor_discharge_plan_tomorrow`

### Configuration Changes
New optional config field in Setup/Reconfigure:
- **Solcast Tomorrow** (optional): Select sensor providing tomorrow's solar prediction
- Type: Sensor selection
- Device class: energy
- Used to calculate tomorrow's discharge plan

## Behavior Changes

### Planning Logic
- **Before**: Single plan based on current + future headroom, high CI periods
- **After**: 
  - Today: Remaining time, actual headroom, LOW CI periods
  - Tomorrow: Full day, predicted solar, LOW CI periods

### Plan Visibility
- **Before**: Attributes hidden in UI, only visible in developer tools/automations
- **After**: Dedicated sensor entities with visible state and detailed attributes

### Export Optimization
- **Before**: Export during high CI (local carbon intensity) - counterintuitive
- **After**: Export during low CI - aligns with user goal of exporting when grid is clean

## Backward Compatibility
- `ATTR_DISCHARGE_PLAN` still populated (set to today's plan)
- Existing automations/templates continue to work
- Reconfigure maintains all previous settings

## Testing Recommendations

1. **Config Flow**
   - [ ] Setup integration (all required fields)
   - [ ] Click config cog - should load without 500 error
   - [ ] Reconfigure - should show current values
   - [ ] Change entity selections and save
   - [ ] Verify no errors in logs

2. **Today's Plan**
   - [ ] Set up with CI forecast sensor enabled
   - [ ] Set target export power
   - [ ] Verify plan has windows during low CI periods only
   - [ ] Check total energy ≤ available headroom
   - [ ] Verify windows only include remaining time today

3. **Tomorrow's Plan**
   - [ ] Configure Solcast Tomorrow sensor
   - [ ] Verify plan appears in sensor attributes
   - [ ] Check windows are for tomorrow's date
   - [ ] Verify total energy ≤ predicted solar for tomorrow
   - [ ] Confirm runs even if today's headroom is 0

4. **Sensor Display**
   - [ ] Both plan sensors appear in Lovelace
   - [ ] State shows summary (windows, energy, avg CI)
   - [ ] Attributes show full plan details
   - [ ] Empty plans show "No plan" gracefully

## Future Enhancements

1. Display both plans in Lovelace dashboard card
2. Calculate discharge times based on expected load profiles
3. Account for battery charging losses in plan calculation
4. Add plan execution with automatic discharge start/stop
5. Integration with Home Assistant energy dashboard

## Version

This implementation should be released as **v1.4.0** (major feature addition)

## Deployment Steps

1. Copy updated files to Home Assistant custom_components/export_monitor/
2. Restart Home Assistant
3. Go to Settings > Devices & Services > Energy Export Monitor
4. Click gear icon to update configuration
5. (Optional) Select Solcast Tomorrow sensor for tomorrow's plan
6. Verify no errors in Home Assistant logs
7. Check for new sensor entities in Developer Tools > States
