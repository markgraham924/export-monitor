# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.9.17] - 2026-02-08

### Changed
- **Slot-aligned discharge**: Slot windows stay on 00/30 boundaries and duration is capped by planned slot energy and length.
- **Reduced write churn**: Power, cutoff, duration, and timer updates only occur when values actually change.
- **Simplified discharge control**: Auto modulation within a slot is disabled to reduce chatter.

## [1.9.16] - 2026-02-08

### Added
- **Last auto action detail**: Recorded action reason, target entity, value, and window context for all auto operations.

## [1.9.15] - 2026-02-08

### Fixed
- **Power modulation stability**: Throttled auto power adjustments, rounded to 2 decimals, and stopped tiny power setpoints to reduce flapping.
- **Whole-minute helper**: Discharge duration helper now uses whole-minute values.

## [1.9.14] - 2026-02-08

### Fixed
- **Auto toggle flapping**: Prevented auto charge/discharge from re-triggering within a window after the target is met, and seeded export tracking from the current export value.
- **Whole-minute duration**: Auto discharge now rounds window durations up to whole minutes for helper/timer updates.

## [1.9.13] - 2026-02-08

### Changed
- **Auto toggle shutdown**: Turning off auto-discharge stops discharge, and turning off auto-charge stops charging.

## [1.9.12] - 2026-02-08

### Changed
- **Auto discharge duration**: When auto-discharge is enabled, the integration now uses the active window length to set `timer.alphaess_helper_force_discharging_timer`, instead of the calculated duration.

## [1.9.11] - 2026-02-08

### Added
- **Current slot sensors**: Headroom, exported energy, target energy, progress, and time remaining for the active plan window.
- **Diagnostics**: Auto-control summary, last auto action, service call stats, and window parse error counts.
- **Control**: Reset Auto Stats button for clearing auto-control diagnostics.

### Changed
- **Charge automation**: Auto-charge now enforces window targets and modulates charge power to stay on plan, mirroring discharge behavior.

## [1.9.10] - 2026-02-08

### Fixed
- **Auto-toggle enforcement**: When auto-discharge is enabled, the integration now forces the Alpha ESS discharge toggle on during active windows and off outside them, overriding manual changes.

## [1.9.9] - 2026-02-08

### Fixed
- **Per-window energy enforcement**: Auto-discharge now tracks exported energy within each plan window and stops when that window's energy target is reached, preventing over-export inside a half-hour slot.
- **Real-time modulation**: Discharge power is adjusted during a window to stay on target when household load changes.

## [1.9.8] - 2026-02-08

### Fixed
- **Auto control enforcement**: Auto charge/discharge now starts when already inside a planned window and stops when outside any planned window to keep Alpha ESS controls aligned with the plan.
- **Target export limits**: Target Export max reduced to 5000 W across the entity and config flows to match the intended 5 kW ceiling.

## [1.9.7] - 2026-02-08

### Fixed
- **Timezone-aware window handling**: Use a UTC-aware `now`, normalize window datetimes, and compute a localized `now` so windows with timezone-aware bounds compare reliably and trigger in the right timezone.
- **Window key compatibility**: Accept `from`/`to` as fallbacks for `period_start`/`period_end` when parsing plan windows to support alternate payload shapes.

## [1.9.6] - 2026-02-08

