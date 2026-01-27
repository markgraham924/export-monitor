# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
