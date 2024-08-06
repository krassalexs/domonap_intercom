import logging
from homeassistant.components.button import ButtonEntity
from .const import DOMAIN, API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    entities = []
    api = hass.data[DOMAIN][API]
    response = await api.get_paged_keys()
    doors = response.get("results", [])
    for door in doors:
        door_id = door["doorId"]
        door_name = door["name"]
        entities.append(IntercomDoor(api, door_id, door_name))

    async_add_entities(entities, True)


class IntercomDoor(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, api, door_id: str, name: str):
        self._api = api
        self._door_id = door_id
        self._name = name

    @property
    def unique_id(self):
        return self._door_id

    @property
    def name(self):
        return self._name

    async def async_press(self):
        try:
            response = await self._api.open_relay_by_door_id(self._door_id)  # Ensure this is awaited
            if response.get('status') is not True:
                _LOGGER.error(f"Failed to open the door {self._name}. Response: {response}")
        except Exception as e:
            _LOGGER.error(f"Error opening the door {self._name}: {e}")