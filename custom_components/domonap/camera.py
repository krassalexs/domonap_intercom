import logging
from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    CameraEntityDescription,
    StreamType,
)
from .const import DOMAIN, API

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    entities = []
    api = hass.data[DOMAIN][API]
    response = await api.get_paged_keys()
    doors = response.get("results", [])
    for door in doors:
        key_id = door["id"]
        key = await api.get_user_key(key_id)
        if key["videoUrl"] is not None:
            entities.append(IntercomCamera(api, key_id, door["name"], key["videoUrl"], key["videoPreview"]))

    async_add_entities(entities, True)


class IntercomCamera(Camera):
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_frontend_stream_type = StreamType.HLS
    _attr_motion_detection_enabled = False

    def __init__(self, api, key_id: str, name: str, stream_url: str, image_url: str):
        super().__init__()
        self._api = api
        self._key_id = key_id
        self._name = name
        self._stream_url = stream_url
        self._image_url = image_url

    @property
    def unique_id(self):
        return self._key_id

    @property
    def name(self):
        return "Camera"

    async def async_camera_image(self, **kwargs):
        return self._image_url

    async def stream_source(self):
        return self._stream_url

    @property
    def supported_features(self):
        return self._attr_supported_features

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._key_id)},
            "name": self._name,
            "manufacturer": "Domonap",
            "model": "Intercom Device",
            "via_device": (DOMAIN, self._key_id),
        }


    async def async_update(self):
        _LOGGER.debug(f"Updating camera: {self._name}")
