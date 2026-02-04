"""Tests for Carbon Intensity planning logic."""
import json
from datetime import datetime, timedelta, timezone

import pytest


# Mock CI data for testing - using relative dates to ensure tests pass as time advances
now = datetime.now(timezone.utc)
tomorrow = now + timedelta(days=1)

MOCK_CI_DATA = {
    "regionid": 3,
    "shortname": "Test Region",
    "data": {
        "data": [
            {
                "from": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00Z"),
                "to": (now + timedelta(hours=1, minutes=30)).strftime("%Y-%m-%dT%H:30Z"),
                "intensity": {"forecast": 25, "index": "low"},
            },
            {
                "from": (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:00Z"),
                "to": (now + timedelta(hours=2, minutes=30)).strftime("%Y-%m-%dT%H:30Z"),
                "intensity": {"forecast": 41, "index": "low"},
            },
            {
                "from": (now + timedelta(hours=3)).strftime("%Y-%m-%dT%H:00Z"),
                "to": (now + timedelta(hours=3, minutes=30)).strftime("%Y-%m-%dT%H:30Z"),
                "intensity": {"forecast": 39, "index": "low"},
            },
            {
                "from": (now + timedelta(hours=4)).strftime("%Y-%m-%dT%H:00Z"),
                "to": (now + timedelta(hours=4, minutes=30)).strftime("%Y-%m-%dT%H:30Z"),
                "intensity": {"forecast": 15, "index": "very low"},
            },
            {
                "from": (now + timedelta(hours=5)).strftime("%Y-%m-%dT%H:00Z"),
                "to": (now + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%dT%H:30Z"),
                "intensity": {"forecast": 41, "index": "low"},
            },
            {
                "from": (now + timedelta(hours=6)).strftime("%Y-%m-%dT%H:00Z"),
                "to": (now + timedelta(hours=6, minutes=30)).strftime("%Y-%m-%dT%H:30Z"),
                "intensity": {"forecast": 12, "index": "very low"},
            },
        ]
    },
}


class MockCoordinator:
    """Mock coordinator for testing CI planning logic."""

    def _parse_ci_forecast(self, sensor_state_str: str) -> dict | None:
        """Parse Carbon Intensity forecast JSON from sensor state."""
        try:
            data = json.loads(sensor_state_str)
        except (json.JSONDecodeError, TypeError):
            return None

        if "data" not in data or not isinstance(data.get("data"), dict):
            return None

        periods = data.get("data", {}).get("data", [])
        if not isinstance(periods, list) or len(periods) == 0:
            return None

        return {"periods": periods, "region": data.get("shortname")}

    def _find_highest_ci_periods(self, periods: list[dict], headroom_kwh: float, discharge_power_kw: float) -> list[dict]:
        """Find and rank highest CI periods, build discharge plan within headroom."""
        if not periods or headroom_kwh <= 0 or discharge_power_kw <= 0:
            return []

        now = datetime.now(timezone.utc)
        future_periods = []

        for period in periods:
            try:
                from_time = datetime.fromisoformat(period["from"].replace("Z", "+00:00"))
                to_time = datetime.fromisoformat(period["to"].replace("Z", "+00:00"))
                intensity_forecast = period.get("intensity", {}).get("forecast", 0)
                intensity_index = period.get("intensity", {}).get("index", "unknown")

                if to_time > now:
                    future_periods.append(
                        {
                            "from": from_time,
                            "to": to_time,
                            "duration_minutes": (to_time - from_time).total_seconds() / 60,
                            "ci_value": intensity_forecast,
                            "ci_index": intensity_index,
                        }
                    )
            except (ValueError, KeyError):
                continue

        # Sort by CI value (highest first)
        future_periods.sort(key=lambda x: x["ci_value"], reverse=True)

        # Build plan greedily within headroom
        plan = []
        remaining_headroom = headroom_kwh

        for period in future_periods:
            if remaining_headroom <= 0:
                break

            period_capacity_kwh = discharge_power_kw * (period["duration_minutes"] / 60)
            export_energy = min(period_capacity_kwh, remaining_headroom)
            export_duration = (export_energy / discharge_power_kw) * 60

            plan.append(
                {
                    "from": period["from"].isoformat(),
                    "to": period["to"].isoformat(),
                    "duration_minutes": export_duration,
                    "energy_kwh": export_energy,
                    "ci_value": period["ci_value"],
                    "ci_index": period["ci_index"],
                }
            )

            remaining_headroom -= export_energy

        return plan

    def _get_current_ci_index(self, periods: list[dict]) -> tuple[int | None, str | None]:
        """Get current CI intensity value and index."""
        now = datetime.now(timezone.utc)

        for period in periods:
            try:
                from_time = datetime.fromisoformat(period["from"].replace("Z", "+00:00"))
                to_time = datetime.fromisoformat(period["to"].replace("Z", "+00:00"))

                if from_time <= now < to_time:
                    ci_value = period.get("intensity", {}).get("forecast", None)
                    ci_index = period.get("intensity", {}).get("index", None)
                    return ci_value, ci_index
            except (ValueError, KeyError):
                continue

        return None, None


@pytest.fixture
def coordinator():
    """Provide a mock coordinator."""
    return MockCoordinator()


class TestCIParsing:
    """Test CI forecast data parsing."""

    def test_parse_valid_ci_data(self, coordinator):
        """Test parsing valid CI forecast JSON."""
        ci_json = json.dumps(MOCK_CI_DATA)
        result = coordinator._parse_ci_forecast(ci_json)

        assert result is not None
        assert "periods" in result
        assert "region" in result
        assert result["region"] == "Test Region"
        assert len(result["periods"]) == 6

    def test_parse_invalid_json(self, coordinator):
        """Test parsing invalid JSON."""
        result = coordinator._parse_ci_forecast("not valid json")
        assert result is None

    def test_parse_missing_data_key(self, coordinator):
        """Test parsing data without 'data' key."""
        invalid_data = {"regionid": 3, "shortname": "Test"}
        result = coordinator._parse_ci_forecast(json.dumps(invalid_data))
        assert result is None

    def test_parse_empty_periods(self, coordinator):
        """Test parsing with no periods."""
        invalid_data = {"regionid": 3, "shortname": "Test", "data": {"data": []}}
        result = coordinator._parse_ci_forecast(json.dumps(invalid_data))
        assert result is None

    def test_parse_none_input(self, coordinator):
        """Test parsing None input."""
        result = coordinator._parse_ci_forecast(None)
        assert result is None


class TestPlanGeneration:
    """Test discharge plan generation."""

    def test_plan_sorted_by_ci_highest_first(self, coordinator):
        """Test that plan periods are sorted by CI (highest first)."""
        ci_data = coordinator._parse_ci_forecast(json.dumps(MOCK_CI_DATA))
        plan = coordinator._find_highest_ci_periods(ci_data["periods"], 3.68, 3.0)

        # Verify sorted by CI value (descending)
        ci_values = [p["ci_value"] for p in plan]
        assert ci_values == sorted(ci_values, reverse=True)

    def test_plan_respects_headroom(self, coordinator):
        """Test that total energy in plan doesn't exceed headroom."""
        ci_data = coordinator._parse_ci_forecast(json.dumps(MOCK_CI_DATA))
        headroom = 2.5  # Limited headroom
        plan = coordinator._find_highest_ci_periods(ci_data["periods"], headroom, 3.0)

        total_energy = sum(p["energy_kwh"] for p in plan)
        assert total_energy <= headroom
        assert total_energy > 0

    def test_plan_respects_power_capacity(self, coordinator):
        """Test that each window respects discharge power capacity."""
        ci_data = coordinator._parse_ci_forecast(json.dumps(MOCK_CI_DATA))
        discharge_power = 2.0  # 2 kW
        plan = coordinator._find_highest_ci_periods(ci_data["periods"], 3.0, discharge_power)

        for window in plan:
            # Max energy for a 30-min window at 2kW = 1.0 kWh
            max_possible = discharge_power * (window["duration_minutes"] / 60)
            assert window["energy_kwh"] <= max_possible + 0.01  # Small tolerance for rounding

    def test_plan_empty_zero_headroom(self, coordinator):
        """Test that empty plan is returned for zero headroom."""
        ci_data = coordinator._parse_ci_forecast(json.dumps(MOCK_CI_DATA))
        plan = coordinator._find_highest_ci_periods(ci_data["periods"], 0, 3.0)
        assert plan == []

    def test_plan_empty_zero_power(self, coordinator):
        """Test that empty plan is returned for zero discharge power."""
        ci_data = coordinator._parse_ci_forecast(json.dumps(MOCK_CI_DATA))
        plan = coordinator._find_highest_ci_periods(ci_data["periods"], 3.68, 0)
        assert plan == []

    def test_plan_empty_no_periods(self, coordinator):
        """Test that empty plan is returned for no periods."""
        plan = coordinator._find_highest_ci_periods([], 3.68, 3.0)
        assert plan == []

    def test_plan_greedy_allocation(self, coordinator):
        """Test greedy algorithm prioritizes highest CI periods."""
        ci_data = coordinator._parse_ci_forecast(json.dumps(MOCK_CI_DATA))
        # With limited headroom, should get the highest CI periods first
        plan = coordinator._find_highest_ci_periods(ci_data["periods"], 1.0, 3.0)

        # Should have allocated to the highest CI periods (41, 41, 39 from data)
        expected_high_ci_values = [41, 41, 39]
        actual_ci_values = [p["ci_value"] for p in plan]
        assert actual_ci_values[0] in expected_high_ci_values

    def test_plan_windows_have_required_fields(self, coordinator):
        """Test that plan windows have all required fields."""
        ci_data = coordinator._parse_ci_forecast(json.dumps(MOCK_CI_DATA))
        plan = coordinator._find_highest_ci_periods(ci_data["periods"], 3.68, 3.0)

        required_fields = ["from", "to", "duration_minutes", "energy_kwh", "ci_value", "ci_index"]
        for window in plan:
            for field in required_fields:
                assert field in window


class TestCurrentCI:
    """Test current carbon intensity detection."""

    def test_get_current_ci_valid_period(self, coordinator):
        """Test getting current CI when in a valid period."""
        # Use a period that started in the past and ends in the future
        periods = [
            {
                "from": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
                "to": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(),
                "intensity": {"forecast": 35, "index": "low"},
            }
        ]
        # Convert ISO format strings to include Z
        periods[0]["from"] = periods[0]["from"].replace("+00:00", "Z")
        periods[0]["to"] = periods[0]["to"].replace("+00:00", "Z")

        ci_value, ci_index = coordinator._get_current_ci_index(periods)
        assert ci_value == 35
        assert ci_index == "low"

    def test_get_current_ci_no_valid_period(self, coordinator):
        """Test getting current CI when no period matches."""
        # All periods in the past
        periods = [
            {
                "from": "2026-02-02T10:00Z",
                "to": "2026-02-02T10:30Z",
                "intensity": {"forecast": 35, "index": "low"},
            }
        ]
        ci_value, ci_index = coordinator._get_current_ci_index(periods)
        assert ci_value is None
        assert ci_index is None

    def test_get_current_ci_empty_periods(self, coordinator):
        """Test getting current CI with empty periods list."""
        ci_value, ci_index = coordinator._get_current_ci_index([])
        assert ci_value is None
        assert ci_index is None


class TestRealWorldScenarios:
    """Test realistic export scenarios."""

    def test_scenario_full_capacity_export(self, coordinator):
        """Scenario: Export at full 3.68 kWh capacity."""
        ci_data = coordinator._parse_ci_forecast(json.dumps(MOCK_CI_DATA))
        plan = coordinator._find_highest_ci_periods(ci_data["periods"], 3.68, 3.0)

        total_energy = sum(p["energy_kwh"] for p in plan)
        assert total_energy <= 3.68
        assert len(plan) > 0

    def test_scenario_limited_capacity(self, coordinator):
        """Scenario: Export with only 1.0 kWh available."""
        ci_data = coordinator._parse_ci_forecast(json.dumps(MOCK_CI_DATA))
        plan = coordinator._find_highest_ci_periods(ci_data["periods"], 1.0, 3.0)

        total_energy = sum(p["energy_kwh"] for p in plan)
        assert total_energy <= 1.0
        # Should still prioritize highest CI
        assert plan[0]["ci_value"] >= 39  # Should get one of the high CI periods

    def test_scenario_small_power(self, coordinator):
        """Scenario: Small discharge power (1 kW)."""
        ci_data = coordinator._parse_ci_forecast(json.dumps(MOCK_CI_DATA))
        plan = coordinator._find_highest_ci_periods(ci_data["periods"], 3.68, 1.0)

        total_energy = sum(p["energy_kwh"] for p in plan)
        assert total_energy <= 3.68
        # Should distribute across multiple windows (1 kW over 30 min = 0.5 kWh per window)
        assert len(plan) > 1

    def test_scenario_energy_duration_consistency(self, coordinator):
        """Scenario: Verify energy = power * duration."""
        ci_data = coordinator._parse_ci_forecast(json.dumps(MOCK_CI_DATA))
        discharge_power_kw = 3.0
        plan = coordinator._find_highest_ci_periods(ci_data["periods"], 3.68, discharge_power_kw)

        for window in plan:
            calculated_energy = discharge_power_kw * (window["duration_minutes"] / 60)
            # Allow small rounding tolerance
            assert abs(window["energy_kwh"] - calculated_energy) < 0.01
