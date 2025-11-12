from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    entities: list[DomonapDoorCodeSensor] = []
    api = hass.data[DOMAIN][config_entry.entry_id][API]

    response = await api.get_paged_keys()
    keys = response.get("results", [])

    for key in keys:
        try:
            key_id: str = key["id"]
            door_id: str = key["doorId"]
            door_name: str = key["name"]
            pin: Optional[str] = key.get("domofonPublicPin")

            if not pin:
                _LOGGER.debug(
                    "No domofonPublicPin for door %s (%s), skipping PIN sensor",
                    door_id,
                    door_name,
                )
                continue

            entities.append(
                DomonapDoorCodeSensor(
                    key_id=key_id,
                    door_id=door_id,
                    device_name=door_name,
                    pin=pin,
                )
            )
        except Exception:
            _LOGGER.exception("Failed to create PIN sensor from key payload: %s", key)

    async_add_entities(entities, True)


class DomonapDoorCodeSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:key-variant"
    _attr_translation_key = "door_code"
    _attr_should_poll = False

    def __init__(self, key_id: str, door_id: str, device_name: str, pin: str):
        self._key_id = key_id
        self._door_id = door_id
        self._device_name = device_name
        self._pin = pin

    @property
    def unique_id(self) -> str:
        return f"{self._door_id}_door_code"

    @property
    def native_value(self) -> str | None:
        return self._pin

    @property
    def device_info(self):
        # Имя устройства — это "дверь". Сущность будет называться "<device>: <translated entity name>"
        return {
            "identifiers": {(DOMAIN, self._key_id)},
            "name": self._device_name,
            "manufacturer": "Domonap",
            "model": "Intercom Device",
        }