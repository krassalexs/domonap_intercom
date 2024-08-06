import aiohttp
import asyncio
from datetime import datetime, timezone


class IntercomAPI:
    def __init__(self, base_url="https://prod-api.lovit.ru"):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
        self.refresh_expiration_date = None
        self.headers = {
            "Content-Type": "application/json"
        }
        self.token_update_callback = None

    def set_tokens(self, access_token, refresh_token, refresh_expiration_date):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.refresh_expiration_date = refresh_expiration_date
        self.headers["Authorization"] = f"Bearer {self.access_token}"

    def check_token_expiration(self):
        if self.refresh_expiration_date:
            expiration_date = datetime.strptime(self.refresh_expiration_date, "%Y-%m-%dT%H:%M:%S.%f%z")
            if datetime.now(timezone.utc) >= expiration_date:
                asyncio.run(self.update_token())

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
                if response.status == 200:
                    data = await response.json()
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
        self.check_token_expiration()
        if not self.access_token:
            return {"error": "No access token available"}
        url = f"{self.base_url}/sso-api/User/GetUser"
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, ssl=False) as response:
                return await response.json()

    async def get_paged_keys(self, per_page=100, current_page=1):
        self.check_token_expiration()
        if not self.access_token:
            return {"error": "No access token available"}
        url = f"{self.base_url}/client-api/Key/GetPagedKeysByKeysType"
        payload = {
            "PerPage": per_page,
            "CurrentPage": current_page
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Error load keys {response.status}"}

    async def get_user_key(self, key_id):
        self.check_token_expiration()
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
        self.check_token_expiration()
        if not self.access_token:
            return {"error": "No access token available"}
        url = f"{self.base_url}/client-api/Device/OpenRelayByDoorId"
        payload = {
            "doorId": door_id
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as response:
                return True
