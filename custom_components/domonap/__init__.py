import asyncio
import logging
from datetime import timedelta

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    API,
    PARAM_ACCESS_TOKEN,
    PARAM_REFRESH_TOKEN,
    PARAM_REFRESH_EXPIRATION,
)
from .api import IntercomAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.CAMERA]
UPDATE_INTERVAL = timedelta(hours=24)


async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    api = IntercomAPI()
    api.set_tokens(
        entry.data.get(PARAM_ACCESS_TOKEN),
        entry.data.get(PARAM_REFRESH_TOKEN),
        entry.data.get(PARAM_REFRESH_EXPIRATION),
    )

    from .notify_consumer import IntercomNotifyConsumer

    consumer = IntercomNotifyConsumer(hass, api)
    hass.data[DOMAIN]["notify_consumer"] = consumer
    entry.async_create_background_task(hass, consumer.start(), "domonap_notify")

    def update_entry(access_token, refresh_token, refresh_expiration_date):
        _LOGGER.debug("Updating entry with new tokens")
        new_data = dict(entry.data)
        new_data.update(
            {
                PARAM_ACCESS_TOKEN: access_token,
                PARAM_REFRESH_TOKEN: refresh_token,
                PARAM_REFRESH_EXPIRATION: refresh_expiration_date,
            }
        )
        hass.config_entries.async_update_entry(entry, data=new_data)

    api.token_update_callback = update_entry
    hass.data[DOMAIN][API] = api

    async_track_time_interval(hass, lambda now: update_tokens(hass), UPDATE_INTERVAL)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    consumer = hass.data[DOMAIN].pop("notify_consumer", None)
    if consumer:
        try:
            await consumer.stop()
        except Exception:
            _LOGGER.debug("Exception while stopping notify consumer", exc_info=True)

    results = await asyncio.gather(
        *[
            hass.config_entries.async_forward_entry_unload(entry, platform)
            for platform in PLATFORMS
        ],
        return_exceptions=False,
    )
    return all(results)


async def update_tokens(hass: HomeAssistant):
    api: IntercomAPI = hass.data[DOMAIN][API]
    try:
        await api.update_token()
    except Exception:
        _LOGGER.debug("Token refresh failed", exc_info=True)