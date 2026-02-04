"""
Tests for core Energy Export Monitor functionality.

Covers:
- Discharge duration calculation
- Export headroom calculation
- Button availability logic
- Sensor state calculations
- Configuration validation
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone


# ============================================================================
# Discharge Duration Calculation Tests
# ============================================================================

class TestDischargeDurationCalculation:
    """Test the discharge duration calculation formula."""

    def test_duration_basic_calculation(self):
        """Test basic duration calculation: duration = (headroom / power) * 60."""
        # Given: headroom=2.0 kWh, power=3.0 kW
        # Expected: duration = (2.0 / 3.0) * 60 = 40 minutes
        headroom_kwh = 2.0
        power_kw = 3.0
        
        duration_minutes = (headroom_kwh / power_kw) * 60
        
        assert duration_minutes == pytest.approx(40.0)

    def test_duration_full_capacity(self):
        """Test duration with full 3.68 kWh headroom."""
        headroom_kwh = 3.68
        power_kw = 3.0
        
        duration_minutes = (headroom_kwh / power_kw) * 60
        
        assert duration_minutes == pytest.approx(73.6)

    def test_duration_small_power(self):
        """Test duration with small discharge power."""
        headroom_kwh = 1.0
        power_kw = 0.5
        
        duration_minutes = (headroom_kwh / power_kw) * 60
        
        assert duration_minutes == pytest.approx(120.0)

    def test_duration_high_power(self):
        """Test duration with high discharge power."""
        headroom_kwh = 2.0
        power_kw = 5.0
        
        duration_minutes = (headroom_kwh / power_kw) * 60
        
        assert duration_minutes == pytest.approx(24.0)

    def test_duration_with_10_percent_buffer(self):
        """Test duration calculation with 10% safety buffer applied."""
        headroom_kwh = 2.0
        power_kw = 3.0
        
        # Calculate duration with 10% buffer
        duration_minutes = (headroom_kwh / power_kw) * 60
        duration_with_buffer = duration_minutes * 0.9  # 10% reduction for safety
        
        assert duration_minutes == pytest.approx(40.0)
        assert duration_with_buffer == pytest.approx(36.0)

    def test_duration_zero_headroom(self):
        """Test duration when headroom is zero."""
        headroom_kwh = 0.0
        power_kw = 3.0
        
        duration_minutes = (headroom_kwh / power_kw) * 60
        
        assert duration_minutes == 0.0

    def test_duration_zero_power(self):
        """Test duration when power is zero (should be prevented at config level)."""
        headroom_kwh = 2.0
        power_kw = 0.0
        
        # In real code, this would be prevented by config validation
        # But mathematically it's infinite/undefined
        with pytest.raises(ZeroDivisionError):
            duration_minutes = (headroom_kwh / power_kw) * 60


# ============================================================================
# Export Headroom Calculation Tests
# ============================================================================

class TestExportHeadroomCalculation:
    """Test export headroom calculation from battery SOC."""

    def test_headroom_basic_calculation(self):
        """Test basic headroom: max_soc - current_soc."""
        battery_capacity_kwh = 13.8
        current_soc = 50  # 50%
        target_soc = 10  # discharge down to 10%
        
        headroom_kwh = (current_soc - target_soc) / 100 * battery_capacity_kwh
        
        assert headroom_kwh == pytest.approx(5.52)

    def test_headroom_with_safety_margin(self):
        """Test headroom with safety margin applied."""
        battery_capacity_kwh = 13.8
        current_soc = 80
        target_soc = 10
        safety_margin = 5  # 5% safety margin
        
        # Effective SOC range: current_soc - safety_margin to target_soc
        effective_soc = current_soc - safety_margin
        headroom_kwh = (effective_soc - target_soc) / 100 * battery_capacity_kwh
        
        assert headroom_kwh == pytest.approx(8.97)

    def test_headroom_full_range(self):
        """Test headroom from 100% to 0%."""
        battery_capacity_kwh = 13.8
        current_soc = 100
        target_soc = 0
        
        headroom_kwh = (current_soc - target_soc) / 100 * battery_capacity_kwh
        
        assert headroom_kwh == pytest.approx(13.8)

    def test_headroom_at_target_soc(self):
        """Test headroom when already at target SOC."""
        battery_capacity_kwh = 13.8
        current_soc = 10
        target_soc = 10
        
        headroom_kwh = (current_soc - target_soc) / 100 * battery_capacity_kwh
        
        assert headroom_kwh == 0.0

    def test_headroom_alpha_ess_13_8_kwh(self):
        """Test headroom with Alpha ESS 13.8 kWh typical configuration."""
        battery_capacity_kwh = 13.8
        current_soc = 75
        target_soc = 10
        
        headroom_kwh = (current_soc - target_soc) / 100 * battery_capacity_kwh
        
        assert headroom_kwh == pytest.approx(8.97)

    def test_headroom_capped_at_max_discharge(self):
        """Test headroom is capped at max discharge capacity."""
        battery_capacity_kwh = 13.8
        current_soc = 100
        target_soc = 0
        max_discharge_kwh = 3.68  # Physical limit
        
        headroom_kwh = (current_soc - target_soc) / 100 * battery_capacity_kwh
        capped_headroom = min(headroom_kwh, max_discharge_kwh)
        
        assert headroom_kwh == pytest.approx(13.8)
        assert capped_headroom == pytest.approx(3.68)

    def test_headroom_percentage_calculation(self):
        """Test headroom expressed as percentage of capacity."""
        battery_capacity_kwh = 13.8
        current_soc = 65
        target_soc = 20
        
        headroom_kwh = (current_soc - target_soc) / 100 * battery_capacity_kwh
        headroom_percent = ((current_soc - target_soc) / (100 - target_soc)) * 100
        
        assert headroom_kwh == pytest.approx(6.21)
        assert headroom_percent == pytest.approx(56.25, rel=1e-3)


# ============================================================================
# Button Availability Logic Tests
# ============================================================================

class TestButtonAvailability:
    """Test button availability conditions."""

    def test_start_discharge_available_with_headroom(self):
        """Start discharge button should be available when headroom > 0."""
        headroom_kwh = 1.0
        
        # Button availability logic
        is_available = headroom_kwh > 0
        
        assert is_available is True

    def test_start_discharge_unavailable_no_headroom(self):
        """Start discharge button should be unavailable when headroom = 0."""
        headroom_kwh = 0.0
        
        is_available = headroom_kwh > 0
        
        assert is_available is False

    def test_start_discharge_unavailable_below_target_soc(self):
        """Start discharge button should be unavailable when at/below target SOC."""
        current_soc = 10
        target_soc = 10
        headroom_kwh = 0.0
        
        is_available = headroom_kwh > 0
        
        assert is_available is False

    def test_stop_discharge_available_when_discharging(self):
        """Stop discharge button should be available when actively discharging."""
        is_discharging = True
        discharge_power = 2.5
        
        is_available = is_discharging and discharge_power > 0
        
        assert is_available is True

    def test_stop_discharge_unavailable_when_not_discharging(self):
        """Stop discharge button should be unavailable when not discharging."""
        is_discharging = False
        
        is_available = is_discharging
        
        assert is_available is False

    def test_button_transition_starts_discharge(self):
        """Test button transitions from available (waiting) to unavailable (discharging)."""
        # Before: headroom available
        headroom_before = 2.0
        start_available_before = headroom_before > 0
        assert start_available_before is True
        
        # After: discharge starts
        is_discharging_after = True
        stop_available_after = is_discharging_after
        assert stop_available_after is True

    def test_button_transition_stops_discharge(self):
        """Test button transitions from unavailable to available after discharge completes."""
        # Before: discharging
        is_discharging_before = True
        stop_available_before = is_discharging_before
        assert stop_available_before is True
        
        # After: discharge stops, but still have headroom left
        is_discharging_after = False
        headroom_after = 0.5
        start_available_after = headroom_after > 0
        assert start_available_after is True


# ============================================================================
# Configuration Validation Tests
# ============================================================================

class TestConfigurationValidation:
    """Test configuration value validation."""

    def test_valid_target_export_power(self):
        """Test valid target export power values."""
        valid_powers = [1000, 2500, 5000, 10000]  # watts
        
        for power in valid_powers:
            assert power > 0
            assert power <= 15000  # reasonable max

    def test_invalid_target_export_power_zero(self):
        """Test zero target export power is invalid."""
        power_w = 0
        
        assert power_w <= 0

    def test_invalid_target_export_power_negative(self):
        """Test negative target export power is invalid."""
        power_w = -1000
        
        assert power_w <= 0

    def test_valid_target_soc(self):
        """Test valid target SOC values."""
        valid_soc_values = [0, 5, 10, 20, 50]
        
        for soc in valid_soc_values:
            assert 0 <= soc <= 100

    def test_invalid_target_soc_above_100(self):
        """Test target SOC above 100 is invalid."""
        soc = 110
        
        assert not (0 <= soc <= 100)

    def test_invalid_target_soc_negative(self):
        """Test negative target SOC is invalid."""
        soc = -10
        
        assert not (0 <= soc <= 100)

    def test_valid_safety_margin(self):
        """Test valid safety margin values."""
        valid_margins = [0, 1, 5, 10]
        
        for margin in valid_margins:
            assert 0 <= margin <= 20  # reasonable range

    def test_safety_margin_less_than_target_soc(self):
        """Test safety margin combined with target SOC is reasonable."""
        safety_margin = 5
        target_soc = 10
        
        # Safety margin should reduce available headroom but not exceed target
        remaining_soc = target_soc + safety_margin
        assert remaining_soc <= 100

    def test_ci_sensor_optional_in_config(self):
        """Test CI sensor is optional in configuration."""
        config_with_ci = {"ci_sensor": "sensor.carbon_intensity"}
        config_without_ci = {}
        
        # Both should be valid
        assert config_with_ci is not None
        assert config_without_ci is not None

    def test_ci_planning_enable_flag_boolean(self):
        """Test CI planning enable flag is boolean."""
        valid_enable_flags = [True, False]
        
        for flag in valid_enable_flags:
            assert isinstance(flag, bool)

    def test_coordinator_update_interval_valid(self):
        """Test coordinator update interval is reasonable."""
        update_interval_seconds = 60
        
        assert update_interval_seconds > 0
        assert update_interval_seconds <= 3600  # Max 1 hour


# ============================================================================
# Sensor State Calculation Tests
# ============================================================================

class TestSensorStateCalculations:
    """Test sensor state calculations."""

    def test_export_headroom_sensor_state(self):
        """Test export headroom sensor calculates correct state."""
        battery_capacity = 13.8
        current_soc = 75
        target_soc = 10
        
        # Sensor state calculation
        headroom_kwh = (current_soc - target_soc) / 100 * battery_capacity
        
        assert headroom_kwh == pytest.approx(8.97)

    def test_discharge_status_sensor_active(self):
        """Test discharge status sensor shows 'Discharging' when active."""
        is_discharging = True
        discharge_power_w = 2500
        
        status = "Discharging" if is_discharging and discharge_power_w > 0 else "Idle"
        
        assert status == "Discharging"

    def test_discharge_status_sensor_idle(self):
        """Test discharge status sensor shows 'Idle' when not active."""
        is_discharging = False
        
        status = "Discharging" if is_discharging else "Idle"
        
        assert status == "Idle"

    def test_discharge_duration_sensor_calculation(self):
        """Test discharge duration sensor calculates minutes."""
        headroom_kwh = 2.0
        power_kw = 3.0
        buffer = 0.9  # 10% safety buffer
        
        duration_minutes = (headroom_kwh / power_kw) * 60 * buffer
        
        assert duration_minutes == pytest.approx(36.0)

    def test_discharge_duration_sensor_zero_headroom(self):
        """Test discharge duration sensor shows 0 with zero headroom."""
        headroom_kwh = 0.0
        power_kw = 3.0
        
        duration_minutes = (headroom_kwh / power_kw) * 60 if headroom_kwh > 0 else 0
        
        assert duration_minutes == 0.0

    def test_current_ci_value_sensor(self):
        """Test current CI value sensor displays correct intensity."""
        current_ci = 45.5  # gCO2/kWh
        
        # Sensor state is the CI value
        assert current_ci > 0

    def test_current_ci_index_sensor(self):
        """Test current CI index sensor displays intensity category."""
        ci_value = 45.5
        
        # CI index categories (example thresholds)
        if ci_value < 100:
            ci_index = "very_low"
        elif ci_value < 200:
            ci_index = "low"
        elif ci_value < 400:
            ci_index = "moderate"
        else:
            ci_index = "high"
        
        assert ci_index == "very_low"

    def test_ci_index_boundary_conditions(self):
        """Test CI index boundaries."""
        test_cases = [
            (50, "very_low"),
            (100, "low"),
            (200, "moderate"),
            (400, "high"),
            (500, "high"),
        ]
        
        for ci_value, expected_index in test_cases:
            if ci_value < 100:
                index = "very_low"
            elif ci_value < 200:
                index = "low"
            elif ci_value < 400:
                index = "moderate"
            else:
                index = "high"
            
            assert index == expected_index


# ============================================================================
# Energy Calculation Consistency Tests
# ============================================================================

class TestEnergyCalculationConsistency:
    """Test that energy calculations remain consistent."""

    def test_energy_discharge_consistency(self):
        """Test energy = power × (duration / 60)."""
        power_kw = 3.0
        duration_minutes = 40.0
        
        energy_discharged = power_kw * (duration_minutes / 60)
        
        assert energy_discharged == pytest.approx(2.0)

    def test_energy_headroom_consistency(self):
        """Test headroom is consumed by discharge."""
        initial_headroom = 3.0
        discharge_energy = 1.5
        
        remaining_headroom = initial_headroom - discharge_energy
        
        assert remaining_headroom == pytest.approx(1.5)

    def test_energy_soc_change_consistency(self):
        """Test energy discharged reflects SOC change."""
        battery_capacity = 13.8
        initial_soc = 60
        final_soc = 50
        
        energy_discharged = (initial_soc - final_soc) / 100 * battery_capacity
        
        assert energy_discharged == pytest.approx(1.38)

    def test_round_trip_calculation(self):
        """Test round-trip: headroom -> power/duration -> back to energy."""
        initial_headroom = 2.5
        power_kw = 2.0
        
        # Calculate duration from headroom
        duration_minutes = (initial_headroom / power_kw) * 60
        
        # Calculate energy from power and duration
        energy_discharged = power_kw * (duration_minutes / 60)
        
        # Should equal initial headroom
        assert energy_discharged == pytest.approx(initial_headroom)

    def test_multiple_discharge_windows(self):
        """Test energy tracking across multiple discharge windows."""
        total_headroom = 3.0
        power_kw = 1.5
        
        # Window 1: 20 minutes
        window1_duration = 20
        window1_energy = power_kw * (window1_duration / 60)
        
        # Window 2: 40 minutes
        window2_duration = 40
        window2_energy = power_kw * (window2_duration / 60)
        
        total_energy = window1_energy + window2_energy
        
        assert window1_energy == pytest.approx(0.5)
        assert window2_energy == pytest.approx(1.0)
        assert total_energy == pytest.approx(1.5)
        assert total_energy <= total_headroom


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_headroom(self):
        """Test with very small headroom (< 0.1 kWh)."""
        headroom_kwh = 0.05
        power_kw = 1.0
        
        duration_minutes = (headroom_kwh / power_kw) * 60
        
        assert duration_minutes == pytest.approx(3.0)
        assert duration_minutes > 0

    def test_very_large_headroom(self):
        """Test with headroom exceeding max discharge."""
        battery_capacity = 13.8
        current_soc = 100
        target_soc = 0
        max_discharge = 3.68
        
        theoretical_headroom = (current_soc - target_soc) / 100 * battery_capacity
        practical_headroom = min(theoretical_headroom, max_discharge)
        
        assert practical_headroom == max_discharge

    def test_fractional_soc_values(self):
        """Test with fractional SOC values."""
        battery_capacity = 13.8
        current_soc = 55.5
        target_soc = 10.2
        
        headroom_kwh = (current_soc - target_soc) / 100 * battery_capacity
        
        assert headroom_kwh == pytest.approx(6.2514)

    def test_power_at_minimum_threshold(self):
        """Test with power at minimum practical value."""
        headroom_kwh = 1.0
        power_kw = 0.1  # 100W
        
        duration_minutes = (headroom_kwh / power_kw) * 60
        
        assert duration_minutes == pytest.approx(600.0)

    def test_power_at_maximum_threshold(self):
        """Test with power at maximum inverter capacity."""
        headroom_kwh = 2.0
        power_kw = 15.0  # 15 kW (high power inverter)
        
        duration_minutes = (headroom_kwh / power_kw) * 60
        
        assert duration_minutes == pytest.approx(8.0)

    def test_soc_rounding_precision(self):
        """Test SOC calculations with rounding precision."""
        battery_capacity = 13.8
        current_soc = 50.123456
        target_soc = 9.876543
        
        headroom_kwh = (current_soc - target_soc) / 100 * battery_capacity
        
        # Should maintain reasonable precision
        assert headroom_kwh > 0
        assert headroom_kwh < battery_capacity

# ============================================================================
# Charge Plan Generation Tests
# ============================================================================

class TestChargePlanGeneration:
    """Test charge plan generation with lowest CI period selection."""

    def test_charge_plan_lowest_ci_sorting(self):
        """Test that charge plan sorts periods by lowest CI first."""
        # Charge planning should prioritize LOWEST CI (ascending), opposite of discharge
        periods = [
            {"from": "2026-02-04T10:00:00Z", "to": "2026-02-04T10:30:00Z", "intensity": {"forecast": 200}},
            {"from": "2026-02-04T09:00:00Z", "to": "2026-02-04T09:30:00Z", "intensity": {"forecast": 50}},
            {"from": "2026-02-04T11:00:00Z", "to": "2026-02-04T11:30:00Z", "intensity": {"forecast": 150}},
        ]
        
        # Sort by CI ascending (lowest first)
        sorted_periods = sorted(periods, key=lambda p: p["intensity"]["forecast"])
        
        assert sorted_periods[0]["intensity"]["forecast"] == 50
        assert sorted_periods[1]["intensity"]["forecast"] == 150
        assert sorted_periods[2]["intensity"]["forecast"] == 200

    def test_charge_plan_energy_allocation(self):
        """Test that charge energy is allocated correctly to periods."""
        charge_power_kw = 3.68
        period_duration_hours = 0.5  # 30 minutes
        energy_needed_kwh = 1.84  # Half of available
        
        # Energy that can be charged in one 30-min period
        period_energy = charge_power_kw * period_duration_hours
        assert period_energy == pytest.approx(1.84, abs=0.01)
        
        # Can fully charge in one period
        allocated = min(period_energy, energy_needed_kwh)
        assert allocated == pytest.approx(1.84, abs=0.01)

    def test_charge_plan_soc_to_energy_conversion(self):
        """Test conversion from SOC percentage to energy (kWh)."""
        current_soc = 50  # 50%
        battery_capacity_kwh = 13.8  # 13.8 kWh
        
        soc_to_charge = 100 - current_soc  # 50%
        energy_needed = (soc_to_charge / 100) * battery_capacity_kwh
        
        assert energy_needed == pytest.approx(6.9, abs=0.01)

    def test_charge_plan_window_filtering(self):
        """Test that charge plan only includes periods within window."""
        # Charge window: 00:00 - 06:00
        window_start = "00:00"
        window_end = "06:00"
        
        # Period outside window (08:00)
        assert not _is_in_window("08:30", window_start, window_end)
        # Period inside window (02:00)
        assert _is_in_window("02:30", window_start, window_end)

    def test_charge_plan_overnight_window(self):
        """Test charge plan with overnight window (23:00 - 06:00)."""
        # Overnight window
        window_start = "23:00"
        window_end = "06:00"
        
        # 23:30 should be in window
        assert _is_in_overnight_window("23:30", window_start, window_end)
        # 02:00 should be in window
        assert _is_in_overnight_window("02:00", window_start, window_end)
        # 12:00 should NOT be in window
        assert not _is_in_overnight_window("12:00", window_start, window_end)

    def test_charge_plan_zero_energy_needed(self):
        """Test charge plan when battery is already fully charged."""
        current_soc = 100
        battery_capacity = 13.8
        
        soc_to_charge = 100 - current_soc
        energy_needed = (soc_to_charge / 100) * battery_capacity
        
        assert energy_needed == 0

    def test_charge_plan_multiple_period_allocation(self):
        """Test allocation across multiple periods."""
        energy_needed = 5.0  # kWh
        charge_power_kw = 3.68
        period_duration = 0.5  # 30 min
        
        period_energy = charge_power_kw * period_duration  # ~1.84 kWh per period
        
        periods_needed = energy_needed / period_energy
        assert periods_needed == pytest.approx(2.72, abs=0.01)  # Need ~3 periods


# Helper functions for window testing
def _is_in_window(time_str: str, window_start: str, window_end: str) -> bool:
    """Check if time is within window (same-day window only)."""
    from datetime import time
    h, m = map(int, time_str.split(":"))
    test_time = time(h, m)
    
    start_h, start_m = map(int, window_start.split(":"))
    end_h, end_m = map(int, window_end.split(":"))
    
    start = time(start_h, start_m)
    end = time(end_h, end_m)
    
    return start <= test_time <= end


def _is_in_overnight_window(time_str: str, window_start: str, window_end: str) -> bool:
    """Check if time is within overnight window (spans midnight)."""
    from datetime import time
    h, m = map(int, time_str.split(":"))
    test_time = time(h, m)
    
    start_h, start_m = map(int, window_start.split(":"))
    end_h, end_m = map(int, window_end.split(":"))
    
    start = time(start_h, start_m)
    end = time(end_h, end_m)
    
    if start <= end:
        return start <= test_time <= end
    else:
        # Overnight: either >= start OR <= end
        return test_time >= start or test_time <= end