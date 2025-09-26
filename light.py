# custom_components/smart_place_ch/light.py

import logging
from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the light platform from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    new_entities = []

    for light_id, light_info in hub.lights.items():
        light = SmartPlaceCHLight(hub, light_id, light_info)
        new_entities.append(light)
    
    if new_entities:
        async_add_entities(new_entities)

class SmartPlaceCHLight(LightEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    # Start as unavailable, wait for the first real state update
    _attr_available = False

    def __init__(self, hub, device_id: str, device_info: dict):
        self._hub = hub
        self._device_id_num = device_id
        self._type = device_info.get("type", "schalter")
        
        self._attr_name = device_info.get("name", f"Light {device_id}")
        self._attr_unique_id = f"{DOMAIN}_leuchte{self._device_id_num}"
        # Default to 0, the first update will set the real value
        self._brightness = 0

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._device_id_num)},
            "name": self.name,
            "manufacturer": "Smart Place CH",
        }

    @property
    def is_on(self) -> bool:
        return self._brightness > 0

    @property
    def brightness(self) -> int | None:
        return self._brightness if self._type == "dimmer" else None

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        if self._type == "dimmer":
            return {ColorMode.BRIGHTNESS}
        return {ColorMode.ONOFF}

    @property
    def color_mode(self) -> ColorMode:
        if self._type == "dimmer":
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    async def async_turn_on(self, brightness: int | None = None, **kwargs):
        command = ""
        if self._type == "dimmer":
            target_brightness = brightness if brightness is not None else 255
            command = f"DIMleuchte{self._device_id_num}:{target_brightness}"
        else:
            if not self.is_on:
                command = f"leuchte{self._device_id_num}"
            else: return
        await self._hub.async_send_command(command)

    async def async_turn_off(self, **kwargs):
        if self.is_on:
            command = f"leuchte{self._device_id_num}"
            await self._hub.async_send_command(command)

    async def async_toggle(self, **kwargs) -> None:
        command = f"leuchte{self._device_id_num}"
        await self._hub.async_send_command(command)

    async def async_added_to_hass(self) -> None:
        """Register for updates from the hub."""
        update_signal = f"update_{DOMAIN}_leuchte{self._device_id_num}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, update_signal, self._handle_update
            )
        )

    @callback
    def _handle_update(self, value: int) -> None:
        """Handle pushed data from the hub."""
        # This is the first time we get real data, so mark as available
        if not self._attr_available:
            self._attr_available = True
        
        self._brightness = value
        self.async_write_ha_state()