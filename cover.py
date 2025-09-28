# custom_components/smart_place_ch/cover.py

import logging
from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the cover platform from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    new_entities = []

    for jalousie_id, jalousie_info in hub.jalousien.items():
        jalousie = SmartPlaceCHJalousie(hub, jalousie_id, jalousie_info)
        new_entities.append(jalousie)
    
    if new_entities:
        async_add_entities(new_entities)

class SmartPlaceCHJalousie(CoverEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
    )
    # Start as unavailable, wait for the first real state update
    _attr_available = False

    def __init__(self, hub, device_id: str, device_info: dict):
        self._hub = hub
        self._device_id_num = device_id
        
        self._attr_name = device_info.get("name", f"Jalousie {device_id}")
        self._attr_unique_id = f"{DOMAIN}_jalousie{self._device_id_num}"
        
        # Internal state attributes
        self._position: int | None = None
        self._tilt_position: int | None = None

        self._attr_device_info = {
            "identifiers": {(DOMAIN, "Jalousie", self._device_id_num)},
            "name": self.name,
            "manufacturer": "Smart Place CH",
        }

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        return self._position

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self._position is None:
            return None
        return self._position == 100

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt."""
        return self._tilt_position

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        command = f"JALUP{self._device_id_num}"
        await self._hub.async_send_command(command)

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        command = f"JALDOW{self._device_id_num}"
        await self._hub.async_send_command(command)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        # Sending up or down again stops the cover. We will send UP.
        command = f"JALUP{self._device_id_num}"
        await self._hub.async_send_command(command)

    async def async_open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        command = f"JALLUE{self._device_id_num}"
        await self._hub.async_send_command(command)

    async def async_close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        command = f"JALLUE{self._device_id_num}"
        await self._hub.async_send_command(command)

    async def async_added_to_hass(self) -> None:
        """Register for updates from the hub."""
        update_signal = f"update_{DOMAIN}_jalousie{self._device_id_num}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, update_signal, self._handle_update
            )
        )

    @callback
    def _handle_update(self, data: dict) -> None:
        """Handle pushed data from the hub."""
        if not self._attr_available:
            self._attr_available = True
        
        position_str = data.get("position")
        tilt_str = data.get("tilt")

        if position_str is not None:
            self._position = 100 - int(position_str)

        if tilt_str is not None:
            self._tilt_position = 100 if tilt_str == "01" else 0

        self.async_write_ha_state()