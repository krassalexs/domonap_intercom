import logging
from datetime import timedelta
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_interval
from .const import DOMAIN, API, PARAM_ACCESS_TOKEN, PARAM_REFRESH_TOKEN, PARAM_REFRESH_EXPIRATION
from .api import IntercomAPI
from .notify_client import IntercomNotifyClient

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BUTTON, Platform.CAMERA]
UPDATE_INTERVAL = timedelta(hours=24)  # интервал обновления токенов


async def async_setup(hass: HomeAssistant, config: dict):
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    api = IntercomAPI()
    api.set_tokens(entry.data.get(PARAM_ACCESS_TOKEN),
                   entry.data.get(PARAM_REFRESH_TOKEN),
                   entry.data.get(PARAM_REFRESH_EXPIRATION))

    notify_client = IntercomNotifyClient(hass, api)
    entry.async_create_background_task(hass, notify_client.process(), "domonap_notify_client_update")

    def update_entry(access_token, refresh_token, refresh_expiration_date):
        _LOGGER.debug("Updating entry with new tokens")
        new_data = entry.data.copy()
        new_data.update({
            PARAM_ACCESS_TOKEN: access_token,
            PARAM_REFRESH_TOKEN: refresh_token,
            PARAM_REFRESH_EXPIRATION: refresh_expiration_date,
        })
        hass.config_entries.async_update_entry(entry, data=new_data)

    api.token_update_callback = update_entry
    hass.data[DOMAIN][API] = api

    # Запланировать периодическое обновление токенов
    async_track_time_interval(hass, lambda now: update_tokens(hass), UPDATE_INTERVAL)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    res = (await hass.config_entries.async_forward_entry_unload(entry, Platform.BUTTON) &
           await hass.config_entries.async_forward_entry_unload(entry, Platform.CAMERA))
    return res


async def update_tokens(hass: HomeAssistant):
    api = hass.data[DOMAIN][API]
    await api.update_token()
