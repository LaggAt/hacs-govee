import asyncio
import aiohttp
from contextlib import asynccontextmanager
import math
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import logging

from govee_api_laggat.govee_dtos import GoveeDevice, GoveeSource

_LOGGER = logging.getLogger(__name__)

_API_BASE_URL = "https://developer-api.govee.com"
_API_PING = _API_BASE_URL + "/ping"
_API_DEVICES = _API_BASE_URL + "/v1/devices"
_API_DEVICES_CONTROL = _API_BASE_URL + "/v1/devices/control"
_API_DEVICES_STATE = _API_BASE_URL + "/v1/devices/state"
# API rate limit header keys
_RATELIMIT_TOTAL = "Rate-Limit-Total"  # The maximum number of requests you're permitted to make per minute.
_RATELIMIT_REMAINING = "Rate-Limit-Remaining"  # The number of requests remaining in the current rate limit window.
_RATELIMIT_RESET = "Rate-Limit-Reset"  # The time at which the current rate limit window resets in UTC epoch seconds.
_RATELIMIT_RESET_MAX_SECONDS = (
    180  # The maximum time in seconds to wait for a rate limit reset
)

# return state from hisory for n seconds after controlling the device
DELAY_GET_FOLLOWING_SET_SECONDS = 2
# do not send another control within n seconds after controlling the device
DELAY_SET_FOLLOWING_SET_SECONDS = 1

# regularly discover devices
SCHEDULE_GET_DEVICES_SECONDS = 100


