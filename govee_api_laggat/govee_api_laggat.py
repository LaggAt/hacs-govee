""" client to connect to the govee API """

import sys
import logging
import time
import datetime
import asyncio
import aiohttp
from dataclasses import dataclass
from typing import List, Tuple, Union

_LOGGER = logging.getLogger(__name__)
_API_URL = "https://developer-api.govee.com"
# API rate limit header keys
_RATELIMIT_TOTAL = 'Rate-Limit-Total' # The maximum number of requests you're permitted to make per minute.
_RATELIMIT_REMAINING = 'Rate-Limit-Remaining' # The number of requests remaining in the current rate limit window.
_RATELIMIT_RESET = 'Rate-Limit-Reset' # The time at which the current rate limit window resets in UTC epoch seconds.

@dataclass
class GoveeDevice(object):
    """ Govee Device DTO """
    device: str
    model: str
    device_name: str
    controllable: bool
    retrievable: bool
    support_turn: bool
    support_brightness: bool
    support_color: bool
    support_color_tem: bool
    
@dataclass
class GoveeDeviceState(object):
    """ State of a Govee Device DTO """
    device: str
    model: str
    online: bool
    power_state: bool
    brightness: int
    color: Tuple[ int, int, int ]

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
        self._devices = []
        self._rate_limit_on = 5 # safe available call count for multiple processes
        self._limit = 100
        self._limit_remaining = 100
        self._limit_reset = 0
        
    @classmethod
    async def create(cls, api_key: str):
        self = Govee(api_key)
        await self.__aenter__()
        return self
    
    async def close(self):
        await self.__aexit__()
    
    def _getAuthHeaders(self):
        return {'Govee-API-Key': self._api_key}

    def _track_rate_limit(self, response):
        """ rate limiting information """
        if _RATELIMIT_TOTAL in response.headers and _RATELIMIT_REMAINING in response.headers and _RATELIMIT_RESET in response.headers:
            self._limit = response.headers[_RATELIMIT_TOTAL]
            self._limit_remaining = response.headers[_RATELIMIT_REMAINING]
            self._limit_reset = response.headers[_RATELIMIT_RESET]

    async def _rate_limit(self):
        if(self._limit_remaining <= self._rate_limit_on):
            utcnow = datetime.datetime.utcnow().timestamp()
            if(self._limit_reset > utcnow):
                sleep_sec = self._limit_reset - utcnow
                _LOGGER.warn(f"Rate limiting active, {self._limit_remaining} of {self._limit} remaining, sleeping for {sleep_sec}s.")
                await asyncio.sleep(sleep_sec)
    
    @property
    def rate_limit_total(self):
        return self._limit
    
    @property
    def rate_limit_remaining(self):
        return self._limit_remaining
    
    @property
    def rate_limit_reset(self):
        return self._limit_reset

    @property
    def rate_limit_on(self):
        return self._rate_limit_on

    @rate_limit_on.setter
    def rate_limit_on(self, val):
        if val > self._limit:
            raise Exception(f"Rate limiter threshold {val} must be below {self._limit}")
        if val < 1:
            raise Exception(f"Rate limiter threshold {val} must be above 1")
        self._rate_limit_on = val
        
    
    @property
    def devices(self):
        """ returns the cached devices list """
        return self._devices
    
    async def ping_async(self) -> Tuple[ float, str ]:
        """ Ping the api endpoint. No API_KEY is needed
            Returns: timeout_ms, error
        """
        _LOGGER.debug("ping_async")
        start = time.time()
        await self._rate_limit()
        ping_ok_delay = None
        err = None

        url = (_API_URL + "/ping")
        async with self._session.get(url=url) as response:
            result = await response.text()
            self._track_rate_limit(response)
            delay = int((time.time() - start) * 1000)
            if response.status == 200:
                if 'Pong' == result:
                    ping_ok_delay = max(1, delay)
                else:
                    err = f'API-Result wrong: {result}'
            else:
                result = await response.text()
                err = f'API-Error {response.status}: {result}'
        return ping_ok_delay, err
        
            
    async def get_devices(self) -> Tuple[ List[GoveeDevice], str ]:
        """ get and cache devices, returns: list, error """
        _LOGGER.debug("get_devices")
        await self._rate_limit()
        devices = []
        err = None
        
        url = (
            _API_URL
            + "/v1/devices"
        )
        async with self._session.get(url=url, headers = self._getAuthHeaders()) as response:
            if response.status == 200:
                result = await response.json()
                devices = [
                    GoveeDevice(
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
            else:
                result = await response.text()
                err = f'API-Error {response.status}: {result}'
        # cache last get_devices result
        self._devices = devices
        return devices, err


    def _get_device(self, device:  Union[str, GoveeDevice]) -> Tuple[ str, GoveeDevice ]:
        """ get a device by address or GoveeDevice dto """
        device_str = device
        if isinstance(device, GoveeDevice):
            device_str = device.device
            if not device in self._devices:
                device = None #disallow unknown devices
        elif isinstance(device, str):
            device = next((x for x in self._devices if x.device == device_str), None)
        return device_str, device

    async def turn_on(self, device: Union[str, GoveeDevice]) -> Tuple[ bool, str ]:
        """ turn on a device, return success and error message """
        return await self._turn(device, "on")

    async def turn_off(self, device: Union[str, GoveeDevice]) -> Tuple[ bool, str ]:
        """ turn off a device, return success and error message """
        return await self._turn(device, "off")

    async def _turn(self, device: Union[str, GoveeDevice], onOff: str) -> Tuple[ bool, str ]:
        device_str, device = self._get_device(device)
        _LOGGER.debug(f'turn_{onOff} {device_str}')
        success = False
        err = None
        if not device:
            err = f'Invalid device {device_str}'
        else:
            if not device.controllable:
                err = f'Device {device.device} is not controllable'
            elif not device.support_turn:
                err = f'Turn command not possible on device {device.device}'
            else:
                await self._rate_limit()
                url = (
                    _API_URL
                    + "/v1/devices/control"
                )
                json = {
                    "device": device.device,
                    "model": device.model,
                    "cmd": {
                        "name": "turn",
                        "value": onOff
                    }
                }
                async with self._session.put(
                    url=url, 
                    headers = self._getAuthHeaders(),
                    json=json
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        success = 'message' in result and result['message'] == 'Success'
                    else:
                        result = await response.text()
                        err = f'API-Error {response.status}: {result}'

        return success, err

    async def get_state(self, device: Union[str, GoveeDevice]) -> Tuple[ GoveeDeviceState, str ]:
        device_str, device = self._get_device(device)
        _LOGGER.debug(f'get_state {device_str}')
        result = None
        err = None
        if not device:
            err = f'Invalid device {device_str}'
        else:
            await self._rate_limit()
            url = (
                _API_URL
                + "/v1/devices/state"
            )
            params = {
                'device': device.device,
                'model': device.model
            }
            async with self._session.get(
                url=url,
                headers = self._getAuthHeaders(),
                params=params
            ) as response:
                if response.status == 200:
                    json_obj = await response.json()

                    prop_online = False
                    prop_power_state = False
                    prop_brightness = False
                    prop_color = (0, 0, 0)

                    for prop in json_obj['data']['properties']:
                        # somehow these are all dicts with one element
                        if 'online' in prop:
                            prop_online = prop['online']
                        elif 'powerState' in prop:
                            prop_power_state = prop['powerState'] == 'on'
                        elif 'brightness' in prop:
                            prop_brightness = prop['brightness']
                        elif 'color' in prop:
                            prop_color = (
                                prop['color']['r'],
                                prop['color']['g'],
                                prop['color']['b']
                            )
                        else:
                            _LOGGER.warn(f'unknown state property {prop}')

                    result = GoveeDeviceState(
                        json_obj["data"]["device"],
                        json_obj["data"]["model"],
                        prop_online,
                        prop_power_state,
                        prop_brightness,
                        prop_color
                    )
                else:
                    result = await response.text()
                    err = f'API-Error {response.status}: {result}'
        return result, err

if __name__ == '__main__':
    """ some example usages """

    async def main():
        print("Govee API client")
        print()

        if(len(sys.argv) == 1):
            print("python3 govee_api_laggat.py [command <API_KEY>]")
            print("<command>'s: ping, devices, turn_on, turn_off, get_state")
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
                ping_ms, err = await govee.ping_async()
                print(f"Ping success? {bool(ping_ms)} after {ping_ms}ms")
            elif command=="devices":
                print("Devices found: " + ", ".join([
                    item.device_name + " (" + item.device + ")"
                    for item
                    in govee.get_devices()
                ]))
            elif command=="turn_on":
                devices, err = await govee.get_devices()
                for lamp in devices:
                    success, err = await govee.turn_on(lamp)
            elif command=="turn_off":
                devices, err = await govee.get_devices()
                for lamp in devices:
                    success, err = await govee.turn_off(lamp.device) # by id here
            elif command=="state":
                devices, err = await govee.get_devices()
                for lamp in devices:
                    state, err = await govee.get_state(lamp)
                    if err:
                        print(f'{lamp.device_name} error getting state: {err}')
                    else:
                        print(f'{lamp.device_name} is powered on? {state.power_state}')

        
        # show usage without content manager, but await and close()
        if command=="ping":
            govee = await Govee.create(api_key)
            ping_ms, err = await govee.ping_async()
            print(f"second Ping success? {bool(ping_ms)} after {ping_ms}ms")
            await govee.close()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    