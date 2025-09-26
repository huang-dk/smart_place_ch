from homeassistant.components.light import EventEntity
from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up doorbell."""

    hub = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([DoorBell(hub)])

    class DoorBell(EventEntity):
        _attr_device_class = EventDeviceClass.DOORBELL
        _attr_event_types = ["single_press"]

        def __init__(self, coordinator: DLightDataUpdateCoordinator) -> None:
            """Initialize a doorbell."""
            super().__init__(coordinator=coordinator)
            LOGGER.debug("light.__init__: %s", coordinator.device_id)

            self._attr_min_color_temp_kelvin = 2600
            self._attr_max_color_temp_kelvin = 6000

            self._attr_unique_id = coordinator.device_id
            self._attr_name = coordinator.name
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._attr_color_mode = ColorMode.COLOR_TEMP

            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, coordinator.device_id)},
                serial_number=coordinator.device_id,
                manufacturer="dLight",
                model=coordinator.discovery["device_model"],
                name=coordinator.name,
                sw_version=coordinator.discovery["sw_version"],
                hw_version=coordinator.discovery["hw_version"],
            )