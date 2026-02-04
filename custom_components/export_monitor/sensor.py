"""Sensor entities for Energy Export Monitor."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower, PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CURRENT_CI_INDEX,
    ATTR_CURRENT_CI_VALUE,
    ATTR_CURRENT_PV,
    ATTR_DISCHARGE_NEEDED,
    ATTR_DISCHARGE_PLAN,
    ATTR_DISCHARGE_PLAN_TODAY,
    ATTR_DISCHARGE_PLAN_TOMORROW,
    ATTR_CHARGE_PLAN_TODAY,
    ATTR_CHARGE_PLAN_TOMORROW,
    ATTR_EXPORT_ALLOWED,
    ATTR_EXPORT_HEADROOM,
    ATTR_EXPORTED_TODAY,
    ATTR_FORECAST_PV,
    DOMAIN,
)
from .coordinator import ExportMonitorCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator: ExportMonitorCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        ExportHeadroomSensor(coordinator, entry),
        DischargeNeededSensor(coordinator, entry),
        ExportedTodaySensor(coordinator, entry),
        DischargeStatusSensor(coordinator, entry),
        CalculatedDurationSensor(coordinator, entry),
        DischargeCompleteSensor(coordinator, entry),
        ReserveSOCTargetSensor(coordinator, entry),
        ReserveSOCStatusSensor(coordinator, entry),
        CurrentCIValueSensor(coordinator, entry),
        CurrentCIIndexSensor(coordinator, entry),
        DischargePlanSensor(coordinator, entry),
        DischargePlanTodaySensor(coordinator, entry),
        DischargePlanTomorrowSensor(coordinator, entry),
    ]

    # Diagnostic Sensors
    diagnostics = [
        GenericDiagnosticSensor(coordinator, entry, ATTR_CURRENT_PV, "Current PV", "mdi:solar-power", UnitOfPower.WATT, SensorDeviceClass.POWER),
        GenericDiagnosticSensor(coordinator, entry, ATTR_FORECAST_PV, "Forecast PV Today", "mdi:solar-power-variant", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY),
        GenericDiagnosticSensor(coordinator, entry, ATTR_EXPORT_ALLOWED, "Export Allowed", "mdi:export-variant"),
        GenericDiagnosticSensor(coordinator, entry, "current_soc", "Current SOC", "mdi:battery", PERCENTAGE, SensorDeviceClass.BATTERY),
        GenericDiagnosticSensor(coordinator, entry, "min_soc", "Minimum SOC", "mdi:battery-arrow-down", PERCENTAGE, SensorDeviceClass.BATTERY),
        GenericDiagnosticSensor(coordinator, entry, "observe_reserve_soc", "Observe Reserve SOC", "mdi:shield-search"),
        GenericDiagnosticSensor(coordinator, entry, "reserve_limit_reached", "Reserve Limit Reached", "mdi:shield-alert"),
    ]

    # Plan Detail Sensors
    plan_details = [
        PlanEnergySensor(coordinator, entry, ATTR_DISCHARGE_PLAN, "Total Plan Energy"),
        PlanEnergySensor(coordinator, entry, ATTR_DISCHARGE_PLAN_TODAY, "Plan Energy Today"),
        PlanEnergySensor(coordinator, entry, ATTR_DISCHARGE_PLAN_TOMORROW, "Plan Energy Tomorrow"),
        PlanWindowSensor(coordinator, entry, ATTR_DISCHARGE_PLAN, "Plan Windows Total"),
        PlanWindowSensor(coordinator, entry, ATTR_DISCHARGE_PLAN_TODAY, "Plan Windows Today"),
        PlanWindowSensor(coordinator, entry, ATTR_DISCHARGE_PLAN_TOMORROW, "Plan Windows Tomorrow"),
        ChargePlanSensor(coordinator, entry, ATTR_CHARGE_PLAN_TODAY, "Charge Plan Today"),
        ChargePlanSensor(coordinator, entry, ATTR_CHARGE_PLAN_TOMORROW, "Charge Plan Tomorrow"),
    ]

    async_add_entities(sensors + diagnostics + plan_details)


class ExportMonitorSensor(CoordinatorEntity, SensorEntity):
    """Base sensor entity for Export Monitor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Energy Export Monitor",
            manufacturer="Energy Export Monitor",
            model="v1",
        )


