import logging
import aiohttp
import asyncio
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)


class IntercomAPI:
    def __init__(self, base_url="https://api.domonap.ru"):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
        self.refresh_expiration_date = None
        self.headers = {
            "Content-Type": "application/json",
            "dom-app": "mobile",
            "dom-platform": "blazor"
        }
        self.token_update_callback = None

    def set_tokens(self, access_token, refresh_token, refresh_expiration_date):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.refresh_expiration_date = refresh_expiration_date
        self.headers["Authorization"] = f"Bearer {self.access_token}"

    async def check_token_expiration(self):
        if self.refresh_expiration_date:
            _LOGGER.debug(f"Expiration_date: {self.refresh_expiration_date}")
            await self.update_device_token()
            expiration_date = datetime.strptime(self.refresh_expiration_date, "%Y-%m-%dT%H:%M:%S.%f%z")
            if datetime.now(timezone.utc) >= expiration_date:
                await self.update_token()

    async def update_device_token(self, device_token="home-assistant"):
        _LOGGER.debug(f"Starting UpdateDeviceToken")
        url = f"{self.base_url}/sso-api/Authorization/UpdateDeviceToken"
        payload = {
            "deviceToken": device_token
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as response:
                if response.status == 200:
                    _LOGGER.debug(f"UpdateDeviceToken alive. Continue...")
                    return "true"
                elif response.status == 401:
                    _LOGGER.error(f"Unauthorized, beginning refresh token {response.headers.get('WWW-Authenticate')}")
                    await self.update_token()
                    return "false"
                else:
                    error_text = f"UpdateDeviceToken failed with status code {response.status} data:\n{response}"
                    _LOGGER.error(error_text)
                    return {error_text}

    async def authorize(self, country_code, phone_number):
        url = f"{self.base_url}/sso-api/Authorization/Authorize"
        payload = {
            "phoneNumber": {
                "countryCode": country_code,
                "number": phone_number
            }
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as response:
                if response.status == 200:
                    return True
                else:
                    return {"error": f"Authorization failed with status code {response.status}"}

    async def confirm_authorization(self, country_code, phone_number, confirm_code, device_token="home-assistant"):
        url = f"{self.base_url}/sso-api/Authorization/ConfirmAuthorization"
        payload = {
            "phoneNumber": {
                "countryCode": country_code,
                "number": phone_number
            },
            "confirmCode": confirm_code,
            "deviceToken": device_token
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as response:
                if response.status == 200:
                    data = await response.json()
                    self.set_tokens(
                        data["completeToken"]["accessToken"],
                        data["completeToken"]["refreshToken"],
                        data["completeToken"]["refreshExpirationDate"]
                    )
                    if self.token_update_callback:
                        self.token_update_callback(data["completeToken"]["accessToken"],
                                                   data["completeToken"]["refreshToken"],
                                                   data["completeToken"]["refreshExpirationDate"])
                return await response.json()

    async def update_token(self):
        if not self.refresh_token:
            return {"error": "No refresh token available"}
        url = f"{self.base_url}/sso-api/Authorization/RefreshToken"
        payload = {
            "refreshToken": self.refresh_token
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as response:
                _LOGGER.info(f"Beginning refreshToken. Old Expiration Date {self.refresh_expiration_date} - "
                             f"today: {datetime.now(timezone.utc)}")
                if response.status == 200:
                    data = await response.json()
                    _LOGGER.info(f"New tokens successfully refreshed. "
                                 f"New Expiration Date{data["refreshExpirationDate"]}")
                    self.set_tokens(
                        data["accessToken"],
                        data["refreshToken"],
                        data["refreshExpirationDate"]
                    )
                    if self.token_update_callback:
                        self.token_update_callback(data["accessToken"],
                                                   data["refreshToken"],
                                                   data["refreshExpirationDate"])
                    return {
                        "access_token": data["accessToken"],
                        "refresh_token": data["refreshToken"],
                        "refresh_expiration_date": data["refreshExpirationDate"]
                    }
                return await response.json()

    async def get_user(self):
        await self.check_token_expiration()
        if not self.access_token:
            return {"error": "No access token available"}
        url = f"{self.base_url}/sso-api/User/GetUser"
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, ssl=False) as response:
                return await response.json()

    async def get_paged_keys(self, per_page=100, current_page=1):
        await self.check_token_expiration()
        if not self.access_token:
            return {"error": "No access token available"}
        url = f"{self.base_url}/client-api/Key/GetPagedKeysByKeysType"
        payload = {
            "perPage": per_page,
            "currentPage": current_page,
            "keysType": "Main"  # "Active"
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Error load keys {response.status}"}

    async def get_user_key(self, key_id):
        await self.check_token_expiration()
        if not self.access_token:
            return {"error": "No access token available"}
        url = f"{self.base_url}/client-api/Key/GetUserKey"
        payload = {
            "keyId": key_id
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as response:
                return await response.json()

    async def open_relay_by_door_id(self, door_id):
        await self.check_token_expiration()
        if not self.access_token:
            return {"error": "No access token available"}
        url = f"{self.base_url}/client-api/Device/OpenRelayByDoorId"
        payload = {
            "doorId": door_id
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as response:
                return await response.text()

    async def open_relay_by_key_id(self, key_id):
        await self.check_token_expiration()
        if not self.access_token:
            return {"error": "No access token available"}
        url = f"{self.base_url}/client-api/Device/OpenRelayByKeyId"
        payload = {
            "keyId": key_id
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as response:
                return await response.text()

    async def answer_call_notify(self, call_id):
        _LOGGER.debug(f"Sending answer_call_notify to call_id: {call_id}")
        await self.check_token_expiration()
        if not self.access_token:
            return {"error": "No access token available"}
        url = f"{self.base_url}/communication-api/Call/NotifyCallAnswered"
        payload = {
            "callId": call_id
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as response:
                result = await response.text()
                _LOGGER.debug(f"result of answer_call_notify to call_id: {call_id} - {result}")
                return result

    async def end_call_notify(self, call_id):
        _LOGGER.debug(f"Sending end_call_notify to call_id: {call_id}")
        await self.check_token_expiration()
        if not self.access_token:
            return {"error": "No access token available"}
        url = f"{self.base_url}/communication-api/Call/NotifyCallEnded"
        payload = {
            "callId": call_id
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as response:
                result = await response.text()
                _LOGGER.debug(f"result of end_call_notify to call_id: {call_id} - {result}")
                return result

    async def get_notify_id_token(self):
        _LOGGER.debug(f"Getting notify_id_token")
        await self.check_token_expiration()
        if not self.access_token:
            return {"error": "No access token available"}
        url = f"{self.base_url}/notificationHub/negotiate?negotiateVersion=1"

        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, ssl=False) as response:
                data = await response.json()
                if response.status == 200:
                    _LOGGER.debug(f"Result is ok. Processing data... {data.get('connectionToken')}")
                    return data.get('connectionToken')
                else:
                    _LOGGER.debug(f"Result is invalid.")
                    return None
