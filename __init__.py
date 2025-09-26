import asyncio
import logging
import aiohttp
import re
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, CONF_URL
from .hub import SmartPlaceCHHub 


_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["light", "event"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Place CH from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hub = SmartPlaceCHHub(hass)

    if not await hub.async_setup(entry.data[CONF_URL]):
        return False
    
    hass.data[DOMAIN][entry.entry_id] = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hub = hass.data[DOMAIN].pop(entry.entry_id)
    await hub.stop()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    return unload_ok


