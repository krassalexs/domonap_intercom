import json
import logging
import aiohttp
import asyncio

from collections.abc import Callable

from homeassistant.core import HomeAssistant

from .api import IntercomAPI

_LOGGER = logging.getLogger(__name__)

WS_MESSAGE_END = ''
WS_HANDSHAKE_MESSAGE = '{"protocol": "json", "version": 1}' + WS_MESSAGE_END


class IntercomNotifyClient:
    base_url = "wss://api.domonap.ru/notificationHub/?id="
    photo_url = "https://s3-api.domonap.ru/snapshot/"
    def __init__(
            self, hass: HomeAssistant, api: IntercomAPI
    ) -> None:
        """Initialise the class."""
        self._hass = hass
        self._callbacks = set()
        self._notify_id_token = None
        self._id = ''
        self._api = api
        self._connected = False
        self.headers = {
            "Authorization": f"Bearer {self._api.access_token}"
        }
        _LOGGER.debug("Init IntercomNotifyClient")

    async def message_callback(self, message, ws):
        message_data = json.loads(message)
        if message == "{}":
            _LOGGER.debug(f"Handshake successful")
        elif message_data.get('type') == 1:
            if message_data.get('target') == 'ReceivePush':
                push_data = message_data.get('arguments')[2]
                if push_data.get("EventMessage") == "DomofonCalling":
                    _LOGGER.debug(f"Incoming call {push_data}")
                    push_data.update({'photoUrl': self.photo_url + push_data.get("CallId")})
                    self._hass.bus.fire("domonap_incoming_call", push_data)
                else:
                    _LOGGER.debug(f"Unknown EventMessage type {push_data.get("EventMessage")} message:\n{message}")

            elif message_data.get('target') in ('ReceiveOnline', "ReceiveOffline"):
                _LOGGER.debug(f"User {message_data.get('arguments')[0]} is "
                              f"{message_data.get('target').replace('ReceiveO', 'o')}")
                self._hass.bus.fire("domonap_user_status_changed", {
                    'user': message_data.get('arguments')[0],
                    'status': message_data.get('target').replace('ReceiveO', 'o')
                })
            elif message_data.get('target') == "ReceiveMessage":
                chat_data = message_data.get('arguments')[0]
                self._hass.bus.fire("domonap_receive_message", chat_data)
                _LOGGER.debug(f"Received message from {chat_data.get('sender')}: {chat_data.get('text')}")
            elif message_data.get('target') == 'ReceiveRead':
                _LOGGER.debug(f"Read confirm messages in channel {message_data.get('arguments')[0]}")
            else:
                _LOGGER.debug(f"Unknown target type {message_data.get('target')} message:\n{message}")

        elif message_data.get('type') == 3:
            _LOGGER.debug(f"Type 3. Хз что это))")
        elif message_data.get('type') == 6:
            _LOGGER.debug(f"Ping - Pong message. Answering.")
            await ws.send_str(message + WS_MESSAGE_END)
        else:
            _LOGGER.debug(f"Unknown messsage type {message_data.get('type')} message:\n{message}")

    async def process(self):
        while not self._connected:
            try:
                self._notify_id_token = await self._api.get_notify_id_token()
                _LOGGER.debug(f"Get token {self._notify_id_token}")
                if self._notify_id_token:
                    async with aiohttp.ClientSession(headers=self.headers) as session:
                        async with session.ws_connect(self.base_url + self._notify_id_token) as ws:
                            _LOGGER.debug("Connected")
                            await ws.send_str(WS_HANDSHAKE_MESSAGE)
                            self._connected = True
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    await self.message_callback(msg.data.replace(WS_MESSAGE_END, ''), ws)
                                elif msg.type == aiohttp.WSMsgType.CLOSED:
                                    self._connected = False
                                    _LOGGER.debug(f"Connection closed {msg.data}")
                                    break
                                elif msg.type == aiohttp.WSMsgType.ERROR:
                                    _LOGGER.error(f"Error in processing {msg.data}")
                                    break
                                await self.publish_updates()
            except aiohttp.WSServerHandshakeError as error:
                if error.status == 404:
                    pass
                elif error.status == 401:
                    _LOGGER.error(f"Unauthorised connection. {error.headers.get('WWW-Authenticate')}")
                    self.headers.update(
                        {
                            "Authorization": f"Bearer {self._api.access_token}"
                        }
                    )
                else:
                    _LOGGER.error(f"Unknown WSServer error connection. {error}")
            except Exception as error:
                _LOGGER.debug(f'start_notify_listening unknown error: {error}')
            await asyncio.sleep(3)

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register callback called when the state changes."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    async def publish_updates(self) -> None:
        """Call all callbacks on update."""
        for callback in self._callbacks:
            callback()

    @property
    def connected(self) -> bool:
        """Available if the websockets connection has value and is not closed."""
        return self._connected
