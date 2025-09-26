from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries

# Use CONF_URL from homeassistant.const if it exists, otherwise define it
# For this custom purpose, we define it in our const.py
from .const import DOMAIN, CONF_URL

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_URL): str
})

class SmartPlaceCHConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Place CH."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}
        if user_input is not None:
            # You could add validation here to ensure it's a valid URL
            return self.async_create_entry(title="Smart Place CH", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )