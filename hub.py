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
        self.klimas = {}
        self.jalousien = {} # ADDED: Dictionary for blind devices
        self._initial_token = None

    async def async_setup(self, initial_token: str) -> bool:
        """Perform connection and device discovery."""
        _LOGGER.info("Starting Smart Place CH Hub setup")
        self._initial_token = initial_token
        self._main_uri = await self._get_main_websocket_uri(self._initial_token)
        if not self._main_uri:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self._main_uri, timeout=10, ssl=False) as ws:
                    self._main_ws = ws
                    _LOGGER.info("WebSocket connected. Discovering devices.")

                    await ws.send_str("GiveMeMainmenu")
                    while True:
                        msg = await asyncio.wait_for(ws.receive(), timeout=30.0)
                        if msg.type != aiohttp.WSMsgType.TEXT: continue
                        if msg.data == "GiveMeMainMenuFinished": break
                        self._parse_discovery_message(msg.data)
                    _LOGGER.info(
                        f"Discovery finished. Found {len(self.lights)} lights, "
                        f"{len(self.klimas)} climate devices, and {len(self.jalousien)} blinds."
                    )

        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout when connecting to {self._main_uri}.")
            return False
        except Exception as e:
            _LOGGER.error(f"Error during discovery handshake: {e}", exc_info=True)
            return False

        self._listener_task = self.hass.async_create_background_task(self._listen(), name="state_listener")
        _LOGGER.info("Smart Place CH Hub setup complete. Listener started.")
        return True
    
    def _parse_discovery_message(self, message: str):
        """Parse a discovery message for lights or climate devices."""
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

            elif message.startswith("INHALTKlimas"):
                parts = message.replace("INHALTKlimas", "").split(":", 1)
                klima_id = parts[0]
                properties = parts[1].split(",")
                name = properties[0]
                if klima_id not in self.klimas:
                    self.klimas[klima_id] = {"name": name}
            
            # ADDED: Discovery logic for blinds
            elif message.startswith("INHALTJalousien"):
                parts = message.replace("INHALTJalousien", "").split(":", 1)
                jalousie_id = parts[0]
                properties = parts[1].split(",")
                name = properties[0]
                if jalousie_id not in self.jalousien:
                    self.jalousien[jalousie_id] = {"name": name}

        except Exception:
            _LOGGER.warning(f"Could not parse discovery message: '{message}'")
    
    async def stop(self):
        if self._listener_task: self._listener_task.cancel()
        if self._main_ws and not self._main_ws.closed: await self._main_ws.close()

    @callback
    def _dispatch_light_update(self, light_id: str, value):
        """Dispatch an update for a light entity."""
        signal = f"update_{DOMAIN}_leuchte{light_id}"
        async_dispatcher_send(self.hass, signal, value)

    @callback
    def _dispatch_klima_update(self, klima_id: str, data: dict):
        """Dispatch an update for a climate entity."""
        signal = f"update_{DOMAIN}_klima{klima_id}"
        async_dispatcher_send(self.hass, signal, data)

    # ADDED: Dispatcher for jalousie updates
    @callback
    def _dispatch_jalousie_update(self, jalousie_id: str, data: dict):
        """Dispatch an update for a jalousie entity."""
        signal = f"update_{DOMAIN}_jalousie{jalousie_id}"
        async_dispatcher_send(self.hass, signal, data)

    def _dispatch_doorbell_event(self, message):
        """Dispatch a doorbell ring event."""
        signal = f"ring"
        async_dispatcher_send(self.hass, signal, message)

    async def _listen(self):
        """Listen for state changes on the WebSocket with reconnection logic."""
        retry_delay = 1
        klima_pattern = re.compile(r"^(TEMPIST|TEMPSOLL|KLIMASINFO)(\d+):(.+)$")
        jalousie_pattern = re.compile(r"^JALICO(\d+):(\d{2,3})-(\d{2})$") # ADDED: Regex for blinds

        while True:
            self._main_uri = await self._get_main_websocket_uri(self._initial_token)
            if not self._main_uri:
                _LOGGER.error(f"Not able to get the URI for {self._initial_token}")
                self._main_ws = None
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 120)
                continue
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(self._main_uri, timeout=10, ssl=False, heartbeat=30) as ws:
                        self._main_ws = ws
                        _LOGGER.info("Persistent listener connection established.")
                        await ws.send_str("SocketConnected:1")
                        retry_delay = 1
                        while not ws.closed:
                            try:
                                _LOGGER.debug("Waiting for message..")
                                msg = await ws.receive(timeout=60)
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    message = msg.data
                                    _LOGGER.debug(f"Received message: {message}")
                                    
                                    if message.startswith("leuchte"):
                                        try:
                                            key, value_str = message.replace("leuchte", "").split(":")
                                            self._dispatch_light_update(key, int(value_str))
                                        except (ValueError, IndexError): pass
                                    
                                    elif (klima_match := klima_pattern.match(message)):
                                        try:
                                            key, device_id, value = klima_match.groups()
                                            update_data = {"key": key, "value": value}
                                            self._dispatch_klima_update(device_id, update_data)
                                        except (ValueError, IndexError): pass

                                    # ADDED: Blind state parsing
                                    elif (jalousie_match := jalousie_pattern.match(message)):
                                        try:
                                            device_id, position, tilt = jalousie_match.groups()
                                            update_data = {"position": position, "tilt": tilt}
                                            self._dispatch_jalousie_update(device_id, update_data)
                                        except (ValueError, IndexError): pass

                                    elif message.startswith(DOORBELL_RING_MESSAGE):
                                        try:
                                            self._dispatch_doorbell_event(message)
                                        except (ValueError, IndexError): pass

                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    _LOGGER.info("Server closed connection")
                                    break
                                elif msg.type == aiohttp.WSMsgType.ERROR:
                                    _LOGGER.error(f"WebSocket connection closed with exception {ws.exception()}")
                                    break
                            
                            except asyncio.TimeoutError:
                                # No message received, send a keep-alive ping.
                                _LOGGER.debug("No message received in 60 seconds, sending a keep-alive ping.")
                                await ws.send_str("SocketConnected:1")
            
            except Exception as e:
                _LOGGER.error(f"Listener connection error: {e}")
            
            finally:
                if self._main_ws and not self._main_ws.closed:
                    await self._main_ws.close()
                self._main_ws = None
                _LOGGER.error(f"Disconnected from listener, will retry in {retry_delay}s")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 120)

    async def _get_main_websocket_uri(self, initial_token: str) -> str | None:
        """Perform bootstrap connection to find the main WebSocket URI."""
        headers = {"User-Agent": "Mozilla/5.0"}
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
        """Send a command over the WebSocket."""
        if self._main_ws and not self._main_ws.closed:
            await self._main_ws.send_str(command_data)
        else:
            _LOGGER.error("Cannot send command, WebSocket is not connected.")