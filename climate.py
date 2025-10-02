# custom_components/smart_place_ch/climate.py

import logging
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# A dictionary to map device modes to HA constants
MODE_MAP = {
    "heizen": {"mode": HVACMode.HEAT, "action": HVACAction.HEATING},
    "kühlen": {"mode": HVACMode.COOL, "action": HVACAction.COOLING},
    "null": {"action": HVACAction.IDLE}, # 'null' only affects the action, not the mode
}
REVERSE_MODE_MAP = {
    HVACMode.HEAT: "heizen",
    HVACMode.COOL: "kühlen",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the climate platform from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    new_entities = []

    for klima_id, klima_info in hub.klimas.items():
        klima_device = SmartPlaceCHKlima(hub, klima_id, klima_info)
        new_entities.append(klima_device)
    
    if new_entities:
        async_add_entities(new_entities)


class SmartPlaceCHKlima(ClimateEntity):
    """Representation of a Smart Place CH climate device."""
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 18
    _attr_max_temp = 26
    _attr_target_temperature_step = 1

    # Start as unavailable, wait for the first real state update
    _attr_available = False

    def __init__(self, hub, device_id: str, device_info: dict):
        """Initialize the climate entity."""
        self._hub = hub
        self._device_id_num = device_id
        
        self._attr_name = device_info.get("name", f"Klima {device_id}")
        self._attr_unique_id = f"{DOMAIN}_klima{self._device_id_num}"
        
        # Internal state attributes
        self._current_temp: float | None = None
        self._target_temp: float | None = None
        self._hvac_mode: HVACMode = HVACMode.OFF
        self._hvac_action: HVACAction = HVACAction.OFF

        self._attr_device_info = {
            "identifiers": {(DOMAIN, "Klima", self._device_id_num)},
            "name": self.name,
            "manufacturer": "Smart Place CH",
        }

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temp

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current hvac mode."""
        return self._hvac_mode
        
    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        # By returning a list with only the current mode, we tell HA
        # there are no other options, so it hides the mode selector.
        return [self.hvac_mode]

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return self._hvac_action

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            command = f"TEMPSOLL{self._device_id_num}:{int(temperature)}"
            await self._hub.async_send_command(command)

    async def async_added_to_hass(self) -> None:
        """Register for updates from the hub."""
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

        if not self._attr_available:
            self._attr_available = True
        
        if key == "TEMPIST":
            self._current_temp = float(value)
        elif key == "TEMPSOLL":
            self._target_temp = float(value)
        elif key == "KLIMASINFO":
            state = MODE_MAP.get(value)
            if state:
                if "mode" in state:
                    self._hvac_mode = state["mode"]
                self._hvac_action = state["action"]

        self.async_write_ha_state()