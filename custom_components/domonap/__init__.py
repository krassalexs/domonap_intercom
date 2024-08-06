import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, API, PARAM_ACCESS_TOKEN, PARAM_REFRESH_TOKEN, PARAM_REFRESH_EXPIRATION
from .api import IntercomAPI

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: dict):
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    api = IntercomAPI()
    api.set_tokens(entry.data.get(PARAM_ACCESS_TOKEN),
                   entry.data.get(PARAM_REFRESH_TOKEN),
                   entry.data.get(PARAM_REFRESH_EXPIRATION))
    hass.data[DOMAIN][API] = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    return await hass.config_entries.async_forward_entry_unload(entry, Platform.BUTTON)
