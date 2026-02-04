"""Switch entities for Energy Export Monitor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLE_AUTO_DISCHARGE,
    DEFAULT_ENABLE_AUTO_DISCHARGE,
    DOMAIN,
)
from .coordinator import ExportMonitorCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    coordinator: ExportMonitorCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            EnableAutoDischargeSwitch(coordinator, entry),
        ]
    )


class ExportMonitorSwitch(CoordinatorEntity, SwitchEntity):
    """Base switch entity for Export Monitor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the switch."""
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        config_data = {**self._entry.data, **self._entry.options}
        config_data[self._key] = True
        self.hass.config_entries.async_update_entry(self._entry, data=config_data)
        await self.hass.config_entries.async_reload(self._entry.entry_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        config_data = {**self._entry.data, **self._entry.options}
        config_data[self._key] = False
        self.hass.config_entries.async_update_entry(self._entry, data=config_data)
        await self.hass.config_entries.async_reload(self._entry.entry_id)

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        config_data = {**self._entry.data, **self._entry.options}
        return config_data.get(self._key, False)


class EnableAutoDischargeSwitch(ExportMonitorSwitch):
    """Switch to enable/disable auto-discharge."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the auto-discharge enable switch."""
        super().__init__(
            coordinator,
            entry,
            CONF_ENABLE_AUTO_DISCHARGE,
            "Enable Auto-Discharge",
            "mdi:battery-auto",
        )
