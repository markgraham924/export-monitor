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
from homeassistant.const import UnitOfEnergy, UnitOfPower
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

    async_add_entities(
        [
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
        ]
    )


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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        return {
            ATTR_CURRENT_PV: self.coordinator.data.get(ATTR_CURRENT_PV),
            ATTR_FORECAST_PV: self.coordinator.data.get(ATTR_FORECAST_PV),
            ATTR_EXPORT_ALLOWED: self.coordinator.data.get(ATTR_EXPORT_ALLOWED),
        }


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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        return {
            "current_soc": self.coordinator.data.get("current_soc"),
            "min_soc": self.coordinator.data.get("min_soc"),
        }


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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        return {
            ATTR_EXPORT_HEADROOM: self.coordinator.data.get(ATTR_EXPORT_HEADROOM),
            ATTR_EXPORT_ALLOWED: self.coordinator.data.get(ATTR_EXPORT_ALLOWED),
        }


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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        return {
            "reserve_soc_target": self.coordinator.data.get("reserve_soc_target"),
            "current_soc": self.coordinator.data.get("current_soc"),
            "observe_reserve_soc": self.coordinator.data.get("observe_reserve_soc"),
            "reserve_limit_reached": self.coordinator.data.get("reserve_limit_reached"),
        }


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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        return {
            "ci_index": self.coordinator.data.get(ATTR_CURRENT_CI_INDEX),
        }


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
    """Sensor showing optimized discharge plan for highest CI periods."""

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
        """Return plan summary."""
        if not self.coordinator.data:
            return "No plan"

        plan = self.coordinator.data.get(ATTR_DISCHARGE_PLAN, [])
        if not plan:
            return "No plan"

        total_energy = sum(p.get("energy_kwh", 0) for p in plan)
        avg_ci = (
            sum(p.get("ci_value", 0) * p.get("energy_kwh", 0) for p in plan) / total_energy
            if total_energy > 0
            else 0
        )

        return f"{len(plan)} windows, {total_energy:.2f} kWh, avg CI {avg_ci:.0f}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed plan."""
        if not self.coordinator.data:
            return {}

        plan = self.coordinator.data.get(ATTR_DISCHARGE_PLAN, [])
        if not plan:
            return {"plan": []}

        return {
            "plan": plan,
            "total_energy_kwh": sum(p.get("energy_kwh", 0) for p in plan),
            "windows": len(plan),
        }

