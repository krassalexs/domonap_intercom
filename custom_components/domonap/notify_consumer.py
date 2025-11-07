import json
import logging
import asyncio
import aiohttp
from typing import Callable, Optional, Any, Iterable, Union
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import IntercomAPI
from .const import EVENT_INCOMING_CALL

_LOGGER = logging.getLogger(__name__)

WS_MESSAGE_END = "\x1e"
WS_HANDSHAKE_MESSAGE = '{"protocol":"json","version":1}' + WS_MESSAGE_END
WS_URL = "wss://api.domonap.ru/notificationHub/?id="
PHOTO_URL = "https://s3-api.domonap.ru/snapshot/"


class IntercomNotifyConsumer:
    def __init__(self, hass: HomeAssistant, api: IntercomAPI) -> None:
        self._hass = hass
        self._api = api
        self._callbacks: set[Callable[[], Union[None, Any]]] = set()
        self._notify_id_token: Optional[str] = None
        self._connected: bool = False
        self._reconnect_delay: float = 1.0
        self._max_reconnect: float = 30.0
        self._stop_event = asyncio.Event()
        self._session = async_get_clientsession(hass)
        self._headers = {"Authorization": f"Bearer {self._api.access_token or ''}"}
        if hasattr(self._api, "token_update_callback") and self._api.token_update_callback is None:
            self._api.token_update_callback = self._on_token_update

    async def start(self) -> None:
        self._stop_event.clear()
        while not self._stop_event.is_set():
            try:
                await self._connect_and_run()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                _LOGGER.debug("Notify loop error: %s", e)
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect)

    async def stop(self) -> None:
        self._stop_event.set()

    def register_callback(self, callback: Callable[[], Any]) -> None:
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], Any]) -> None:
        self._callbacks.discard(callback)

    @property
    def connected(self) -> bool:
        return self._connected

    def _on_token_update(self, access: str, _refresh: str, _exp: str) -> None:
        self._headers["Authorization"] = f"Bearer {access}"

    async def _connect_and_run(self) -> None:
        self._notify_id_token = await self._api.get_notify_id_token()
        _LOGGER.debug("Negotiated connectionToken: %s", self._notify_id_token)
        if not self._notify_id_token:
            raise RuntimeError("Negotiation failed: empty connectionToken")
        ws_url = WS_URL + self._notify_id_token
        async with self._session.ws_connect(ws_url, headers=self._headers) as ws:
            _LOGGER.debug("WS connected")
            self._connected = True
            self._reconnect_delay = 1.0
            await ws.send_str(WS_HANDSHAKE_MESSAGE)
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_text(msg.data, ws)
                    await self._publish_updates()
                elif msg.type == aiohttp.WSMsgType.PING:
                    await ws.pong()
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    _LOGGER.debug("WS closed/error: %s", msg.data)
                    break
        self._connected = False
        _LOGGER.debug("WS disconnected")

    async def _handle_text(self, raw: str, ws: aiohttp.ClientWebSocketResponse) -> None:
        payload = raw.replace(WS_MESSAGE_END, "")
        if payload == "{}":
            _LOGGER.debug("Handshake ack")
            return
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            _LOGGER.debug("Non-JSON frame: %s", payload[:200])
            return
        frame_type = data.get("type")
        if frame_type == 1:
            await self._handle_invocation(data, ws)
        elif frame_type == 6:
            await ws.send_str(payload + WS_MESSAGE_END)
        elif frame_type == 3:
            _LOGGER.debug("Completion frame: %s", data)
        else:
            _LOGGER.debug("Unknown frame type=%s data=%s", frame_type, payload[:200])

    async def _handle_invocation(self, data: dict, ws: aiohttp.ClientWebSocketResponse) -> None:
        target = data.get("target")
        args: Iterable = data.get("arguments") or []
        if target == "ReceivePush":
            push_data = args[2] if len(args) >= 3 else None
            if isinstance(push_data, dict):
                evt = push_data.get("EventMessage")
                if evt == "DomofonCalling":
                    push_data["photoUrl"] = PHOTO_URL + str(push_data.get("CallId", ""))
                    self._hass.bus.fire(EVENT_INCOMING_CALL, push_data)
                    _LOGGER.debug("Incoming call: %s", push_data)
                else:
                    _LOGGER.debug("Unknown EventMessage=%s push=%s", evt, str(push_data)[:200])
            return

    async def _publish_updates(self) -> None:
        for cb in list(self._callbacks):
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb()  # type: ignore[misc]
                else:
                    cb()
            except Exception as e:
                _LOGGER.debug("Callback error: %s", e)