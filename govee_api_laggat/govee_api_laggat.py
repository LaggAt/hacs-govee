""" client to connect to the govee API """

from govee_api_laggat.learning_storage import GoveeAbstractLearningStorage, GoveeLearnedInfo
import aiohttp
import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
import sys
import time
from typing import List, Tuple, Union, Optional, Any

_LOGGER = logging.getLogger(__name__)
_API_URL = "https://developer-api.govee.com"
# API rate limit header keys
_RATELIMIT_TOTAL = 'Rate-Limit-Total' # The maximum number of requests you're permitted to make per minute.
_RATELIMIT_REMAINING = 'Rate-Limit-Remaining' # The number of requests remaining in the current rate limit window.
_RATELIMIT_RESET = 'Rate-Limit-Reset' # The time at which the current rate limit window resets in UTC epoch seconds.

# return state from hisory for n seconds after controlling the device
DELAY_GET_FOLLOWING_SET_SECONDS = 2
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
    online: bool
    power_state: bool
    brightness: int
    color: Tuple[ int, int, int ]
    timestamp: int
    source: str
    error: str
    lock_set_until: int
    lock_get_until: int
    learned_set_brightness_max: int
    learned_get_brightness_max: int
    
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
    
    def __init__(self, api_key: str, *, 
            learning_storage: Optional[GoveeAbstractLearningStorage] = None
        ):
        """ init with an API_KEY """
        self._api_key = api_key
        self._devices = {}
        self._rate_limit_on = 5 # safe available call count for multiple processes
        self._limit = 100
        self._limit_remaining = 100
        self._limit_reset = 0
        self._learning_storage = learning_storage
        if not self._learning_storage:
            # use an internal learning storage as long as we run.
            # we will need to re-learn every time again.
            self._learning_storage = GoveeAbstractLearningStorage()

        
    @classmethod
    async def create(cls, api_key: str, *, 
            learning_storage: Optional[GoveeAbstractLearningStorage] = None
        ):
        self = Govee(api_key, learning_storage=learning_storage)
        await self.__aenter__()
        return self
    
    async def close(self):
        await self.__aexit__()
    
    def _getAuthHeaders(self):
        return {'Govee-API-Key': self._api_key}

    def _utcnow(self):
        return datetime.timestamp(datetime.now())

    def _track_rate_limit(self, response):
        """ rate limiting information """
        if response.status == 429:
            _LOGGER.warning(f'Rate limit exceeded, check if other devices also utilize the govee API')
        limit_unknown = True
        if(_RATELIMIT_TOTAL in response.headers and _RATELIMIT_REMAINING in response.headers and _RATELIMIT_RESET in response.headers):
            try:
                self._limit = int(response.headers[_RATELIMIT_TOTAL])
                self._limit_remaining = int(response.headers[_RATELIMIT_REMAINING])
                self._limit_reset = float(response.headers[_RATELIMIT_RESET])
                _LOGGER.debug(f'Rate limit total: {self._limit}, remaining: {self._limit_remaining} in {self.rate_limit_reset_seconds} seconds')
                limit_unknown = False
            except Exception as ex:
                _LOGGER.warning(f'Error trying to set rate limits: {ex}')
        if limit_unknown:
            self._limit_remaining = 0
            self._limit_reset = float(self._utcnow() + 5)
            _LOGGER.warning(f'Rate limits are unknown, next request is 5 seconds delayed, response headers: {response.headers}')

    async def rate_limit_delay(self):
        # do we have requests left?
        if self.rate_limit_remaining <= self.rate_limit_on:
            # do we need to sleep?
            sleep_sec = self.rate_limit_reset_seconds
            if sleep_sec > 0:
                _LOGGER.warning(f"Rate limiting active, {self._limit_remaining} of {self._limit} remaining, sleeping for {sleep_sec}s.")
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
        return self._limit_reset - self._utcnow()

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
    def devices(self) -> List[GoveeDevice]:
        """ returns the cached devices list """
        lst = []
        for dev in self._devices:
            lst.append(self._devices[dev])
        return lst
    
    def device(self, device) -> GoveeDevice:
        """ returns the cached device """
        _, device = self._get_device(device)
        return device

    async def ping(self) -> Tuple[ float, str ]:
        """ Ping the api endpoint. No API_KEY is needed
            Returns: timeout_ms, error
        """
        _LOGGER.debug("ping")
        start = time.time()
        ping_ok_delay = None
        err = None

        url = (_API_URL + "/ping")
        await self.rate_limit_delay()
        async with self._session.get(url=url) as response:
            # no rate limit header fields exist on ping
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
        devices = {}
        err = None
        
        url = (
            _API_URL
            + "/v1/devices"
        )
        await self.rate_limit_delay()
        async with self._session.get(url=url, headers = self._getAuthHeaders()) as response:
            self._track_rate_limit(response)
            if response.status == 200:
                result = await response.json()
                timestamp = self._utcnow()
                
                learning_infos = await self._learning_storage._read_cached()

                for item in result["data"]["devices"]:
                    device_str = item["device"]

                    # assuming max values for control and feedback of brightness
                    learned_set_brightness_max = None
                    learned_get_brightness_max = None
                    if device_str in learning_infos:
                        learning_info = learning_infos[device_str]
                        learned_set_brightness_max = learning_info.set_brightness_max
                        learned_get_brightness_max = learning_info.get_brightness_max
                    if not item["retrievable"]:
                        learned_get_brightness_max = -1

                    # create device DTO
                    devices[device_str] = GoveeDevice(
                        device = device_str,
                        model = item["model"],
                        device_name = item["deviceName"],
                        controllable = item["controllable"],
                        retrievable = item["retrievable"],
                        support_cmds = item["supportCmds"],
                        support_turn = "turn" in item["supportCmds"],
                        support_brightness = "brightness" in item["supportCmds"],
                        support_color = "color" in item["supportCmds"],
                        support_color_tem = "colorTem" in item["supportCmds"],
                        # defaults for state
                        online = True,
                        power_state = False,
                        brightness = 0,
                        color = (0, 0, 0), 
                        timestamp = timestamp,
                        source = 'history',
                        error = None,
                        lock_set_until = 0,
                        lock_get_until = 0,
                        learned_set_brightness_max = learned_set_brightness_max,
                        learned_get_brightness_max = learned_get_brightness_max,
                    )
            else:
                result = await response.text()
                err = f'API-Error {response.status}: {result}'
        # cache last get_devices result
        self._devices = devices
        return self.devices, err


    def _get_device(self, device:  Union[str, GoveeDevice]) -> Tuple[ str, GoveeDevice ]:
        """ get a device by address or GoveeDevice dto """
        device_str = device
        if isinstance(device, GoveeDevice):
            device_str = device.device
            if not device_str in self._devices:
                device = None #disallow unknown devices
        elif isinstance(device, str) and device_str in self._devices:
            device = self._devices[device_str]
        return device_str, device

    def _is_success_result_message(self, result) -> bool:
        return 'message' in result and result['message'] == 'Success'

    async def turn_on(self, device: Union[str, GoveeDevice]) -> Tuple[ bool, str ]:
        """ turn on a device, return success and error message """
        return await self._turn(device, "on")

    async def turn_off(self, device: Union[str, GoveeDevice]) -> Tuple[ bool, str ]:
        """ turn off a device, return success and error message """
        return await self._turn(device, "off")

    async def _turn(self, device: Union[str, GoveeDevice], onOff: str) -> Tuple[ bool, str ]:
        success = False
        err = None
        device_str, device = self._get_device(device)
        if not device:
            err = f'Invalid device {device_str}, {device}'
        else:
            command = "turn"
            params = onOff
            result, err = await self._control(device, command, params)
            success = False
            if not err:
                success = self._is_success_result_message(result)
                if success:
                    self._devices[device_str].timestamp = self._utcnow
                    self._devices[device_str].source = 'history'
                    self._devices[device_str].power_state = onOff == "on"
        return success, err

    async def set_brightness(self, device: Union[str, GoveeDevice], brightness: int) -> Tuple[ bool, str ]:
        """ set brightness to 0 .. 254 (converted to 0 .. 100 for control on some devices) """
        success = False
        err = None
        device_str, device = self._get_device(device)
        if not device:
            err = f'Invalid device {device_str}, {device}'
        else:
            if brightness < 0 or brightness > 254:
                err = f'set_brightness: invalid value {brightness}, allowed range 0 .. 254'
            else:
                # set brightness as 0..254
                brightness_set = brightness
                brightness_set_100 = brightness * 100 // 254
                if device.learned_set_brightness_max == 100:
                    # set brightness as 0..100
                    brightness_set = brightness_set_100
                command = "brightness"
                result, err = await self._control(device, command, brightness_set)
                if err:
                    # try again with 0-100 range
                    if device.learned_set_brightness_max == None and "API-Error 400" in err:
                        # set brightness as 0..100 as 0..254 didn't work
                        brightness_set = brightness_set_100
                        result, err = await self._control(device, command, brightness_set)
                        if not err:
                            device.learned_set_brightness_max = 100
                            await self._learn(device)
                else:
                    device.learned_set_brightness_max = 254
                    await self._learn(device)

                if not err:
                    success = self._is_success_result_message(result)
                    if success:
                        self._devices[device_str].timestamp = self._utcnow
                        self._devices[device_str].source = 'history'
                        self._devices[device_str].brightness = brightness
                        self._devices[device_str].power_state = brightness > 0
        return success, err

    async def _learn(self, device):
        """Persist learned information from device DTO."""
        learning_infos: Dict[str, GoveeLearnedInfo] = await self._learning_storage._read_cached()
        # init Dict and entry for device
        if learning_infos == None:
            learning_infos = {}
        if device.device not in learning_infos:
            learning_infos[device.device] = GoveeLearnedInfo()
        # output what was lerned, and learn
        if learning_infos[device.device].set_brightness_max != device.learned_set_brightness_max:
            _LOGGER.debug("learned device %s uses range 0-%s for setting brightness.", device.device, device.learned_set_brightness_max)
            learning_infos[device.device].set_brightness_max = device.learned_set_brightness_max
        if learning_infos[device.device].get_brightness_max != device.learned_get_brightness_max:
            _LOGGER.debug("learned device %s uses range 0-%s for getting brightness state.", device.device, device.learned_get_brightness_max)
            if device.learned_get_brightness_max == 100:
                _LOGGER.info("brightness range for %s is assumed. If the brightness slider doesn't match the actual brightness pull the brightness up to max once.", device.device)
            learning_infos[device.device].get_brightness_max = device.learned_get_brightness_max
        
        await self._learning_storage._write_cached(learning_infos)

    async def set_color_temp(self, device: Union[str, GoveeDevice], color_temp: int) -> Tuple[ bool, str ]:
        """ set color temperature to 2000 .. 9000."""
        success = False
        err = None
        device_str, device = self._get_device(device)
        if not device:
            err = f'Invalid device {device_str}, {device}'
        else:
            if color_temp < 2000 or color_temp > 9000:
                err = f'set_color_temp: invalid value {color_temp}, allowed range 2000 .. 9000'
            else:
                command = "colorTem"
                result, err = await self._control(device, command, color_temp)
                if not err:
                    success = self._is_success_result_message(result)
                    if success:
                        self._devices[device_str].timestamp = self._utcnow
                        self._devices[device_str].source = 'history'
                        self._devices[device_str].color_temp = color_temp
        return success, err

    async def set_color(self, device: Union[str, GoveeDevice], color: Tuple[ int, int, int ]) -> Tuple[ bool, str ]:
        """ set color (r, g, b) where each value may be in range 0 .. 255 """
        success = False
        err = None
        device_str, device = self._get_device(device)
        if not device:
            err = f'Invalid device {device_str}, {device}'
        else:
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
                    if not err:
                        success = self._is_success_result_message(result)
                        if success:
                            self._devices[device_str].timestamp = self._utcnow
                            self._devices[device_str].source = 'history'
                            self._devices[device_str].color = color
        return success, err

    def _get_lock_seconds(self, utcSeconds: int) -> int:
        seconds_lock = utcSeconds - self._utcnow()
        if(seconds_lock < 0):
            seconds_lock = 0
        return seconds_lock

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
            seconds_locked = self._get_lock_seconds(device.lock_set_until)
            if not device.controllable:
                err = f'Device {device.device} is not controllable'
            elif seconds_locked:
                err = f'Device {device.device} is locked for control next {sec} seconds'
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
                await self.rate_limit_delay()
                async with self._session.put(
                    url=url, 
                    headers = self._getAuthHeaders(),
                    json=json
                ) as response:
                    self._track_rate_limit(response)
                    if response.status == 200:
                        device.lock_get_until = self._utcnow() + DELAY_GET_FOLLOWING_SET_SECONDS
                        result = await response.json()
                    else:
                        text = await response.text()
                        err = f'API-Error {response.status} on command {cmd}: {text} for device {device}'
        return result, err

    async def get_states(self) -> List[GoveeDevice]:
        _LOGGER.debug('get_states')
        for device_str in self._devices:
            state, err = await self._get_device_state(device_str)
            if err:
                self._devices[device_str].error = err
            else:
                self._devices[device_str] = state
                self._devices[device_str].error = None
        return self.devices

    async def _get_device_state(self, device: Union[str, GoveeDevice]) -> Tuple[ GoveeDevice, str ]:
        device_str, device = self._get_device(device)
        result = None
        err = None
        seconds_locked = self._get_lock_seconds(device.lock_get_until)
        if not device:
            err = f'Invalid device {device_str}'
        elif not device.retrievable:
            # device {device_str} isn't able to return state, return 'history' state
            self._devices[device_str].source = 'history'
            result = self._devices[device_str]
        elif seconds_locked:
            # we just changed something, return state from history
            self._devices[device_str].source = 'history'
            result = self._devices[device_str]
            _LOGGER.debug(f'state object returned from cache: {result}, next state for {device.device} from api allowed in {seconds_locked} seconds')
        else:
            url = (
                _API_URL
                + "/v1/devices/state"
            )
            params = {
                'device': device.device,
                'model': device.model
            }
            await self.rate_limit_delay()
            async with self._session.get(
                url=url,
                headers = self._getAuthHeaders(),
                params=params
            ) as response:
                self._track_rate_limit(response)
                if response.status == 200:
                    timestamp = self._utcnow()
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
                            _LOGGER.warning(f'unknown state property {prop}')

                    #autobrightness learning
                    if device.learned_get_brightness_max == None \
                        or ( \
                            device.learned_get_brightness_max == 100 \
                            and prop_brightness > 100 \
                        ):
                        device.learned_get_brightness_max = 100  # assumption, as we didn't get anything higher
                        if prop_brightness > 100:
                            device.learned_get_brightness_max = 254
                        await self._learn(device)
                    if device.learned_get_brightness_max == 100:
                        # scale range 0-100 up to 0-254
                        prop_brightness = prop_brightness * 254 // 100

                    result = self._devices[device_str]
                    result.online = prop_online
                    result.power_state = prop_power_state
                    result.brightness = prop_brightness
                    result.color = prop_color
                    result.timestamp = timestamp
                    result.source = 'api'
                    result.error = None

                    _LOGGER.debug(f'state returned from API: {json_obj}, resulting state object: {result}')
                else:
                    errText = await response.text()
                    err = f'API-Error {response.status}: {errText}'
        return result, err
