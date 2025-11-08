from __future__ import annotations

import asyncio
import logging
from datetime import timedelta, datetime
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    API,
    PARAM_ACCESS_TOKEN,
    PARAM_REFRESH_TOKEN,
    PARAM_REFRESH_EXPIRATION,
    PLATFORMS,
    UPDATE_INTERVAL,
)

if TYPE_CHECKING:
    from .api import IntercomAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .api import IntercomAPI
    from .notify_consumer import IntercomNotifyConsumer

    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    api = IntercomAPI()
    api.set_tokens(
        entry.data.get(PARAM_ACCESS_TOKEN),
        entry.data.get(PARAM_REFRESH_TOKEN),
        entry.data.get(PARAM_REFRESH_EXPIRATION),
    )

    def update_entry(access_token: str, refresh_token: str, refresh_expiration_date: str) -> None:
        _LOGGER.debug("Updating entry tokens in config_entry data")
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

    consumer = IntercomNotifyConsumer(hass, api)
    hass.data[DOMAIN][entry.entry_id][API] = api
    hass.data[DOMAIN][entry.entry_id]["notify_consumer"] = consumer

    async def _update_tokens_tick(now: datetime) -> None:
        try:
            await api.update_token()
        except Exception:
            _LOGGER.debug("Token refresh failed", exc_info=True)

    unsub_refresh = async_track_time_interval(hass, _update_tokens_tick, UPDATE_INTERVAL)
    hass.data[DOMAIN][entry.entry_id]["unsub_refresh"] = unsub_refresh

    entry.async_create_background_task(hass, consumer.start(), "domonap_notify")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    stored = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

    if (unsub := stored.get("unsub_refresh")) is not None:
        try:
            unsub()
        except Exception:
            _LOGGER.debug("Error unsubscribing refresh timer", exc_info=True)

    consumer = stored.get("notify_consumer")
    if consumer:
        try:
            await consumer.stop()
        except Exception:
            _LOGGER.debug("Exception while stopping notify consumer", exc_info=True)

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    return unloaded