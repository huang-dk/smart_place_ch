# custom_components/smart_place_ch/hub.py

import asyncio
import logging
import aiohttp
import re
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, DOORBELL_RING_MESSAGE

_LOGGER = logging.getLogger(__name__)
class SmartPlaceCHHub:
    """Manages the WebSocket connection and data for Smart Place CH."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._main_uri = None
        self._main_ws = None
        self._listener_task = None
        self.lights = {}

    async def async_setup(self, initial_token: str) -> bool:
        """Perform connection and device discovery."""
        _LOGGER.info("Starting Smart Place CH Hub setup")
        self._main_uri = await self._get_main_websocket_uri(initial_token)
        if not self._main_uri: return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self._main_uri, timeout=10, ssl=False) as ws:
                    _LOGGER.info("WebSocket connected. Discovering devices.")

                    await ws.send_str("GiveMeMainmenu")
                    while True:
                        msg = await asyncio.wait_for(ws.receive(), timeout=30.0)
                        if msg.type != aiohttp.WSMsgType.TEXT: continue
                        if msg.data == "GiveMeMainMenuFinished": break
                        self._parse_discovery_message(msg.data)
                    _LOGGER.info(f"Discovery finished. Found {len(self.lights)} lights.")

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout during device discovery.")
            return False
        except Exception as e:
            _LOGGER.error(f"Error during discovery handshake: {e}", exc_info=True)
            return False
        
        self._listener_task = self.hass.async_create_background_task(self._listen(), name="state_listener")
        _LOGGER.info("Smart Place CH Hub setup complete. Listener started.")
        return True
    
    def _parse_discovery_message(self, message: str):
        try:
            if message.startswith("INHALTLeuchten"):
                parts = message.replace("INHALTLeuchten", "").split(":", 1)
                light_id = parts[0]
                properties = parts[1].split(",")
                name = properties[0]
                light_type = "schalter"
                if "dimmer" in properties: light_type = "dimmer"
                if light_id not in self.lights:
                    self.lights[light_id] = {"name": name, "type": light_type}
        except Exception:
            _LOGGER.warning(f"Could not parse discovery message: '{message}'")
    
    async def stop(self):
        if self._listener_task: self._listener_task.cancel()
        if self._main_ws and not self._main_ws.closed: await self._main_ws.close()

    @callback
    def _dispatch_light_update(self, light_id: str, value):
        signal = f"update_{DOMAIN}_leuchte{light_id}"
        async_dispatcher_send(self.hass, signal, value)

    def _dispatch_doorbell_event(self, message):
        signal = f"ring"
        async_dispatcher_send(self.hass, signal, message)

    async def _listen(self):
        retry_delay = 5
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(self._main_uri, timeout=10, ssl=False) as ws:
                        self._main_ws = ws
                        _LOGGER.info("Persistent listener connection established.")
                        await ws.send_str("SocketConnected:1")
                        retry_delay = 5
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                message = msg.data
                                _LOGGER.debug(f"Received message: {message}")
                                if message.startswith("leuchte"):
                                    try:
                                        key, value_str = message.replace("leuchte", "").split(":")
                                        self._dispatch_light_update(key, int(value_str))
                                    except (ValueError, IndexError): pass
                                elif message.startswith(DOORBELL_RING_MESSAGE):
                                    try:
                                        self._dispatch_doorbell_event(message)
                                    except (ValueError, IndexError): pass
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR): break
            except Exception as e:
                _LOGGER.error(f"Listener connection error: {e}")
            finally:
                self._main_ws = None
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 120)

    async def _get_main_websocket_uri(self, initial_token: str) -> str | None:
        headers = {"User-Agent": "Mozilla/5.0"}
        # Example URL: wss://spr2.smartplace.ch:8770/StartAppExt/?TOKEN=y6n8fftlhglw59qqu85h98pfzlz86ehcy2okvbku06zpqpd99pi6xwai0kf4adnmeyziguekwnmy3b6no3q1smchli0qzvulfa07
        bootstrap_url = f"wss://spr2.smartplace.ch:8770/StartAppExt/?TOKEN={initial_token}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(bootstrap_url, headers=headers, timeout=10, ssl=False) as ws:
                    msg = await ws.receive(timeout=10)
                    if msg.type != aiohttp.WSMsgType.TEXT: return None
                    match = re.search(r"GoToLinkSSL:([^/]+)", msg.data)
                    if not match: return None
                    return f"wss://{match.group(1)}/UpdatenLS"
        except Exception as e:
            _LOGGER.error(f"Error during bootstrap connection: {e}")
            return None
            
    async def async_send_command(self, command_data: str):
        if self._main_ws and not self._main_ws.closed:
            await self._main_ws.send_str(command_data)
        else:
            _LOGGER.error("Cannot send command, WebSocket is not connected.")