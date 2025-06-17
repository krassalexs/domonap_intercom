import logging
from homeassistant.components.button import ButtonEntity
from .const import DOMAIN, API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    entities = []
    api = hass.data[DOMAIN][API]
    response = await api.get_paged_keys()
    keys = response.get("results", [])
    for key in keys:
        key_id = key["id"]
        door_id = key["doorId"]
        door_name = key["name"]
        entities.append(IntercomDoor(api, key_id, door_id, door_name))

    async_add_entities(entities, True)


class IntercomDoor(ButtonEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:lock"

    def __init__(self, api, key_id, door_id: str, name: str):
        self._api = api
        self._key_id = key_id
        self._door_id = door_id
        self._name = name

    @property
    def unique_id(self):
        return self._door_id

    @property
    def name(self):
        return "Open Door"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._key_id)},
            "name": self._name,
            "manufacturer": "Domonap",
            "model": "Intercom Device",
            "via_device": (DOMAIN, self._key_id),
        }

    async def async_press(self):
        try:
            response = await self._api.open_relay_by_key_id(self._key_id)  # Ensure this is awaited
            if response != "true":
                _LOGGER.error(f"Failed to open the door {self._name}. Response: {response}")
        except Exception as e:
            _LOGGER.error(f"Error opening the door {self._name}: {e}")