"""Time platform for Dyson integration: the day a BLE light works to."""

from __future__ import annotations

import logging
from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DysonBLEDataUpdateCoordinator
from .entity import DysonBLEEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the day start and day end of a BLE light."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    if isinstance(entry_data, dict) and entry_data.get("is_ble"):
        coordinator: DysonBLEDataUpdateCoordinator = entry_data["ble_coordinator"]
        async_add_entities(
            [
                DysonBLEDayTime(coordinator, end=False),
                DysonBLEDayTime(coordinator, end=True),
            ],
            True,
        )


class DysonBLEDayTime(DysonBLEEntity, TimeEntity):
    """When the lamp's day starts or ends.

    Daylight mode moves the lamp's colour temperature through this day: it
    begins its rise at the start and settles to a warm, dim light after the
    end.  The lamp fills these from sunrise and sunset at its location, and
    the MyDyson app's "custom daytime" writes its own.  Setting one here does
    the same, and the lamp acts on it at once.
    """

    coordinator: DysonBLEDataUpdateCoordinator

    def __init__(self, coordinator: DysonBLEDataUpdateCoordinator, end: bool) -> None:
        """Initialise the entity for the start of the day, or for its end."""
        super().__init__(coordinator)
        self._end = end
        self._key = "day_end_minutes" if end else "day_start_minutes"
        self._attr_name = "Day end" if end else "Day start"
        self._attr_icon = "mdi:weather-sunset-down" if end else "mdi:weather-sunset-up"
        self._attr_unique_id = (
            f"{coordinator.serial_number}_{'day_end' if end else 'day_start'}"
        )

    @property
    def native_value(self) -> time | None:
        """Return the time the lamp holds, or None if it has no day."""
        data = self.coordinator.data
        minutes = data.get(self._key) if data else None
        if minutes is None or not 0 <= minutes < 1440:  # noqa: PLR2004
            return None
        return time(hour=minutes // 60, minute=minutes % 60)

    async def async_set_value(self, value: time) -> None:
        """Write the time to the lamp."""
        dev = self.coordinator.ble_device
        if dev is None:
            raise HomeAssistantError(
                f"No BLE device available for {self.coordinator.serial_number}"
            )
        try:
            await dev.set_day(self._end, value.hour * 60 + value.minute)
        except RuntimeError as err:
            raise HomeAssistantError(str(err)) from err