class GoveeApi(object):
    """Govee API client."""

    async def __aenter__(self):
        """Async context manager enter."""
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *err):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
        self._session = None

    def __init__(
        self,
        govee,
        api_key: str,
    ):
        """Init with an API_KEY and storage for learned values."""
        self._govee = govee
        self._api_key = api_key
        self._rate_limit_on = 5  # safe available call count for multiple processes
        self._limit = 100
        self._limit_remaining = 100
        self._limit_reset = 0

    @classmethod
    async def create(
        cls,
        govee,
        api_key: str,
    ):
        """Use create method if you want to use this Client without an async context manager."""
        self = GoveeApi(govee, api_key)
        await self.__aenter__()
        return self

    async def close(self):
        """Use close when your are finished with the Client without using an async context manager."""
        await self.__aexit__()

    def _getHeaders(self, auth: bool):
        """Return Request headers with/without authentication."""
        if auth:
            return {"Govee-API-Key": self._api_key}
        return {}

    @asynccontextmanager
    async def _api_put(self, *, auth=True, url: str, json):
        """API HTTP Put call."""
        async with self._api_request_internal(
            lambda: self._session.put(
                url=url, headers=self._getHeaders(auth), json=json
            )
        ) as response:
            yield response

    @asynccontextmanager
    async def _api_get(self, *, auth=True, url: str, params=None):
        """API HTTP Get call."""
        async with self._api_request_internal(
            lambda: self._session.get(
                url=url, headers=self._getHeaders(auth), params=params
            )
        ) as response:
            yield response

    @asynccontextmanager
    async def _api_request_internal(self, request_lambda):
        """API Methond handling all HTTP calls.

        This also handles:
        - rate-limiting
        - online/offline status
        """
        err = None
        await self.rate_limit_delay()
        try:
            async with request_lambda() as response:
                self._govee._set_online(True)  # we got something, so we are online
                self._track_rate_limit(response)
                # return the async content manager response
                yield response
        except aiohttp.ClientError as ex:
            # we are offline
            self._govee._set_online(False)
            err = "error from aiohttp: %s" % repr(ex)
        except Exception as ex:
            err = "unknown error: %s" % repr(ex)

        if err:

            class error_response:
                def __init__(self, err_msg):
                    self._err_msg = err_msg

                status = -1

                async def text(self):
                    return self._err_msg

            yield error_response("_api_request_internal: " + err)

    def _track_rate_limit(self, response):
        """Track rate limiting."""
        if response.status == 429:
            _LOGGER.warning(
                f"Rate limit exceeded, check if other devices also utilize the govee API"
            )
        limit_unknown = True
        if (
            _RATELIMIT_TOTAL in response.headers
            and _RATELIMIT_REMAINING in response.headers
            and _RATELIMIT_RESET in response.headers
        ):
            try:
                self._limit = int(response.headers[_RATELIMIT_TOTAL])
                self._limit_remaining = int(response.headers[_RATELIMIT_REMAINING])
                # reset rate limiting with maximum
                limit_reset = self._govee._utcnow() + _RATELIMIT_RESET_MAX_SECONDS
                limit_reset_api = float(response.headers[_RATELIMIT_RESET])
                if limit_reset_api < limit_reset:
                    # api returns valid values for rate limit reset seconds
                    limit_reset = limit_reset_api
                self._limit_reset = limit_reset
                _LOGGER.debug(
                    f"Rate limit total: {self._limit}, remaining: {self._limit_remaining} in {self.rate_limit_reset_seconds} seconds"
                )
                limit_unknown = False
            except Exception as ex:
                _LOGGER.warning(f"Error trying to get rate limits: {ex}")
        if limit_unknown:
            self._limit_remaining -= 1

    async def rate_limit_delay(self):
        """Delay a call when rate limiting is active."""
        # do we have requests left?
        if self.rate_limit_remaining <= self.rate_limit_on:
            # do we need to sleep?
            sleep_sec = self.rate_limit_reset_seconds
            if sleep_sec > 0:
                _LOGGER.warning(
                    f"Rate limiting active, {self._limit_remaining} of {self._limit} remaining, sleeping for {sleep_sec}s."
                )
                await asyncio.sleep(sleep_sec)

    @property
    def rate_limit_total(self):
        """Rate limit is counted down from this value."""
        return self._limit

    @property
    def rate_limit_remaining(self):
        """Remaining Rate limit."""
        return self._limit_remaining

    @property
    def rate_limit_reset(self):
        """UTC time in seconds when the rate limit will be reset."""
        return self._limit_reset

    @property
    def rate_limit_reset_seconds(self):
        """Seconds until the rate limit will be reset."""
        return self._limit_reset - self._govee._utcnow()

    @property
    def rate_limit_on(self):
        """Remaining calls that trigger rate limiting.

        Defaults to 5, which means there is some room for other clients.
        """
        return self._rate_limit_on

    @rate_limit_on.setter
    def rate_limit_on(self, val):
        """Set the remaining calls that trigger rate limiting."""
        if val > self._limit:
            raise GoveeError(
                f"Rate limiter threshold {val} must be below {self._limit}"
            )
        if val < 1:
            raise GoveeError(f"Rate limiter threshold {val} must be above 1")
        self._rate_limit_on = val

    async def check_connection(self) -> bool:
        """Check connection to API."""
        # TODO: ping is removed from API, get devices list here!
        try:
            # this will set self.online
            await self.ping()
        except:
            pass
        return self._govee.online

    async def ping(self) -> Tuple[float, str]:
        """Ping the api endpoint. No API_KEY is needed."""
        # TODO: ping is removed from API, remove.
        _LOGGER.debug("ping")
        start = time.time()
        ping_ok_delay = None
        err = None

        async with self._api_get(url=_API_PING, auth=False) as response:
            result = await response.text()
            delay = int((time.time() - start) * 1000)
            if response.status == 200:
                if "Pong" == result:
                    ping_ok_delay = max(1, delay)
                else:
                    err = f"API-Result wrong: {result}"
            else:
                result = await response.text()
                err = f"API-Error {response.status}: {result}"
        return ping_ok_delay, err

    async def get_devices(self) -> Tuple[List[GoveeDevice], str]:
        """Get and cache devices."""
        _LOGGER.debug("get_devices")
        err = None

        async with self._api_get(url=_API_DEVICES) as response:
            if response.status == 200:
                result = await response.json()
                if (
                    "data" in result
                    and "devices" in result["data"]
                    and isinstance(result["data"]["devices"], list)
                ):
                    timestamp = self._govee._utcnow()
                    learning_infos = await self._govee._learning_storage._read_cached()

                    for item in result["data"]["devices"]:
                        device_str = item["device"]
                        if device_str in self._govee._devices.keys():
                            # already in list
                            continue
                        model_str = item["model"]
                        is_retrievable = item["retrievable"]

                        # assuming defaults for learned/configured values
                        learned_set_brightness_max = None
                        learned_get_brightness_max = None
                        before_set_brightness_turn_on = False
                        config_offline_is_off = False  # effenctive state
                        # defaults by some conditions
                        if not is_retrievable:
                            learned_get_brightness_max = -1
                        if model_str == "H6104":
                            before_set_brightness_turn_on = True

                        # load learned/configured values
                        if device_str in learning_infos:
                            learning_info = learning_infos[device_str]
                            learned_set_brightness_max = (
                                learning_info.set_brightness_max
                            )
                            learned_get_brightness_max = (
                                learning_info.get_brightness_max
                            )
                            before_set_brightness_turn_on = (
                                learning_info.before_set_brightness_turn_on
                            )
                            config_offline_is_off = learning_info.config_offline_is_off

                        # create device DTO
                        self._govee._devices[device_str] = GoveeDevice(
                            device=device_str,
                            model=model_str,
                            device_name=item["deviceName"],
                            controllable=item["controllable"],
                            retrievable=is_retrievable,
                            support_cmds=item["supportCmds"],
                            support_turn="turn" in item["supportCmds"],
                            support_brightness="brightness" in item["supportCmds"],
                            support_color="color" in item["supportCmds"],
                            support_color_tem="colorTem" in item["supportCmds"],
                            # defaults for state
                            online=True,
                            power_state=False,
                            brightness=0,
                            color=(0, 0, 0),
                            color_temp=0,
                            timestamp=timestamp,
                            source=GoveeSource.HISTORY,
                            error=None,
                            lock_set_until=0,
                            lock_get_until=0,
                            learned_set_brightness_max=learned_set_brightness_max,
                            learned_get_brightness_max=learned_get_brightness_max,
                            before_set_brightness_turn_on=before_set_brightness_turn_on,
                            config_offline_is_off=config_offline_is_off,
                        )
                        # inform client on new devices
                        self._govee.events.new_device(self._govee._devices[device_str])

                else:
                    _LOGGER.info(
                        "API is connected, but there are no devices connected via Govee API. You may want to use Govee Home to pair your devices and connect them to WIFI."
                    )
            else:
                result = await response.text()
                err = f"API-Error {response.status}: {result}"
        # cache last get_devices result
        return self._govee.devices, err

    def _is_success_result_message(self, result) -> bool:
        """Given an aiohttp result checks if it is a success result."""
        return "message" in result and result["message"] == "Success"

    async def _turn(
        self, device: Union[str, GoveeDevice], onOff: str
    ) -> Tuple[bool, str]:
        """Turn command called by turn_on and turn_off."""
        success = False
        err = None
        device_str, device = self._govee._get_device(device)
        if not device:
            err = f"Invalid device {device_str}, {device}"
        else:
            command = "turn"
            params = onOff
            result, err = await self._control(device, command, params)
            success = False
            if not err:
                success = self._is_success_result_message(result)
                if success:
                    self._govee._update_state(
                        GoveeSource.HISTORY, device, "power_state", onOff == "on"
                    )
        return success, err

    async def set_brightness(
        self, device: Union[str, GoveeDevice], brightness: int
    ) -> Tuple[bool, str]:
        """Set brightness to 0-254."""
        success = False
        err = None
        device_str, device = self._govee._get_device(device)
        if not device:
            err = f"Invalid device {device_str}, {device}"
        else:
            if brightness < 0 or brightness > 254:
                err = f"set_brightness: invalid value {brightness}, allowed range 0 .. 254"
            else:
                if brightness > 0 and device.before_set_brightness_turn_on:
                    await self._govee.turn_on(device)
                    # api doesn't work if we don't sleep
                    await asyncio.sleep(1)
                # set brightness as 0..254
                brightness_set = brightness
                brightness_result = brightness_set
                brightness_set_100 = 0
                if brightness_set > 0:
                    brightness_set_100 = max(1, math.floor(brightness * 100 / 254))
                brightness_result_100 = math.ceil(brightness_set_100 * 254 / 100)
                if device.learned_set_brightness_max == 100:
                    # set brightness as 0..100
                    brightness_set = brightness_set_100
                    brightness_result = brightness_result_100
                command = "brightness"
                result, err = await self._control(device, command, brightness_set)
                if err:
                    # try again with 0-100 range
                    if "API-Error 400" in err:  # Unsupported Cmd Value
                        # set brightness as 0..100 as 0..254 didn't work
                        brightness_set = brightness_set_100
                        brightness_result = brightness_result_100
                        result, err = await self._control(
                            device, command, brightness_set
                        )
                        if not err:
                            device.learned_set_brightness_max = 100
                            await self._govee._learn(device)
                else:
                    if brightness_set > 100:
                        device.learned_set_brightness_max = 254
                        await self._govee._learn(device)

                if not err:
                    success = self._is_success_result_message(result)
                    if success:
                        self._govee._update_state(
                            GoveeSource.HISTORY, device, "brightness", brightness_result
                        )
                        self._govee._update_state(
                            GoveeSource.HISTORY,
                            device,
                            "power_state",
                            brightness_result > 0,
                        )
        return success, err

    async def set_color_temp(
        self, device: Union[str, GoveeDevice], color_temp: int
    ) -> Tuple[bool, str]:
        """Set color temperature to 2000-9000."""
        success = False
        err = None
        device_str, device = self._govee._get_device(device)
        if not device:
            err = f"Invalid device {device_str}, {device}"
        else:
            if color_temp < 2000 or color_temp > 9000:
                err = f"set_color_temp: invalid value {color_temp}, allowed range 2000-9000"
            else:
                command = "colorTem"
                result, err = await self._control(device, command, color_temp)
                if not err:
                    success = self._is_success_result_message(result)
                    if success:
                        self._govee._update_state(
                            GoveeSource.HISTORY, device, "color_temp", color_temp
                        )
        return success, err

    async def set_color(
        self, device: Union[str, GoveeDevice], color: Tuple[int, int, int]
    ) -> Tuple[bool, str]:
        """Set color (r, g, b) where each value may be in range 0-255 """
        success = False
        err = None
        device_str, device = self._govee._get_device(device)
        if not device:
            err = f"Invalid device {device_str}, {device}"
        else:
            if len(color) != 3:
                err = f"set_color: invalid value {color}, must be tuple with (r, g, b) values"
            else:
                red = color[0]
                green = color[1]
                blue = color[2]
                if red < 0 or red > 255:
                    err = (
                        f"set_color: invalid value {color}, red must be within 0 .. 254"
                    )
                elif green < 0 or green > 255:
                    err = f"set_color: invalid value {color}, green must be within 0 .. 254"
                elif blue < 0 or blue > 255:
                    err = f"set_color: invalid value {color}, blue must be within 0 .. 254"
                else:
                    command = "color"
                    command_color = {"r": red, "g": green, "b": blue}
                    result, err = await self._control(device, command, command_color)
                    if not err:
                        success = self._is_success_result_message(result)
                        if success:
                            self._govee._update_state(
                                GoveeSource.HISTORY, device, "color", color
                            )
        return success, err

    def _get_lock_seconds(self, utcSeconds: int) -> int:
        """Get seconds to wait."""
        seconds_lock = utcSeconds - self._govee._utcnow()
        if seconds_lock < 0:
            seconds_lock = 0
        return seconds_lock

    async def _control(
        self, device: Union[str, GoveeDevice], command: str, params: Any
    ) -> Tuple[Any, str]:
        """Control led strips and bulbs."""
        device_str, device = self._govee._get_device(device)
        cmd = {"name": command, "value": params}
        _LOGGER.debug(f"control {device_str}: {cmd}")
        result = None
        err = None
        if not device:
            err = f"Invalid device {device_str}, {device}"
        else:
            if not device.controllable:
                err = f"Device {device.device} is not controllable"
                _LOGGER.debug(f"control {device_str} not possible: {err}")
            elif not command in device.support_cmds:
                err = f"Command {command} not in supported commands on device {device.device}"
                _LOGGER.warning(f"control {device_str} not possible: {err}")
            else:
                while True:
                    seconds_locked = self._get_lock_seconds(device.lock_set_until)
                    if not seconds_locked:
                        break
                    _LOGGER.debug(
                        f"control {device_str} is locked for {seconds_locked} seconds. Command waiting: {cmd}"
                    )
                    await asyncio.sleep(seconds_locked)
                json = {"device": device.device, "model": device.model, "cmd": cmd}
                await self.rate_limit_delay()
                async with self._api_put(
                    url=_API_DEVICES_CONTROL, json=json
                ) as response:
                    if response.status == 200:
                        device.lock_set_until = (
                            self._govee._utcnow() + DELAY_SET_FOLLOWING_SET_SECONDS
                        )
                        device.lock_get_until = (
                            self._govee._utcnow() + DELAY_GET_FOLLOWING_SET_SECONDS
                        )
                        result = await response.json()
                    else:
                        text = await response.text()
                        err = f"API-Error {response.status} on command {cmd}: {text} for device {device}"
                        _LOGGER.warning(f"control {device_str} failed: {err}")
        return result, err

    async def _get_device_state(
        self, device: Union[str, GoveeDevice]
    ) -> Tuple[GoveeDevice, str]:
        """Get state for one specific device."""
        device_str, device = self._govee._get_device(device)
        result = None
        err = None
        seconds_locked = self._get_lock_seconds(device.lock_get_until)
        if not device:
            err = f"Invalid device {device_str}"
        elif not device.retrievable:
            # device {device_str} isn't able to return state, return 'history' state
            self._govee._update_state(
                GoveeSource.HISTORY, device_str, "source", GoveeSource.HISTORY
            )
            result = device
        elif seconds_locked:
            # we just changed something, return state from history
            self._govee._update_state(
                GoveeSource.HISTORY, device_str, "source", GoveeSource.HISTORY
            )
            result = device
            _LOGGER.debug(
                f"state object returned from cache: {result}, next state for {device.device} from api allowed in {seconds_locked} seconds"
            )
        else:
            params = {"device": device.device, "model": device.model}
            async with self._api_get(url=_API_DEVICES_STATE, params=params) as response:
                if response.status == 200:
                    json_obj = await response.json()
                    if not json_obj:
                        err = f"API returned OK but no valid json."
                        result = device
                    else:
                        prop_online = False
                        prop_power_state = False
                        prop_brightness = False
                        prop_color = (0, 0, 0)
                        prop_color_temp = 0

                        for prop in json_obj["data"]["properties"]:
                            # somehow these are all dicts with one element
                            if "online" in prop:
                                prop_online = prop["online"] in [True, "true"]
                            elif "powerState" in prop:
                                prop_power_state = prop["powerState"] == "on"
                            elif "brightness" in prop:
                                prop_brightness = prop["brightness"]
                            elif "color" in prop:
                                prop_color = (
                                    prop["color"]["r"],
                                    prop["color"]["g"],
                                    prop["color"]["b"],
                                )
                            elif "colorTemInKelvin" in prop:
                                prop_color_temp = prop["colorTemInKelvin"]
                            else:
                                _LOGGER.debug(f"unknown state property '{prop}'")

                        if not prop_online:
                            if self._govee.config_offline_is_off is not None:
                                # global option
                                if self._govee.config_offline_is_off:
                                    prop_power_state = False
                            elif device.config_offline_is_off:
                                # learning option
                                prop_power_state = False

                        # autobrightness learning
                        if device.learned_get_brightness_max == None or (
                            device.learned_get_brightness_max == 100
                            and prop_brightness > 100
                        ):
                            device.learned_get_brightness_max = (
                                100  # assumption, as we didn't get anything higher
                            )
                            if prop_brightness > 100:
                                device.learned_get_brightness_max = 254
                            await self._govee._learn(device)
                        if device.learned_get_brightness_max == 100:
                            # scale range 0-100 up to 0-254
                            prop_brightness = math.floor(prop_brightness * 254 / 100)

                        self._govee._update_state(
                            GoveeSource.API, device, "error", None
                        )
                        self._govee._update_state(
                            GoveeSource.API, device, "online", prop_online
                        )
                        self._govee._update_state(
                            GoveeSource.API, device, "power_state", prop_power_state
                        )
                        self._govee._update_state(
                            GoveeSource.API, device, "brightness", prop_brightness
                        )
                        self._govee._update_state(
                            GoveeSource.API, device, "color", prop_color
                        )
                        self._govee._update_state(
                            GoveeSource.API, device, "color_temp", prop_color_temp
                        )
                        result = device

                        _LOGGER.debug(
                            f"state returned from API: {json_obj}, resulting state object: {result}"
                        )
                else:
                    result = device
                    errText = await response.text()
                    err = f"API-Error {response.status}: {errText}"
        return result, err
