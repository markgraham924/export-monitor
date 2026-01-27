"""Number entities for Energy Export Monitor."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_MIN_SOC,
    CONF_SAFETY_MARGIN,
    CONF_TARGET_EXPORT,
    DEFAULT_MIN_SOC,
    DEFAULT_SAFETY_MARGIN,
    DEFAULT_TARGET_EXPORT,
    DOMAIN,
)
from .coordinator import ExportMonitorCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator: ExportMonitorCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            TargetExportNumber(coordinator, entry),
            MinimumSOCNumber(coordinator, entry),
            SafetyMarginNumber(coordinator, entry),
        ]
    )


class ExportMonitorNumber(CoordinatorEntity, NumberEntity):
    """Base number entity for Export Monitor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        # Update the config entry options
        new_options = {**self.coordinator.entry.options, self._key: value}
        self.hass.config_entries.async_update_entry(
            self.coordinator.entry, options=new_options
        )
        self._attr_native_value = value
        self.async_write_ha_state()

        # Trigger a coordinator refresh
        await self.coordinator.async_request_refresh()


class TargetExportNumber(ExportMonitorNumber):
    """Number entity for target grid export power."""

    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 10000
    _attr_native_step = 100

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the target export number."""
        super().__init__(
            coordinator,
            entry,
            CONF_TARGET_EXPORT,
            "Target Export",
            "mdi:transmission-tower-export",
        )
        config_data = {**entry.data, **entry.options}
        self._attr_native_value = config_data.get(
            CONF_TARGET_EXPORT, DEFAULT_TARGET_EXPORT
        )


class MinimumSOCNumber(ExportMonitorNumber):
    """Number entity for minimum battery SOC."""

    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the minimum SOC number."""
        super().__init__(
            coordinator,
            entry,
            CONF_MIN_SOC,
            "Minimum SOC",
            "mdi:battery-low",
        )
        config_data = {**entry.data, **entry.options}
        self._attr_native_value = config_data.get(CONF_MIN_SOC, DEFAULT_MIN_SOC)


class SafetyMarginNumber(ExportMonitorNumber):
    """Number entity for safety margin."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 20
    _attr_native_step = 0.1

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the safety margin number."""
        super().__init__(
            coordinator,
            entry,
            CONF_SAFETY_MARGIN,
            "Safety Margin",
            "mdi:shield-alert",
        )
        config_data = {**entry.data, **entry.options}
        self._attr_native_value = config_data.get(
            CONF_SAFETY_MARGIN, DEFAULT_SAFETY_MARGIN
        )