class ExportHeadroomSensor(ExportMonitorSensor):
    """Sensor showing remaining export headroom (kWh)."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the safe export limit sensor."""
        super().__init__(
            coordinator,
            entry,
            "export_headroom",
            "Export Headroom",
            "mdi:shield-check",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get(ATTR_EXPORT_HEADROOM)
        return None


class DischargeNeededSensor(ExportMonitorSensor):
    """Sensor showing recommended discharge power (1h window assumption)."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the discharge needed sensor."""
        super().__init__(
            coordinator,
            entry,
            "discharge_needed",
            "Discharge Needed",
            "mdi:battery-arrow-up-outline",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get(ATTR_DISCHARGE_NEEDED)
        return None


class ExportedTodaySensor(ExportMonitorSensor):
    """Sensor showing total exported energy today."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the grid export sensor."""
        super().__init__(
            coordinator,
            entry,
            "exported_today",
            "Exported Today",
            "mdi:transmission-tower-export",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get(ATTR_EXPORTED_TODAY)
        return None


class DischargeStatusSensor(ExportMonitorSensor):
    """Sensor showing discharge status."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the discharge status sensor."""
        super().__init__(
            coordinator,
            entry,
            "discharge_status",
            "Discharge Status",
            "mdi:information",
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.discharge_active:
            return "Active"
        
        if self.coordinator.data:
            discharge_needed = self.coordinator.data.get(ATTR_DISCHARGE_NEEDED, 0)
            if discharge_needed > 0:
                return "Needed"
        
        return "Idle"


class CalculatedDurationSensor(ExportMonitorSensor):
    """Sensor showing calculated discharge duration in minutes."""

    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the calculated duration sensor."""
        super().__init__(
            coordinator,
            entry,
            "calculated_duration",
            "Calculated Duration",
            "mdi:timer",
        )

    @property
    def native_value(self) -> float | None:
        """Return the calculated discharge duration in minutes."""
        if self.coordinator.data:
            return self.coordinator.data.get("calculated_duration")
        return None


class DischargeCompleteSensor(ExportMonitorSensor):
    """Sensor showing if discharge target has been reached."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the discharge complete sensor."""
        super().__init__(
            coordinator,
            entry,
            "discharge_complete",
            "Discharge Complete",
            "mdi:check-circle",
        )

    @property
    def native_value(self) -> str:
        """Return whether discharge is complete."""
        if not self.coordinator.data:
            return "Unknown"
        
        if self.coordinator.data.get("discharge_complete", False):
            return "Complete"
        elif self.coordinator.discharge_active:
            return "In Progress"
        else:
            return "Not Started"


class ReserveSOCTargetSensor(ExportMonitorSensor):
    """Sensor showing reserve SOC target value."""

    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the reserve SOC target sensor."""
        super().__init__(
            coordinator,
            entry,
            "reserve_soc_target",
            "Reserve SOC Target",
            "mdi:battery-lock",
        )

    @property
    def native_value(self) -> float | None:
        """Return the reserve SOC target value."""
        if self.coordinator.data:
            return self.coordinator.data.get("reserve_soc_target")
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data.get("reserve_soc_target") is not None


class ReserveSOCStatusSensor(ExportMonitorSensor):
    """Sensor showing reserve SOC monitoring status."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the reserve SOC status sensor."""
        super().__init__(
            coordinator,
            entry,
            "reserve_soc_status",
            "Reserve SOC Status",
            "mdi:shield-alert",
        )

    @property
    def native_value(self) -> str:
        """Return the reserve SOC monitoring status."""
        if not self.coordinator.data:
            return "Unknown"
        
        observe_reserve = self.coordinator.data.get("observe_reserve_soc", False)
        if not observe_reserve:
            return "Monitoring Disabled"
        
        reserve_limit_reached = self.coordinator.data.get("reserve_limit_reached", False)
        if reserve_limit_reached:
            return "Limit Reached"
        else:
            return "Normal"


class CurrentCIValueSensor(ExportMonitorSensor):
    """Sensor showing current Carbon Intensity value (gCO2/kWh)."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the current CI value sensor."""
        super().__init__(
            coordinator,
            entry,
            "current_ci_value",
            "Current Carbon Intensity",
            "mdi:leaf",
        )

    @property
    def native_value(self) -> int | None:
        """Return current CI value."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(ATTR_CURRENT_CI_VALUE)


class CurrentCIIndexSensor(ExportMonitorSensor):
    """Sensor showing current Carbon Intensity index (very low/low/etc)."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the current CI index sensor."""
        super().__init__(
            coordinator,
            entry,
            "current_ci_index",
            "Current Carbon Intensity Index",
            "mdi:leaf-circle",
        )

    @property
    def native_value(self) -> str | None:
        """Return current CI index."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(ATTR_CURRENT_CI_INDEX)


class DischargePlanSensor(ExportMonitorSensor):
    """Sensor showing optimized discharge plan summary."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the discharge plan sensor."""
        super().__init__(
            coordinator,
            entry,
            "discharge_plan",
            "Discharge Plan",
            "mdi:battery-charging-outline",
        )

    @property
    def native_value(self) -> str:
        """Return detailed plan windows."""
        if not self.coordinator.data:
            return "No plan"

        plan = self.coordinator.data.get(ATTR_DISCHARGE_PLAN, [])
        if not plan:
            return "No plan"

        windows = []
        for p in plan:
            try:
                from_time = p.get("from", "")
                to_time = p.get("to", "")
                energy = p.get("energy_kwh", 0)
                if from_time and to_time:
                    from_hour = from_time.split("T")[1][:5] if "T" in from_time else ""
                    to_hour = to_time.split("T")[1][:5] if "T" in to_time else ""
                    if from_hour and to_hour:
                        windows.append(f"{from_hour} - {to_hour} {energy:.2f}kWh")
            except (ValueError, IndexError, AttributeError):
                continue

        if not windows:
            return "No plan"
        return "\n".join(windows)


class DischargePlanTodaySensor(ExportMonitorSensor):
    """Sensor showing discharge plan for today summary."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the discharge plan today sensor."""
        super().__init__(
            coordinator, entry, "discharge_plan_today", "Discharge Plan Today", "mdi:battery-charging-outline"
        )

    @property
    def native_value(self) -> str:
        if not self.coordinator.data:
            return "No plan"
        plan = self.coordinator.data.get(ATTR_DISCHARGE_PLAN_TODAY, [])
        if not plan:
            return "No plan"
        
        windows = []
        for p in plan:
            try:
                from_time = p.get("from", "")
                to_time = p.get("to", "")
                energy = p.get("energy_kwh", 0)
                if from_time and to_time:
                    from_hour = from_time.split("T")[1][:5] if "T" in from_time else ""
                    to_hour = to_time.split("T")[1][:5] if "T" in to_time else ""
                    if from_hour and to_hour:
                        windows.append(f"{from_hour} - {to_hour} {energy:.2f}kWh")
            except (ValueError, IndexError, AttributeError):
                continue
        
        if not windows:
            return "No plan"
        return "\n".join(windows)


class DischargePlanTomorrowSensor(ExportMonitorSensor):
    """Sensor showing discharge plan for tomorrow summary."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the discharge plan tomorrow sensor."""
        super().__init__(
            coordinator, entry, "discharge_plan_tomorrow", "Discharge Plan Tomorrow", "mdi:battery-charging-outline"
        )

    @property
    def native_value(self) -> str:
        if not self.coordinator.data:
            return "No plan"
        plan = self.coordinator.data.get(ATTR_DISCHARGE_PLAN_TOMORROW, [])
        if not plan:
            return "No plan"
        
        windows = []
        for p in plan:
            try:
                from_time = p.get("from", "")
                to_time = p.get("to", "")
                energy = p.get("energy_kwh", 0)
                if from_time and to_time:
                    from_hour = from_time.split("T")[1][:5] if "T" in from_time else ""
                    to_hour = to_time.split("T")[1][:5] if "T" in to_time else ""
                    if from_hour and to_hour:
                        windows.append(f"{from_hour} - {to_hour} {energy:.2f}kWh")
            except (ValueError, IndexError, AttributeError):
                continue
        
        if not windows:
            return "No plan"
        return "\n".join(windows)


class GenericDiagnosticSensor(ExportMonitorSensor):
    """Generic diagnostic sensor for attributes."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
        unit: str | None = None,
        device_class: SensorDeviceClass | None = None,
    ) -> None:
        super().__init__(coordinator, entry, f"diag_{key}", name, icon)
        self._data_key = key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self._data_key) if self.coordinator.data else None


class PlanEnergySensor(ExportMonitorSensor):
    """Sensor for plan energy total."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ExportMonitorCoordinator, entry: ConfigEntry, plan_key: str, name: str) -> None:
        super().__init__(coordinator, entry, f"{plan_key}_energy", name, "mdi:lightning-bolt")
        self._plan_key = plan_key

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data: return None
        plan = self.coordinator.data.get(self._plan_key, [])
        return sum(p.get("energy_kwh", 0) for p in plan)


class PlanWindowSensor(ExportMonitorSensor):
    """Sensor for number of plan windows."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ExportMonitorCoordinator, entry: ConfigEntry, plan_key: str, name: str) -> None:
        super().__init__(coordinator, entry, f"{plan_key}_windows", name, "mdi:clock-list")
        self._plan_key = plan_key

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data: return None
        plan = self.coordinator.data.get(self._plan_key, [])
        return len(plan)


class ChargePlanSensor(ExportMonitorSensor):
    """Sensor for charge plan display."""

    def __init__(self, coordinator: ExportMonitorCoordinator, entry: ConfigEntry, plan_key: str, name: str) -> None:
        super().__init__(coordinator, entry, plan_key, name, "mdi:battery-charging")
        self._plan_key = plan_key

    @property
    def native_value(self) -> str | None:
        """Return formatted charge plan windows."""
        if not self.coordinator.data:
            return None
        
        plan = self.coordinator.data.get(self._plan_key, [])
        if not plan:
            return "No charge plan"
        
        # Format each window as "HH:MM - HH:MM 0.60kWh"
        windows = []
        for period in plan:
            try:
                start = period.get("period_start", "")
                end = period.get("period_end", "")
                energy = period.get("energy_kwh", 0)
                
                if start and end:
                    # Extract time portion from ISO format
                    start_time = start.split("T")[1][:5] if "T" in start else start
                    end_time = end.split("T")[1][:5] if "T" in end else end
                    windows.append(f"{start_time} - {end_time} {energy:.2f}kWh")
            except (KeyError, IndexError, AttributeError):
                continue
        
        return "\n".join(windows) if windows else "No windows"

