"""Button entities for Energy Export Monitor."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ExportMonitorCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    coordinator: ExportMonitorCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            StartDischargeButton(coordinator, entry),
            StopDischargeButton(coordinator, entry),
            CalculateDischargeButton(coordinator, entry),
            ResetAutoStatsButton(coordinator, entry),
        ]
    )


class ExportMonitorButton(CoordinatorEntity, ButtonEntity):
    """Base button entity for Export Monitor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Energy Export Monitor",
            manufacturer="Energy Export Monitor",
            model="v1",
        )


class StartDischargeButton(ExportMonitorButton):
    """Button to start battery discharge."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the start discharge button."""
        super().__init__(
            coordinator,
            entry,
            "start_discharge",
            "Start Discharge",
            "mdi:battery-arrow-up",
        )

    async def async_press(self) -> None:
        """Handle button press."""
        if not self.coordinator.data:
            _LOGGER.warning("No coordinator data available")
            return

        headroom = self.coordinator.data.get("export_headroom_kwh", 0)

        if headroom <= 0:
            _LOGGER.info("No export headroom available at this time")
            return

        # Call the start_discharge service (duration calculated automatically)
        await self.hass.services.async_call(
            DOMAIN,
            "start_discharge",
            {},
            blocking=True,
        )


class StopDischargeButton(ExportMonitorButton):
    """Button to stop battery discharge."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the stop discharge button."""
        super().__init__(
            coordinator,
            entry,
            "stop_discharge",
            "Stop Discharge",
            "mdi:battery-arrow-down",
        )

    async def async_press(self) -> None:
        """Handle button press."""
        await self.hass.services.async_call(
            DOMAIN,
            "stop_discharge",
            {},
            blocking=True,
        )


class CalculateDischargeButton(ExportMonitorButton):
    """Button to recalculate discharge requirements."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the calculate button."""
        super().__init__(
            coordinator,
            entry,
            "calculate_discharge",
            "Calculate Discharge",
            "mdi:calculator",
        )

    async def async_press(self) -> None:
        """Handle button press."""
        await self.hass.services.async_call(
            DOMAIN,
            "calculate_discharge",
            {},
            blocking=True,
        )


class ResetAutoStatsButton(ExportMonitorButton):
    """Button to reset auto-control diagnostic counters."""

    def __init__(
        self,
        coordinator: ExportMonitorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            "reset_auto_stats",
            "Reset Auto Stats",
            "mdi:restart",
        )

    async def async_press(self) -> None:
        self.coordinator.reset_auto_stats()
        await self.coordinator.async_request_refresh()
