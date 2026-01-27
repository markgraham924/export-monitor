"""Button entities for Energy Export Monitor."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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

        discharge_needed = self.coordinator.data.get("discharge_needed", 0)
        min_soc = self.coordinator.data.get("min_soc", 20)

        if discharge_needed <= 0:
            _LOGGER.info("No discharge needed at this time")
            return

        # Call the start_discharge service
        await self.hass.services.async_call(
            DOMAIN,
            "start_discharge",
            {
                "power": int(discharge_needed),
                "cutoff_soc": int(min_soc),
            },
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
