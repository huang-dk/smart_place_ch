# custom_components/smart_place_ch/sensor.py

import logging
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    new_entities = []

    for klima_id, klima_info in hub.klimas.items():
        # For each climate device, create a corresponding temperature sensor
        temp_sensor = SmartPlaceCHTemperatureSensor(hub, klima_id, klima_info)
        new_entities.append(temp_sensor)
    
    if new_entities:
        async_add_entities(new_entities)


class SmartPlaceCHTemperatureSensor(SensorEntity):
    """Representation of a Smart Place CH Temperature Sensor."""
    _attr_should_poll = False
    _attr_has_entity_name = True

    # Sensor-specific attributes
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    
    # Start as unavailable, wait for the first real state update
    _attr_available = False

    def __init__(self, hub, device_id: str, device_info: dict):
        """Initialize the sensor entity."""
        self._hub = hub
        self._device_id_num = device_id
        
        # This name will be combined with the device name.
        # e.g., Device "Living Room" + Entity "Temperature" = "Living Room Temperature"
        self._attr_name = "Temperature"
        self._attr_unique_id = f"{DOMAIN}_klima{self._device_id_num}_temperature"
        
        # This is the crucial part that links this sensor to the climate entity's device
        # It MUST be identical to the device_info in your climate.py
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "Klima", self._device_id_num)},
            "name": device_info.get("name", f"Klima {device_id}"),
            "manufacturer": "Smart Place CH",
        }

    async def async_added_to_hass(self) -> None:
        """Register for updates from the hub."""
        # Listen for the same signal as the climate entity
        update_signal = f"update_{DOMAIN}_klima{self._device_id_num}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, update_signal, self._handle_update
            )
        )

    @callback
    def _handle_update(self, data: dict) -> None:
        """Handle pushed data from the hub."""
        key = data.get("key")
        value = data.get("value")

        # This sensor only cares about the current temperature
        if key == "TEMPIST":
            self._attr_native_value = float(value)
            if not self._attr_available:
                self._attr_available = True
            self.async_write_ha_state()