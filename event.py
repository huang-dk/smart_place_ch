# custom_components/my_integration/event.py

import logging
from typing import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
)

# Assuming your integration's domain is 'my_integration'
from .const import DOMAIN, DOORBELL_RING_MESSAGE
# You would get your hub instance from hass.data
# from .hub import MyHub  # Uncomment and adapt this to your actual hub class

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the doorbell event entity from a config entry."""
    # Get the hub instance that was stored in hass.data by __init__.py
    _LOGGER.debug("Register doorbell device")
    hub = hass.data[DOMAIN][config_entry.entry_id]

    # Create the doorbell entity and add it to Home Assistant
    async_add_entities([Doorbell(config_entry, hub)])


class Doorbell(EventEntity):
    """A doorbell event entity for My Integration."""

    # This attribute is needed to link the entity to the config entry's device
    _attr_has_entity_name = True

    def __init__(self, config_entry: ConfigEntry, hub) -> None:
        """Initialize the doorbell entity."""
        self._hub = hub
        self._config_entry_id = config_entry.entry_id

        # Set the device class to DOORBELL
        self._attr_device_class = EventDeviceClass.DOORBELL

        # Define the event types this entity can fire. For a simple doorbell,
        # one type is usually enough. This is the value that will appear in automations.
        self._attr_event_types = ["ring"]

        # Set the name of the entity
        self._attr_name = "Doorbell"

        # Set a unique ID for this entity
        self._attr_unique_id = f"{DOMAIN}_{self._config_entry_id}_doorbell"

        # Link this entity to the hub device for a nice entity hierarchy
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._config_entry_id)},
            name="SmartPlace Doorbell"
        )
        
        # This will hold the function to remove the callback later
        self._remove_callback: Callable[[], None] | None = None

    @callback
    def _handle_event(self, message: str) -> None:
        """Handle an incoming event from the hub."""
        if message.startswith(DOORBELL_RING_MESSAGE):
            _LOGGER.info("Doorbell ring event received from hub")
            # This is the core function that fires the event in Home Assistant
            self._trigger_event("ring")
            # Optionally, you can write the event to the entity's state attributes
            self.async_write_ha_state()
        else:
            _LOGGER.warning(f"Wrong message dispatched to doorbell: {message}")

    async def async_added_to_hass(self) -> None:
        """Register for updates from the hub."""
        update_signal = f"ring"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, update_signal, self._handle_event
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        # Unregister the callback when the entity is removed
        if self._remove_callback:
            self._remove_callback()
            _LOGGER.debug("Removed doorbell callback from the hub")