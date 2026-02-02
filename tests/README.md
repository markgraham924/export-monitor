# CI Planning Tests

Comprehensive test suite for the Carbon Intensity (CI) planning feature of the Energy Export Monitor integration.

## Test Coverage

### CI Parsing (`TestCIParsing`)
- ✅ Valid CI forecast JSON parsing
- ✅ Invalid JSON handling
- ✅ Missing required fields handling
- ✅ Empty periods handling
- ✅ None input handling

### Plan Generation (`TestPlanGeneration`)
- ✅ Plans sorted by CI (highest first)
- ✅ Respects export headroom limits
- ✅ Respects discharge power capacity
- ✅ Empty plan for zero headroom
- ✅ Empty plan for zero power
- ✅ Empty plan for no periods
- ✅ Greedy allocation to highest CI periods
- ✅ All required fields in windows

### Current CI Detection (`TestCurrentCI`)
- ✅ Current CI detection in valid period
- ✅ Handling when no period matches
- ✅ Handling empty periods list

### Real-World Scenarios (`TestRealWorldScenarios`)
- ✅ Full capacity export (3.68 kWh)
- ✅ Limited capacity export (1.0 kWh)
- ✅ Small discharge power (1 kW)
- ✅ Energy-duration consistency verification

## Running Tests Locally

### Install dependencies
```bash
pip install -r requirements-test.txt
```

### Run all tests
```bash
pytest tests/test_ci_planning.py -v
```

### Run with coverage
```bash
pytest tests/test_ci_planning.py --cov=custom_components/export_monitor --cov-report=html
```

### Run specific test class
```bash
pytest tests/test_ci_planning.py::TestPlanGeneration -v
```

### Run specific test
```bash
pytest tests/test_ci_planning.py::TestPlanGeneration::test_plan_sorted_by_ci_highest_first -v
```

## GitHub Actions

Tests run automatically on:
- Every push to `main` or `develop` branches
- Every pull request to `main`

**Python versions tested:** 3.11, 3.12

**Artifacts:**
- Test results with coverage report
- Coverage uploaded to Codecov

### View test results

1. Go to GitHub Actions tab
2. Click on "Test CI Planning" workflow
3. View results for each Python version
4. Download coverage report

## Test Statistics

- **Total Tests:** 20
- **Test Categories:** 4 (Parsing, Generation, Detection, Scenarios)
- **Execution Time:** ~0.10 seconds
- **Coverage:** Core CI planning logic

## Key Test Scenarios

### Scenario: Full Capacity Export
```
Headroom: 3.68 kWh
Discharge Power: 3.0 kW
Expected: Plan uses all available headroom, prioritizes highest CI periods
```

### Scenario: Limited Capacity
```
Headroom: 1.0 kWh
Discharge Power: 3.0 kW
Expected: Plan limited to 1.0 kWh, still prioritizes highest CI
```

### Scenario: Algorithm Consistency
```
Each window: energy = power × (duration / 60)
Expected: All windows satisfy this formula (tolerance: ±0.01 kWh)
```

## Troubleshooting

### Tests fail with "No module named 'tests'"
```bash
# Make sure you're in the project root
cd export-monitor
pytest tests/test_ci_planning.py
```

### ImportError on coordinator
The tests use a MockCoordinator that doesn't require Home Assistant dependencies. If you need to test with real coordinator, create a separate `test_coordinator_integration.py` file.

## Adding New Tests

1. Create test class inheriting from appropriate base
2. Use `@pytest.fixture` for common setup
3. Follow naming: `test_<feature>_<condition>`
4. Run tests to verify: `pytest tests/test_ci_planning.py -v`
5. Update this README with new test description

## Future Test Expansion

Planned test additions:
- [ ] Integration tests with mock Home Assistant
- [ ] Performance tests for large CI forecast datasets
- [ ] Edge cases with DST/timezone transitions
- [ ] Tests for export plan execution tracking
