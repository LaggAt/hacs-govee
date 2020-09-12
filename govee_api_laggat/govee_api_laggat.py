""" client to connect to the govee API """

import sys
import logging
from typing import List

from dataclasses import dataclass
import asyncio
import aiohttp

_VERSION = "0.0.1" 
_LOGGER = logging.getLogger(__name__)
_API_URL = "https://developer-api.govee.com"

@dataclass
class GoveeLightInfo(object):
    device: str
    model: str
    device_name: str
    controllable: bool
    retrievable: bool
    support_turn: bool
    support_brightness: bool
    support_color: bool
    support_color_tem: bool

class Govee(object):
    """ client to connect to the govee API """

    async def __aenter__(self):
        """ async context manager enter """
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *err):
        """ async context manager exit """
        if self._session:
            await self._session.close()
        self._session = None
    
    def __init__(self, api_key: str):
        """ init with an API_KEY """
        self._api_key = api_key
        
    @classmethod
    async def create(cls, api_key: str):
        self = Govee(api_key)
        await self.__aenter__()
        return self
    
    async def close(self):
        await self.__aexit__()
    
    def _getAuthHeaders(self):
        return {'Govee-API-Key': self._api_key}

    async def ping_async(self) -> bool:
        _LOGGER.debug("ping_async")
        url = (_API_URL + "/ping")
        async with self._session.get(url=url) as response:
            assert response.status == 200
            result = await response.text()
            return 'Pong' == result


    async def get_devices(self) -> List[GoveeLightInfo]:
        _LOGGER.debug("get_devices")
        url = (
            _API_URL
            + "/v1/devices"
        )
        async with self._session.get(url=url, headers = self._getAuthHeaders()) as response:
            assert response.status == 200
            result = await response.json()
            light_infos = [
                GoveeLightInfo(
                    item["device"],
                    item["model"],
                    item["deviceName"],
                    item["controllable"],
                    item["retrievable"],
                    "turn" in item["supportCmds"],
                    "brightness" in item["supportCmds"],
                    "color" in item["supportCmds"],
                    "colorTem" in item["supportCmds"]
                ) for item in result["data"]["devices"]
            ]
            return light_infos

if __name__ == '__main__':
    """ test connectivity """

    async def main():
        print("Govee API client v" + _VERSION)
        print()

        if(len(sys.argv) == 1):
            print("python3 govee_api_laggat.py [command <API_KEY>]")
            print("<command>'s: ping, devices")
            print()

        command = "ping"
        api_key = ""
        if len(sys.argv) > 1:
            command = sys.argv[1]
            if len(sys.argv) > 2:
                api_key = sys.argv[2]
        
        # show usage with content manager
        async with Govee(api_key) as govee:
            if command=="ping":
                print("Ping success? " + str(await govee.ping_async()))
            elif command=="devices":
                print("Devices found: " + ", ".join([
                    item.device_name + " (" + item.device + ")"
                    for item
                    in govee.get_devices()
                ]))
        
        # show usage without content manager, but await and close()
        govee = await Govee.create(api_key)
        if command=="ping":
            print("second Ping success? " + str(await govee.ping_async()))
        await govee.close()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    