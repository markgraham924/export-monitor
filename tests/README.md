# Energy Export Monitor Tests

Comprehensive test suite for the Energy Export Monitor integration, covering CI planning features and core discharge functionality.

## Test Files

### test_ci_planning.py
Carbon Intensity (CI) planning feature tests.

**Coverage (20 tests):**
- ✅ **CI Parsing** (5 tests) - Valid JSON, invalid JSON, missing data, empty periods, None input
- ✅ **Plan Generation** (9 tests) - Sorting, constraints, allocation, greedy algorithm
- ✅ **Current CI Detection** (3 tests) - Period identification, edge cases
- ✅ **Real-World Scenarios** (3 tests) - Full capacity, limited capacity, consistency checks

### test_core_functionality.py
Core discharge and energy management logic tests.

**Coverage (51 tests):**
- ✅ **Discharge Duration Calculation** (7 tests) - Formula verification, buffer application, edge cases
- ✅ **Export Headroom Calculation** (7 tests) - SOC-based headroom, safety margins, capacity limits
- ✅ **Button Availability Logic** (8 tests) - Start/stop button conditions, state transitions
- ✅ **Configuration Validation** (10 tests) - Power range, SOC range, safety margins, CI options
- ✅ **Sensor State Calculations** (8 tests) - Headroom, discharge status, duration, CI values
- ✅ **Energy Consistency** (5 tests) - Round-trip calculations, multi-window tracking
- ✅ **Edge Cases** (6 tests) - Fractional values, extreme power ranges, precision handling

## Test Statistics

**Total Tests:** 71
- CI Planning: 20 tests
- Core Functionality: 51 tests

**Execution Time:** ~0.14 seconds
**Pass Rate:** 100% (71/71)

## Running Tests Locally

### Install dependencies
```bash
pip install -r requirements-test.txt
```

### Run all tests
```bash
pytest -v
```

### Run specific test file
```bash
pytest tests/test_core_functionality.py -v
pytest tests/test_ci_planning.py -v
```

### Run with coverage
```bash
pytest --cov=custom_components/export_monitor --cov-report=html
```

### Run specific test class
```bash
pytest tests/test_core_functionality.py::TestDischargeDurationCalculation -v
pytest tests/test_ci_planning.py::TestPlanGeneration -v
```

### Run specific test
```bash
pytest tests/test_core_functionality.py::TestDischargeDurationCalculation::test_duration_basic_calculation -v
```

## Test Organization

### Discharge Duration Formula
Tests validate: `duration_minutes = (headroom_kwh / power_kw) × 60`

Tests cover:
- Basic calculations across different power levels
- Full capacity scenarios (3.68 kWh max)
- 10% safety buffer application
- Edge cases (zero headroom, extreme power values)

### Export Headroom Calculation
Tests validate: `headroom_kwh = (current_soc - target_soc) / 100 × battery_capacity`

Tests cover:
- SOC-based headroom with Alpha ESS 13.8 kWh battery
- Safety margin application
- Full discharge range (100% to 0%)
- Capacity limits (max 3.68 kWh)
- Fractional SOC values

### Button Availability
Tests validate when buttons are enabled/disabled:

**Start Discharge:** Available when headroom > 0
**Stop Discharge:** Available when actively discharging

Tests cover:
- State transitions (waiting → discharging → waiting)
- Condition boundaries
- User interaction flow

### Configuration Validation
Tests verify all user-configurable values:
- Target export power (1-15 kW range)
- Target SOC (0-100%)
- Safety margin (0-20%)
- Optional CI sensor configuration
- Update intervals

### Sensor State Calculations
Tests validate sensor output values:
- Export headroom (kWh)
- Discharge status (Discharging/Idle)
- Discharge duration (minutes)
- Current CI value (gCO2/kWh)
- Current CI index (very_low/low/moderate/high)

### Energy Consistency
Tests verify mathematical consistency:
- Energy = Power × (Duration / 60)
- Headroom consumption by discharge
- SOC change reflects energy discharged
- Round-trip calculations (headroom → power/duration → energy)
- Multi-window discharge tracking

## GitHub Actions

Tests run automatically on:
- Every push to `main` or `develop` branches
- Every pull request to `main`

**Python versions tested:** 3.11, 3.12

### View test results

1. Go to GitHub Actions tab
2. Click on "Test CI Planning" workflow
3. View results for each Python version
4. Download coverage report

## Key Test Scenarios

### Scenario 1: Full Capacity Export
```
Battery:       13.8 kWh (Alpha ESS)
Current SOC:   75%
Target SOC:    10%
Headroom:      3.68 kWh (max capacity)
Power:         3.0 kW
Duration:      73.6 minutes
```

### Scenario 2: Limited Capacity Export
```
Headroom:      1.0 kWh
Power:         3.0 kW
Duration:      20 minutes (limited by power, not headroom)
```

### Scenario 3: Small Power Discharge
```
Headroom:      1.0 kWh
Power:         0.5 kW
Duration:      120 minutes
Use Case:      Gradual export during low-demand periods
```

### Scenario 4: CI-Aware Planning
```
Available Headroom:    3.68 kWh
Forecast Periods:      24 hourly CI values
Discharge Power:       3.0 kW
Plan:                  Select highest-CI periods
                      Allocate discharge windows
                      Total energy ≤ headroom
```

## Troubleshooting

### Tests fail with "No module named 'tests'"
```bash
# Make sure you're in the project root
cd export-monitor
pytest
```

### ImportError on coordinator
The tests use mock objects that don't require Home Assistant dependencies.

### Import errors on custom_components
Ensure the `custom_components` package is discoverable:
```bash
# Run tests from project root
cd /path/to/export-monitor
pytest
