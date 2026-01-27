"""Sensor entities for Energy Export Monitor."""
from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CURRENT_PV,
    ATTR_CURRENT_THRESHOLD,
    ATTR_DISCHARGE_NEEDED,
    ATTR_FORECAST_PV,
    ATTR_GRID_EXPORT,
    ATTR_SAFE_EXPORT_LIMIT,
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
            SafeExportLimitSensor(coordinator, entry),
            DischargeNeededSensor(coordinator, entry),
            GridExportSensor(coordinator, entry),
            DischargeStatusSensor(coordinator, entry),
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


class SafeExportLimitSensor(ExportMonitorSensor):
    """Sensor showing the safe export limit."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
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
            "safe_export_limit",
            "Safe Export Limit",
            "mdi:shield-check",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get(ATTR_SAFE_EXPORT_LIMIT)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        return {
            ATTR_CURRENT_PV: self.coordinator.data.get(ATTR_CURRENT_PV),
            ATTR_FORECAST_PV: self.coordinator.data.get(ATTR_FORECAST_PV),
        }


class DischargeNeededSensor(ExportMonitorSensor):
    """Sensor showing the discharge power needed."""

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
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        return {
            "current_soc": self.coordinator.data.get("current_soc"),
            "min_soc": self.coordinator.data.get("min_soc"),
        }


class GridExportSensor(ExportMonitorSensor):
    """Sensor showing current grid export."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the grid export sensor."""
        super().__init__(
            coordinator,
            entry,
            "grid_export",
            "Grid Export",
            "mdi:transmission-tower-export",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get(ATTR_GRID_EXPORT)
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
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        return {
            ATTR_CURRENT_THRESHOLD: self.coordinator.data.get(ATTR_CURRENT_THRESHOLD),
            ATTR_SAFE_EXPORT_LIMIT: self.coordinator.data.get(ATTR_SAFE_EXPORT_LIMIT),
        }