### Fixed
- **Calculated Duration Sensor**: Corrected duration calculation logic and reporting
- **Discharge Button Activation**: Fixed activation timing to align with calculated durations (#15)

## [1.9.5] - 2026-02-05

### Fixed
- **Critical Bug Fix**: Resolved NameError from unreachable code and conditionally-defined variables (#14)
  - Fixed variable initialization issues in error handling paths
  - Ensures robust error recovery in edge cases

## [1.10.0] - 2026-02-04 - **Production Readiness Update**

### Added - Safety & Reliability
- **Error Handler Module** (`error_handler.py`): Comprehensive error handling infrastructure
  - `SafeServiceCall`: Wraps all service calls with 5-second timeout and state verification
  - `CircuitBreaker`: Prevents cascade failures (opens after 5 failures, auto-resets after 60s)
  - `StaleDataDetector`: Tracks data age and blocks discharge when data >30s old
  - `SensorValidation`: Validates all sensor values against reasonable ranges
    - SOC: 0-100%
    - Energy: 0-1000 kWh
    - Power: ±50 kW

- **System Health Monitoring**: 4 new diagnostic sensors (Entity Category: Diagnostic)
  - `System Health`: Overall status (Healthy/Error/Stale Data/Circuit Breaker Open)
  - `Error State`: Current error condition with specific codes
  - `Data Staleness`: Age of coordinator data in seconds
  - `Circuit Breaker Status`: Failure protection state with failure count

- **Persistent Notifications**: Critical failures send persistent notifications with:
  - Detailed error description
  - Specific resolution steps
  - Entity/sensor identification
  - Auto-dismiss when error resolves
  - Notification types: SOC Sensor Failed, Stale Data, Discharge Power Failed, Start Failed, Stop Failed (CRITICAL)

- **Production Deployment Guide** (`PRODUCTION_GUIDE.md`): Comprehensive 500+ line guide covering:
  - Pre-deployment checklist and safe testing procedures
  - Critical sensors monitoring guide
  - 5 common failure scenarios with symptoms and resolution
  - Emergency stop procedures (4 levels: HA service, Alpha ESS integration, app, hardware)
  - Logging and diagnostics configuration
  - Performance tuning for different system loads
  - Compliance and liability considerations
  - Quick reference card for critical operations

### Changed - Service Call Safety
- **All service calls** now use `safe_service_call` with:
  - 5-second timeout (prevents hanging)
  - Entity state verification after call
  - Error notification on failure
  - Coordinator error state tracking

- **Sensor value retrieval** now validated with type-specific ranges:
  - `_get_sensor_value` now requires `sensor_type` parameter
  - Invalid values logged and rejected
  - Default values returned on validation failure

- **Coordinator update loop** protected with:
  - Circuit breaker check before each update
  - Success/failure tracking for circuit breaker
  - Stale data timestamp recording
  - Proper exception handling with UpdateFailed re-raising

### Enhanced - Public API
- Added public methods to coordinator for better encapsulation:
  - `can_attempt_operation()`: Check if circuit breaker allows operations
  - `is_circuit_breaker_open()`: Check circuit breaker state
  - `is_data_stale()`: Check if data is too old
  - `get_data_age()`: Get data age in seconds
  - `get_error_state()`: Get current error condition
  - `set_error_state(error)`: Record error with logging
  - `clear_error_state()`: Clear error and reset circuit breaker
  - `get_system_health()`: Get comprehensive health status

### Fixed
- Fixed encapsulation: Sensors now use public methods instead of accessing `_circuit_breaker` directly
- Added missing `sensor_type="energy"` parameter to solcast_tomorrow sensor call
- Version consistency: PRODUCTION_GUIDE.md updated to v1.10.0 (matches manifest.json)

### Security
- ✅ **CodeQL Security Scan**: Passed with 0 vulnerabilities
- All user inputs validated
- Service call timeouts prevent resource exhaustion
- Circuit breaker prevents abuse
- Sensor value ranges prevent injection

### Documentation
- Updated README.md with:
  - ⚠️ Important Safety Notice section
  - Production Readiness Features checklist
  - Link to PRODUCTION_GUIDE.md
  - System Health & Monitoring sensor descriptions
  - Comprehensive changelog for v1.10.0

### Production Readiness Score: 8/10
- Before: 4/10 (Not Production Ready)
- After: 8/10 (Production Ready with Monitoring)
- Remaining items are quality-of-life enhancements, not blockers

### Migration Notes
- **No breaking changes** - All changes are backward compatible
- New diagnostic sensors will appear automatically after upgrade
- Existing configurations continue to work without changes
- Recommended: Review PRODUCTION_GUIDE.md for monitoring best practices

## [1.9.4] - 2026-02-04

### Fixed
- **Charge Window Time Format Parsing**: Fixed parsing to handle both HH:MM and HH:MM:SS formats
  - AlphaESS provides charge window times with seconds (e.g., '00:00 - 07:00:00')
  - Previous code expected only HH:MM format, causing parsing failures
  - Added missing `time` import from datetime module
  - Updated all three charge planning methods to flexibly parse variable-length time strings

## [1.9.2] - 2026-02-04

### Fixed
- **CRITICAL: Charge Planning Dictionary Key Bug**: Charge planning was looking for wrong CI data key
  - Bug: Code looked for `ci_data['data']` but `_parse_ci_forecast()` returns `ci_data['periods']`
  - Impact: Charge planning always received empty periods list, causing "No charge session planned"
  - This explains why charge session never populated despite multiple previous fixes
  - Now uses correct 'periods' key matching parser output
  - Added comprehensive debug logging for future troubleshooting

## [1.9.1] - 2026-02-04

### Fixed
- **Overnight Charge Window Logic**: Fixed condition bug that prevented next charge session from being calculated
  - Bug: Used AND instead of OR in window boundary check (`current_time < start AND current_time > end` is impossible)
  - Now correctly identifies next charge window for overnight schedules (e.g., 00:00-07:00)
  - Periods within next window are properly filtered and included in charge plan
  - Next Charge Session sensor now displays data when charge planning is enabled

## [1.9.0] - 2026-02-04

### Changed
- **Charge Planning Refactor**: Simplified charge plan logic to single "Next Charge Session" sensor
  - Removed "Charge Plan Today" and "Charge Plan Tomorrow" (confusing for overnight windows)
  - New "Next Charge Session" sensor shows upcoming charge window with greenest (lowest CI) periods
  - Logic finds next charge window from current time and allocates energy to lowest CI periods
  - More intuitive: At 17:31, next session is tonight (00:00-07:00), not split by calendar days
  - Displays windows with times, energy amounts, and CI values; includes attributes for total_energy, num_windows, avg_ci

### Added
- **Smoke Tests**: New integration test suite to catch runtime errors before deployment
  - `test_coordinator_no_undefined_variables`: Detects variable name mismatches (e.g., min_soc vs min_soc_percent)
  - `test_coordinator_return_dict_keys`: Verifies return dictionary keys reference defined variables
  - `test_coordinator_import_completeness`: Ensures all CONF_/DEFAULT_ constants are imported
  - `test_all_test_files_have_assertions`: Validates test code quality
  - Successfully caught the v1.8.2 bug pattern if reintroduced
  - 82 total tests (78 unit + 4 smoke), all passing

## [1.8.1] - 2026-02-04

### Fixed
- **Diagnostic Sensors Display**: Added missing diagnostic values (current_soc, min_soc, reserve_soc_target) to coordinator data dictionary
  - Fixes Current SOC, Minimum SOC, and Reserve SOC Target sensors showing "Unknown"
  - GenericDiagnosticSensor now has access to all calculated values

## [1.8.0] - 2026-02-04

### Added
- **Battery Capacity Configuration**: New required configuration field for battery total capacity in kWh (default: 10 kWh)
  - Enables accurate energy calculations for charge planning
  - Calculates energy needed as: `(100% - current_soc%) / 100 × battery_capacity_kwh`
  - Configurable via UI with range 0.5 - 100 kWh in 0.1 kWh steps
  - Added to user setup, reconfigure, and options flows

### Changed
- **Charge Plan Calculation**: Replaced heuristic battery capacity estimation with explicit configuration
  - Today's charge plan: Calculates energy from current SOC to 100%
  - Tomorrow's charge plan: Plans for full battery capacity charge
  - More accurate energy allocation across low-CI periods

## [1.7.5] - 2026-02-04

### Fixed
- **Current SOC Handling**: Changed from direct dictionary access to `.get()` method for CONF_CURRENT_SOC
  - Prevents crashes when sensor configuration is missing
  - Gracefully handles missing SOC sensor during initialization

## [1.7.4] - 2026-02-04

### Fixed
- **State Class Warnings**: Removed MEASUREMENT state_class from energy device sensors
  - Home Assistant expects energy device class to use None, TOTAL_INCREASING, or TOTAL for state_class
  - Fixed warnings for: ExportHeadroomSensor, PlanEnergySensor entities
- **Charge Plan Generation Logic**: Fixed conditional checks to ensure proper nested execution
  - Checks current_soc availability before attempting charge planning
  - Properly nests `if periods:` block within `if ci_data:` scope
  - Prevents undefined variable access

## [1.7.3] - 2026-02-04

### Fixed
- **Charge Plan Variable Scope**: Corrected undefined `parsed_ci` variable in charge plan generation
  - Charge planning now independently fetches CI data
  - Added proper null checks before accessing ci_data
  - Fixes "name 'parsed_ci' is not defined" runtime error

## [1.7.2] - 2026-02-04

### Fixed
- **Coordinator Import Fix**: Added missing SERVICE_START_DISCHARGE and charge planning constant imports to coordinator.py

## [1.7.1] - 2026-02-04

### Fixed
- **Config Flow 500 Error**: Added missing charge planning constant imports to config_flow.py

## [1.7.0] - 2026-02-04

### Added
- **Battery Charge Planning**: Intelligent charge planning identifies lowest carbon intensity periods within a user-defined window
- **Charge Plan Sensors**: New sensors to display charge plans for today and tomorrow
  - `sensor.charge_plan_today`: Shows optimal charging windows with energy allocation
  - `sensor.charge_plan_tomorrow`: Tomorrow's planned charging periods
- **Charge Window Configuration**: Time-based start/end selectors to define charging hours (default: 00:00 - 06:00 for overnight)
- **Charge Power Setting**: Configurable charge power in kW (default: 3.68 kW)
- **Lowest CI Prioritization**: Unlike discharge (high CI), charge planning selects **lowest carbon intensity periods** to minimize grid carbon impact during charging
- **Energy Calculations**: Automatically calculates energy needed to reach 100% SOC from current battery state
- **Comprehensive Tests**: Added 7 new unit tests for charge planning logic covering:
  - Lowest CI period sorting
  - Energy allocation across periods
  - SOC to energy conversion
  - Window filtering (normal and overnight windows)
  - Multiple period allocation

### Changed
- Extended configuration flows (user, reconfigure, options) with charge planning controls

## [1.6.0] - 2026-02-05

### Added
- **Auto-Discharge Feature**: New toggle control to automatically trigger discharge at planned export windows
- **Export Window Constraints**: Time-based start/end selectors to limit discharge to specific hours (default: 00:00 - 23:59)
- **Window Auto-Trigger**: Discharge automatically starts when current time reaches planned window time
- **Window Deduplication**: Prevents duplicate discharge triggers for the same window within a 24-hour period
- **High CI Prioritization**: Fixed plan generation to prioritize HIGH carbon intensity periods (when grid is dirtiest)
  - Discharge now helps grid most during peak carbon times instead of off-peak times
  - Descending CI sort ensures highest-carbon periods are planned first

### Changed
- **Plan Generation Logic**: Export window constraints now filter discharge periods to only include times within specified window
- **CI Period Sorting**: Changed from ascending to descending order to prioritize highest carbon intensity periods

## [1.5.1] - 2026-02-04

### Fixed
- **Config Flow 500 Error**: Added missing configuration fields to reconfigure step (CI Forecast Sensor, Enable CI Planning)
- **Reconfigure Missing Fields**: All sensors and options now available for reconfiguration
- **Device Class Validation**: Removed strict device class requirements for optional Solcast sensors to prevent validation errors
- **Detailed Plan Display**: Plan sensors now show time windows and energy (e.g., "16:30 - 17:00 0.60kWh") instead of summary counts

## [1.5.0] - 2026-02-04

### Added
- **Diagnostic Sensor Section**: Moved battery SOC, solar forecast, and internal status flags to a dedicated Diagnostics section.
- **Detailed Plan Sensors**: Created new sensor entities for plan energy and window counts (Today, Tomorrow, Total) to ensure visibility in modern Home Assistant UI.

### Changed
- **Removed Attributes**: Eliminated `extra_state_attributes` from primary sensors, replacing them with discrete sensor entities for better data accessibility.

## [1.4.1] - 2026-02-04

### Fixed
- Fixed invalid JSON in manifest.json (trailing comma causing install/update failures)

## [1.4.0] - 2026-02-04

### Added
- **Separate Today/Tomorrow Discharge Plans**: Major redesign of CI planning logic
  - New sensor: `discharge_plan_today` - Remaining time slots until midnight with actual headroom constraints
  - New sensor: `discharge_plan_tomorrow` - Full 24-hour plan using Solcast predicted solar
  - Optional `Solcast Tomorrow` configuration for tomorrow's solar prediction
  - Both plans now export during **low CI periods** (cleanest grid) instead of high
  - Today's plan respects actual export headroom; tomorrow's plan optimizes within predicted solar capacity

### Fixed
- **Config Flow 500 Error**: Integration config/reconfigure now loads without errors
  - Lenient entity validation - only checks existence, not availability at config time
  - Proper error handling in reconfigure step
  - Fixes issue where AlphaESS/Solcast sensors unavailable at startup caused config errors

### Changed
- **Plan Display Strategy**: Moved from attribute-only display to dedicated sensor entities
  - Plans now visible in Home Assistant UI (previously hidden in attributes)
  - Backward compatible: `discharge_plan` sensor still populated (set to today's plan)
  - Enhanced plan data structure with window-by-window breakdown

### Improved
- Plan generation algorithm prioritizes clean grid exports (low CI values)
- Time-aware planning: today's plan only includes remaining slots until midnight
- Tomorrow's plan uses full 24-hour window with predicted solar

## [1.3.2] - 2026-02-02

### Fixed
- CI forecast parsing now accepts attribute data where `data` is a list of periods or a nested dict
- CI planning can parse forecast periods even when sensor state is unknown

## [1.3.1] - 2026-02-02

### Fixed
- CI forecast parsing now supports sensors that provide forecast data in attributes even when the state is unknown
- CI planning runs when attributes contain the forecast list (common for Carbon Intensity integrations)

## [1.3.0] - 2026-02-02

### Added
- **Carbon Intensity (CI) Aware Discharge Planning**: New optional feature that generates discharge plans prioritizing highest-carbon periods within available headroom constraints
  - New sensors: `CurrentCIValueSensor`, `CurrentCIIndexSensor`, `DischargePlanSensor`
  - Greedy algorithm allocates discharge windows to highest-CI periods
  - Respects system constraints: 3.68 kWh max discharge capacity and user-configured power settings
  - Optional CI forecast sensor configuration
  - Automatic CI data parsing from forecast JSON
- **Comprehensive Test Suite**: 71 unit tests covering all core functionality
  - 20 tests for CI planning (parsing, allocation, algorithm validation)
  - 51 tests for core features (discharge duration, headroom, buttons, configuration, sensors, energy consistency, edge cases)
  - 100% pass rate with ~0.14s execution time
  - GitHub Actions CI/CD workflow for Python 3.11 and 3.12
- **Updated Documentation**:
  - Agent instructions (250+ lines of development guidance)
  - Logo assets (256×256 and 512×512 optimized PNGs)
  - Comprehensive README with discharge formula explanation
  - Tests README with coverage details and running instructions

### Changed
- Discharge formula clarification in documentation: Fixed power (user-configured) with duration scaling linearly with available headroom
- Updated button logic to check export headroom availability instead of discharge_needed state
- CI features are fully optional; existing installations unaffected

### Technical Details
- New coordinator methods: `_parse_ci_forecast()`, `_find_highest_ci_periods()`, `_get_current_ci_index()`
- CI planning disabled by default; users can optionally enable via config flow
- Backward compatible: all new features are opt-in
- Test suite validates algorithm correctness and edge cases

## [1.2.6] - 2026-02-02

### Fixed
- Discharge service now uses the configured target export power when setting discharge power, preventing invalid helper values and ensuring power is >0 W

## [1.2.5] - 2026-02-02

### Changed
- Version bump only; no functional changes since 1.2.4

## [1.2.4] - 2026-02-01

### Fixed
- Reissued 1.2.3 changes with corrected GitHub release automation

## [1.2.3] - 2026-02-01

### Fixed
- **Critical**: Discharge duration now respects user-configured value from helper entity
- When `target_export` is 0 (default), the system now reads the desired duration from `input_number.alphaess_helper_force_discharging_duration` or `number.alphaess_template_force_discharging_duration`
- No longer hardcodes duration to 60 minutes when these entities have different values
- Discharge power is now calculated based on the desired duration: `power = (headroom_kwh / (duration_minutes / 60)) * 1000`

### Changed
- Added `_get_desired_duration()` method to coordinator to read duration from helper entities
- Enhanced logging to show when duration is read from helper entity vs fallback default

### Technical Details
- When `target_export` is configured (>0), duration is still calculated dynamically based on headroom and target power
- When `target_export` is 0, system now checks for duration helper entity first, then falls back to 60 minutes only if entity not found
- This allows users to control discharge duration through the helper entity as originally intended

## [1.2.2] - 2026-01-27

### Fixed
- **Critical**: OptionsFlow config_entry property setter error causing UI crash
- Removed custom `__init__` from OptionsFlowHandler that attempted to set read-only property
- Integration no longer crashes when accessing options in Home Assistant UI

### Technical Details
- Home Assistant's `OptionsFlow` base class automatically manages `config_entry` property
- Custom initialization was redundant and conflicted with read-only property definition

## [1.2.1] - 2026-01-27

### Fixed
- **Critical**: Auto-stop discharge when export headroom is exhausted (≤0 kWh)
- Prevents continued discharge when safe export limit is reached or exceeded
- Fixed duration fallback logic - no longer defaults to 60 minutes when headroom is 0
- Added validation to prevent starting discharge when no headroom available
- Improved auto-stop logic with unified check for all stop conditions

### Changed
- Auto-stop now triggers for three conditions (in priority order):
  1. Export headroom exhausted (≤0 kWh) - prevents export limit breach
  2. Discharge target reached - when calculated energy exported
  3. Reserve SOC limit reached - battery protection
- Service handler now rejects discharge start when calculated duration is 0
- Enhanced logging shows specific stop reason

### Technical Details
- Coordinator checks headroom every 30 seconds during discharge
- Auto-stop callback triggers immediately when any limit reached
- Prevents negative export headroom situations

## [1.2.0] - 2026-01-27

### Added
- Reserve SOC monitoring feature to protect battery from excessive discharge
- Optional `reserve_soc_sensor` configuration field to specify sensor with end-of-day reserve target
- `observe_reserve_soc` toggle to enable/disable reserve monitoring (default: disabled)
- Automatic discharge stop when current SOC drops below reserve target
- New sensors: `reserve_soc_target` (%) and `reserve_soc_status` (monitoring status)
- Auto-stop callback mechanism in coordinator to stop discharge when reserve limit reached

### Changed
- Config flow now includes optional reserve SOC sensor selection
- Coordinator monitors reserve SOC during discharge if configured
- Enhanced logging for reserve limit events

### Use Case
- For users with sensors that predict required battery reserve for end of day
- Prevents battery discharge below the minimum needed for evening/night usage
- Automatically stops discharge when reserve limit is reached

### Example
- Configure `sensor.battery_soc_reserve_target` (updates hourly with required reserve)
- Enable `observe_reserve_soc` toggle
- During discharge, if current SOC drops below reserve target, discharge automatically stops
- Status sensors show reserve target, monitoring state, and limit reached status

## [1.1.0] - 2026-01-27

### Added
- Dynamic discharge duration calculation based on target export power
- New `_calculate_discharge_duration()` method in coordinator with background load buffer (default 10%)
- New sensors: `calculated_duration` (minutes) and `discharge_complete` (status)
- Discharge progress tracking: monitors grid export during discharge and logs when target is reached
- Coordinator now tracks discharge start time, initial export, and target energy

### Changed
- **BREAKING**: Discharge logic no longer assumes 1-hour duration
- Discharge power now uses `target_export` configuration value instead of calculating from headroom
- Duration calculation: `duration_minutes = (headroom_kwh / target_export_kw) * 60 * (1 + buffer)`
- Service `start_discharge` now has optional `duration` parameter - uses calculated duration if not provided
- Enhanced logging for discharge tracking and duration calculation

### Example
- With 1 kWh headroom and 3.68 kW target export: duration = ~16 minutes (plus 10% buffer = ~18 minutes)
- With 0.5 kWh headroom and 3.68 kW target export: duration = ~8 minutes (plus buffer = ~9 minutes)

## [1.0.3] - 2026-01-27

### Fixed
- Fixed syntax error in service registration schema that prevented integration from loading
- Corrected service schema to properly include both `power` and `duration` parameters

## [1.0.2] - 2026-01-27

### Fixed
- Fixed reconfiguration flow to properly show current entity values
- Config flow now correctly retrieves existing config entry when reconfiguring
- Integration properly reloads after entity reconfiguration

## [1.0.1] - 2026-01-27

### Added
- Entity reconfiguration support via device page
- Automatic discharge duration control (looks for `input_number.alphaess_helper_force_discharging_duration`)
- Entity domain detection for proper service calls (`input_number` vs `number`)

### Changed
- Replaced `cutoff_soc` parameter with `duration` parameter (defaults to 60 minutes)
- Cutoff SOC now always set to 20% (min_soc) to avoid Alpha ESS grid-switching behavior

### Fixed
- Fixed entity control to work with both `input_number` and `number` entities
- Fixed service calls to use correct domain and service names

## [1.0.0] - 2026-01-27

### Added
- Initial release
- Energy-based export control using kWh sensors
- Alpha ESS battery discharge control integration
- Solcast PV forecast integration
- Config flow with UI and YAML support
- Device grouping (10 entities under single device)
- Services: start_discharge, stop_discharge, calculate_discharge
- Entities: buttons, numbers, sensors
- HACS compatibility

### Features
- Calculates safe export limit: `max(pv_energy_today, forecast_total_today) + safety_margin_kwh`
- Prevents T&C breaches with configurable safety margin (default 0.5 kWh)
- 30-second polling interval
- Automatic discharge power calculation
- Battery SOC safety checks

[1.0.3]: https://github.com/markgraham924/export-monitor/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/markgraham924/export-monitor/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/markgraham924/export-monitor/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/markgraham924/export-monitor/releases/tag/v1.0.0
