""" client to connect to the govee API """

import sys
import logging
import time
from datetime import datetime
import asyncio
import aiohttp
from dataclasses import dataclass
from typing import List, Tuple, Union, Any

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
    support_cmds: List[str]
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
        if(_RATELIMIT_TOTAL in response.headers and _RATELIMIT_REMAINING in response.headers and _RATELIMIT_RESET in response.headers):
            try:
                self._limit = int(response.headers[_RATELIMIT_TOTAL])
                self._limit_remaining = int(response.headers[_RATELIMIT_REMAINING])
                self._limit_reset = float(response.headers[_RATELIMIT_RESET])
            except ex:
                _LOGGER.warn(f'Cannot track rate limits, response headers: {response.headers}')

    async def _rate_limit(self):
        if self._limit_remaining <= self._rate_limit_on:
            sleep_sec = self.rate_limit_reset_seconds
            if sleep_sec > 0:
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
    def rate_limit_reset_seconds(self):
        utcnow = datetime.timestamp(datetime.now())
        return self._limit_reset - utcnow

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
        ping_ok_delay = None
        err = None

        url = (_API_URL + "/ping")
        await self._rate_limit()
        async with self._session.get(url=url) as response:
            self._track_rate_limit(response)
            result = await response.text()
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
        devices = []
        err = None
        
        url = (
            _API_URL
            + "/v1/devices"
        )
        await self._rate_limit()
        async with self._session.get(url=url, headers = self._getAuthHeaders()) as response:
            self._track_rate_limit(response)
            if response.status == 200:
                result = await response.json()
                devices = [
                    GoveeDevice(
                        device = item["device"],
                        model = item["model"],
                        device_name = item["deviceName"],
                        controllable = item["controllable"],
                        retrievable = item["retrievable"],
                        support_cmds = item["supportCmds"],
                        support_turn = "turn" in item["supportCmds"],
                        support_brightness = "brightness" in item["supportCmds"],
                        support_color = "color" in item["supportCmds"],
                        support_color_tem = "colorTem" in item["supportCmds"]
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

    def _is_success_result_message(self, result) -> bool:
        return 'message' in result and result['message'] == 'Success'

    async def _turn(self, device: Union[str, GoveeDevice], onOff: str) -> Tuple[ bool, str ]:
        command = "turn"
        params = onOff
        result, err = await self._control(device, command, params)
        success = False
        if not err:
            success = self._is_success_result_message(result)
        return success, err

    async def set_brightness(self, device: Union[str, GoveeDevice], brightness: int) -> Tuple[ bool, str ]:
        """ set brightness to 0 .. 254 (converted to 0 .. 100 for control)
            Govee state returns brightness in the range 0 .. 254, but for setting you need to use 0 .. 100
        """
        success = False
        err = None
        if brightness < 0 or brightness > 254:
            err = f'set_brightness: invalid value {brightness}, allowed range 0 .. 254'
        else:
            brightness_100 = brightness * 100 // 254
            success, err = await self.set_brightness_100(device, brightness_100)
        return success, err

    async def set_brightness_100(self, device: Union[str, GoveeDevice], brightness: int) -> Tuple[ bool, str ]:
        """ set brightness to 0 .. 100 """
        success = False
        err = None
        if brightness < 0 or brightness > 100:
            err = f'set_brightness100: invalid value {brightness}, allowed range 0 .. 100'
        else:
            command = "brightness"
            result, err = await self._control(device, command, brightness)
            success = False
            if not err:
                success = self._is_success_result_message(result)
        return success, err

    async def set_color_temp(self, device: Union[str, GoveeDevice], color_temp: int) -> Tuple[ bool, str ]:
        """ set color temperature to 2000 .. 9000 """
        success = False
        err = None
        if color_temp < 2000 or color_temp > 9000:
            err = f'set_color_temp: invalid value {color_temp}, allowed range 2000 .. 9000'
        else:
            command = "colorTem"
            result, err = await self._control(device, command, color_temp)
            success = False
            if not err:
                success = self._is_success_result_message(result)
        return success, err

    async def set_color(self, device: Union[str, GoveeDevice], color: Tuple[ int, int, int ]) -> Tuple[ bool, str ]:
        """ set color (r, g, b) where each value may be in range 0 .. 255 """
        success = False
        err = None
        if len(color) != 3:
            err = f'set_color: invalid value {color}, must be tuple with (r, g, b) values'
        else:
            red = color[0]
            green = color[1]
            blue = color[2]
            if red < 0 or red > 255:
                err = f'set_color: invalid value {color}, red must be within 0 .. 254'
            elif green < 0 or green > 255:
                err = f'set_color: invalid value {color}, green must be within 0 .. 254'
            elif blue < 0 or blue > 255:
                err = f'set_color: invalid value {color}, blue must be within 0 .. 254'
            else:
                command = "color"
                command_color = {"r": red, "g": green, "b": blue}
                result, err = await self._control(device, command, command_color)
                success = False
                if not err:
                    success = self._is_success_result_message(result)
        return success, err

    async def _control(self, device: Union[str, GoveeDevice], command: str, params: Any) -> Tuple[ Any, str ]:
        device_str, device = self._get_device(device)
        cmd = {
            "name": command,
            "value": params
        }
        _LOGGER.debug(f'control {device_str}: {cmd}')
        result = None
        err = None
        if not device:
            err = f'Invalid device {device_str}, {device}'
        else:
            if not device.controllable:
                err = f'Device {device.device} is not controllable'
            elif not command in device.support_cmds:
                err = f'Command {command} not possible on device {device.device}'
            else:
                url = (
                    _API_URL
                    + "/v1/devices/control"
                )
                json = {
                    "device": device.device,
                    "model": device.model,
                    "cmd": cmd
                }
                await self._rate_limit()
                async with self._session.put(
                    url=url, 
                    headers = self._getAuthHeaders(),
                    json=json
                ) as response:
                    self._track_rate_limit(response)
                    if response.status == 200:
                        result = await response.json()
                    else:
                        text = await response.text()
                        err = f'API-Error {response.status} on command {cmd}: {text} for device {device}'
        return result, err

    async def get_state(self, device: Union[str, GoveeDevice]) -> Tuple[ GoveeDeviceState, str ]:
        device_str, device = self._get_device(device)
        _LOGGER.debug(f'get_state {device_str}')
        result = None
        err = None
        if not device:
            err = f'Invalid device {device_str}'
        else:
            url = (
                _API_URL
                + "/v1/devices/state"
            )
            params = {
                'device': device.device,
                'model': device.model
            }
            await self._rate_limit()
            async with self._session.get(
                url=url,
                headers = self._getAuthHeaders(),
                params=params
            ) as response:
                self._track_rate_limit(response)
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
                        device = json_obj["data"]["device"],
                        model = json_obj["data"]["model"],
                        online = prop_online,
                        power_state = prop_power_state,
                        brightness = prop_brightness,
                        color = prop_color
                    )
                else:
                    errText = await response.text()
                    err = f'API-Error {response.status}: {result}'
        return result, err

