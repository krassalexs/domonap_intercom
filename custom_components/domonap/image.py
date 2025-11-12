from __future__ import annotations

import logging
from typing import Optional, Callable

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, API, EVENT_INCOMING_CALL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """Создаём image-entity для каждой двери; картинка обновляется при звонке из PhotoUrl."""
    entities: list[IntercomCallImageEntity] = []
    api = hass.data[DOMAIN][config_entry.entry_id][API]

    response = await api.get_paged_keys()
    keys = response.get("results", [])

    for key in keys:
        # создаём сущность только если есть стартовый превью-URL
        if key.get("videoPreview") is not None:
            key_id: str = key["id"]
            door_id: str = key["doorId"]
            door_name: str = key["name"]
            photo_url: str = key["videoPreview"]

            entities.append(
                IntercomCallImageEntity(
                    hass=hass,
                    api=api,
                    key_id=key_id,
                    door_id=door_id,
                    name=door_name,
                    photo_url=photo_url,
                )
            )

    async_add_entities(entities, True)


class IntercomCallImageEntity(ImageEntity):
    """Image-entity, показывающая последнюю картинку звонящего."""

    _attr_has_entity_name = True
    _attr_translation_key = "incoming_call_image"
    _attr_content_type = "image/jpeg"

    def __init__(
        self,
        hass: HomeAssistant,
        api,
        key_id: str,
        door_id: str,
        name: str,
        photo_url: Optional[str] = None,
    ):
        super().__init__(hass)
        self._api = api
        self._key_id = key_id
        self._door_id = door_id
        self._attr_name = name
        self._photo_url = photo_url
        self._unsub: Optional[Callable[[], None]] = None

    @property
    def unique_id(self) -> str:
        return f"{self._door_id}_photo"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._key_id)},
            "name": self._attr_name,
            "manufacturer": "Domonap",
            "model": "Intercom Device",
        }

    async def async_added_to_hass(self) -> None:
        self._unsub = self.hass.bus.async_listen(
            EVENT_INCOMING_CALL, self._handle_incoming_call
        )

        if self._photo_url:
            data = await self._http_get_bytes(self._photo_url)
            if data:
                await self.async_set_image(data)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_incoming_call(self, event) -> None:
        """Обновляем картинку при звонке по новому PhotoUrl (строго из поля PhotoUrl)."""
        if event.data.get("DoorId") != self._door_id:
            return

        photo_url: Optional[str] = event.data.get("PhotoUrl")
        if not photo_url:
            return

        async def _fetch_and_set():
            data = await self._http_get_bytes(photo_url)
            if data:
                await self.async_set_image(data)

        self.hass.async_create_task(_fetch_and_set())

    async def _http_get_bytes(self, url: str) -> Optional[bytes]:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
                _LOGGER.debug("GET %s returned HTTP %s", url, resp.status)
        except Exception:
            _LOGGER.exception("Failed to GET %s", url)
        return None