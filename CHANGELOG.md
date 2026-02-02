# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
