import logging
from typing import Optional, Callable
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from .const import DOMAIN, API, EVENT_INCOMING_CALL

_LOGGER = logging.getLogger(__name__)

RESET_DELAY = 10  # секунды


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Настройка binary sensor для каждой двери."""
    entities = []
    api = hass.data[DOMAIN][API]
    response = await api.get_paged_keys()
    keys = response.get("results", [])
    
    for key in keys:
        key_id = key["id"]
        door_id = key["doorId"]
        door_name = key["name"]
        # Создаем sensor только для дверей с httpVideoUrl
        if key.get("httpVideoUrl") is not None:
            entities.append(IntercomCallBinarySensor(hass, api, key_id, door_id, door_name))

    async_add_entities(entities, True)


class IntercomCallBinarySensor(BinarySensorEntity):
    """Binary sensor для отслеживания входящих звонков по DoorId."""
    
    _attr_has_entity_name = True
    _attr_icon = "mdi:phone-incoming"
    _attr_device_class = "running"
    _attr_translation_key = "incoming_call"

    def __init__(self, hass: HomeAssistant, api, key_id: str, door_id: str, name: str):
        self._hass = hass
        self._api = api
        self._key_id = key_id
        self._door_id = door_id
        self._name = name
        self._state = False
        self._reset_timer: Optional[Callable[[], None]] = None
        self._listener = None

    @property
    def unique_id(self):
        return f"{self._door_id}_call"

    @property
    def is_on(self):
        """Возвращает True если есть входящий звонок."""
        return self._state

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._key_id)},
            "name": self._name,
            "manufacturer": "Domonap",
            "model": "Intercom Device",
        }

    async def async_added_to_hass(self):
        """Вызывается когда entity добавлен в Home Assistant."""
        # Подписываемся на событие входящего звонка
        self._listener = self._hass.bus.async_listen(
            EVENT_INCOMING_CALL, self._handle_incoming_call
        )

    async def async_will_remove_from_hass(self):
        """Вызывается когда entity удаляется из Home Assistant."""
        # Отписываемся от события
        if self._listener:
            self._listener()
        # Отменяем таймер если он активен
        if self._reset_timer:
            self._reset_timer()
            self._reset_timer = None

    @callback
    def _handle_incoming_call(self, event):
        """Обработчик события входящего звонка."""
        door_id = event.data.get("DoorId")
        if door_id == self._door_id:
            _LOGGER.debug(
                "Incoming call detected for door %s (%s)", self._door_id, self._name
            )
            # Устанавливаем состояние в True
            self._state = True
            self.async_write_ha_state()
            
            # Отменяем предыдущий таймер если он был
            if self._reset_timer:
                self._reset_timer()
            
            # Устанавливаем таймер на сброс через 10 секунд
            self._reset_timer = async_call_later(
                self._hass, RESET_DELAY, self._reset_state
            )

    @callback
    def _reset_state(self, _now):
        """Сбрасывает состояние в False через 10 секунд."""
        _LOGGER.debug(
            "Resetting call state for door %s (%s)", self._door_id, self._name
        )
        self._state = False
        self._reset_timer = None
        self.async_write_ha_state()

