import aiohttp
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
    keys = response.get("results", [])
    for key in keys:
        key_id = key["id"]
        if key["httpVideoUrl"] is not None:
            entities.append(IntercomCamera(api, key_id, key["name"], key["httpVideoUrl"], key["videoPreview"]))

    async_add_entities(entities, True)


class IntercomCamera(Camera):
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_frontend_stream_type = StreamType.HLS
    _attr_motion_detection_enabled = False

    def __init__(self, api, key_id: str, name: str, stream_url: str, snapshot_url: str):
        super().__init__()
        self._api = api
        self._key_id = key_id
        self._name = name
        self._stream_url = stream_url
        self._snapshot_url = snapshot_url

    @property
    def unique_id(self):
        return self._key_id

    @property
    def name(self):
        return f"Камера {self._name}"

    async def async_camera_image(self, width=None, height=None):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self._snapshot_url) as response:
                    if response.status == 200:
                        _LOGGER.debug(f"Successfully fetched snapshot for {self._name}")
                        return await response.read()
                    else:
                        _LOGGER.error(f"Failed to fetch snapshot, HTTP {response.status}")
                        return None
        except Exception as e:
            _LOGGER.error(f"Error fetching snapshot from {self._snapshot_url}: {e}")
            return None

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
