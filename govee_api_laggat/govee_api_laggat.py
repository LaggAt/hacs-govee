"""Govee API client package."""

import asyncio
import logging
import time
import math
from datetime import datetime
from events import Events
from typing import Any, Dict, List, Optional, Tuple, Union
import os

from govee_api_laggat.__version__ import VERSION
from govee_api_laggat.api import GoveeApi
from govee_api_laggat.ble import GoveeBle
from govee_api_laggat.govee_dtos import GoveeDevice, GoveeSource
from govee_api_laggat.learning_storage import (
    GoveeAbstractLearningStorage,
    GoveeLearnedInfo,
)

_LOGGER = logging.getLogger(__name__)

ERR_MESSAGE_NO_ACTIVE_IMPL = "No implementation is available for that action."


class GoveeError(Exception):
    """Base Exception thrown from govee_api_laggat."""


class GoveeDeviceNotFound(GoveeError):
    """Device is unknown."""


class Govee(object):
    """Govee client."""

    async def __aenter__(self, *args, **kwargs):
        """Async context manager enter."""
        # self._session = aiohttp.ClientSession()
        await self._scheduler_start()
        if self._api_key:
            self._api = await GoveeApi.create(self, self._api_key)
        return self

    async def __aexit__(self, *err):
        """Async context manager exit."""
        await self._scheduler_stop()
        # if self._session:
        #    await self._session.close()
        # self._session = None
        if self._api:
            await self._api.close()

    async def _scheduler_start(self):
        """Start tasks which we need to do regularly."""
        self._tasks = [asyncio.create_task(self._schedule_get_devices())]

    async def _scheduler_stop(self):
        for task in self._tasks:
            task.cancel()

    def __init__(
        self,
        api_key: str,
        *,
        learning_storage: Optional[GoveeAbstractLearningStorage] = None,
    ):
        """Init with an API_KEY and storage for learned values."""
        _LOGGER.debug("govee_api_laggat v%s", VERSION)
        self._api_key = api_key
        self._api = None
        self._online = False
        self.events = Events()
        self._ble = GoveeBle(self)
        self._ignore_fields = self._get_empty_ignore_fields()
        self._devices = {}
        self._config_offline_is_off = None
        self._learning_storage = learning_storage
        if not self._learning_storage:
            # use an internal learning storage as long as we run.
            # we will need to re-learn every time again.
            self._learning_storage = GoveeAbstractLearningStorage()

    @classmethod
    async def create(
        cls,
        api_key: str,
        *,
        learning_storage: Optional[GoveeAbstractLearningStorage] = None,
    ):
        """Use create method if you want to use this Client without an async context manager."""
        self = Govee(api_key, learning_storage=learning_storage)
        await self.__aenter__()
        return self

    async def close(self):
        """Use close when your are finished with the Client without using an async context manager."""
        await self.__aexit__()

    def _utcnow(self):
        """Helper method to get utc now as seconds."""
        return datetime.timestamp(datetime.now())

    @property
    def rate_limit_total(self):
        """Rate limit is counted down from this value."""
        if not self._api:
            return "API not connected."
        return self._api._limit

    @property
    def rate_limit_remaining(self):
        """Remaining Rate limit."""
        if not self._api:
            return "API not connected."
        return self._api._limit_remaining

    @property
    def rate_limit_reset(self):
        """UTC time in seconds when the rate limit will be reset."""
        if not self._api:
            return "API not connected."
        return self._api._limit_reset

    @property
    def rate_limit_reset_seconds(self):
        """Seconds until the rate limit will be reset."""
        if not self._api:
            return "API not connected."
        return self._api._limit_reset - self._utcnow()

    @property
    def rate_limit_on(self):
        """Remaining calls that trigger rate limiting.

        Defaults to 5, which means there is some room for other clients.
        """
        if not self._api:
            return "API not connected."
        return self._api._rate_limit_on

    @rate_limit_on.setter
    def rate_limit_on(self, val):
        """Set the remaining calls that trigger rate limiting."""
        if not self._api:
            return "API not connected."
        if val > self._api._limit:
            raise GoveeError(
                f"Rate limiter threshold {val} must be below {self._limit}"
            )
        if val < 1:
            raise GoveeError(f"Rate limiter threshold {val} must be above 1")
        self._api._rate_limit_on = val

    @property
    def config_offline_is_off(self):
        """Get the global config option config_offline_is_off."""
        return self._config_offline_is_off

    @config_offline_is_off.setter
    def config_offline_is_off(self, val: bool):
        """
        Set global behavour when device is offline.

        None: default, use config_offline_is_off from learning, or False by default.
        False: an offline device doesn't change power state.
        True: an offline device is shown as off.
        """
        self._config_offline_is_off = val

    def _get_empty_ignore_fields(self):
        return {
            GoveeSource.API: [],
            GoveeSource.HISTORY: [],
            GoveeSource.BLE: [],
        }

    def ignore_device_attributes(self, ignore_str: str):
        """
        Set a semicolon-separated list of properties to ignore from source API or HISTORY (which means: remembered values on commands)

        Examples:
        "API:online;HISTORY:power_state": ignore online from API, ignore power_state from HISTORY
        "API:power_state": ignore power state from API
        """
        ignore_fields = self._get_empty_ignore_fields()
        is_ignored = False
        if ignore_str:
            pair_list = ignore_str.split(";")
            for pair in pair_list:
                pair = pair.strip()
                if pair:
                    pair_details = pair.split(":")
                    if len(pair_details) != 2:
                        raise GoveeError(
                            "Format of '%s' is incorrect, use 'source:attribute;...'"
                            % (pair,)
                        )
                    src, field = pair_details
                    src = src.lower()
                    field = field.lower()
                    src_strings = {
                        "api": GoveeSource.API,
                        "history": GoveeSource.HISTORY,
                        "ble": GoveeSource.BLE,
                    }
                    if src not in src_strings:
                        raise GoveeError(
                            "Cannot disable attributes for source '%s' as source must be in %s."
                            % (
                                src,
                                repr(src_strings.keys),
                            )
                        )
                    if field not in GoveeDevice.__dataclass_fields__:
                        raise GoveeError(
                            "Cannot disable attribute '%s' as GoveeDevice does not have such an attribute. Available fields (not all work): "
                            % (
                                field,
                                repr(GoveeDevice.__dataclass_fields__),
                            )
                        )
                    if src not in ignore_fields[src_strings[src]]:
                        ignore_fields[src_strings[src]].append(field)
                        is_ignored = True
        self._ignore_fields = ignore_fields
        if is_ignored:
            _LOGGER.warning(
                "Set to ignore some attributes: %s", repr(self._ignore_fields)
            )

    def _update_state(
        self,
        source: GoveeSource,
        device_str: Union[str, GoveeDevice],
        field: str,
        val: any,
    ) -> bool:
        """This is used to update state once it is created."""
        device = self.device(device_str)
        if device is None:
            _LOGGER.warning(
                "Device %s does not exist, cannot update state field %s to %s",
                device.device,
                field,
                val,
            )
            return False
        if field not in dir(device):
            _LOGGER.warning(
                "Field %s does not exist on device %s, cannot update to %s",
                field,
                device.device,
                val,
            )
            return False
        if field.lower() in self._ignore_fields[source]:
            _LOGGER.warning(
                "I do not set field %s on Device %s to %s because it is disabled by you.",
                field,
                device.device,
                val,
            )
            # this is no error
            return True
        setattr(device, field, val)
        device.source = source
        device.timestamp = self._utcnow()
        return True

    @property
    def devices(self) -> List[GoveeDevice]:
        """Cached devices list."""
        lst = []
        for dev in self._devices:
            lst.append(self._devices[dev])
        return lst

    def device(self, device: Union[str, GoveeDevice]) -> GoveeDevice:
        """Single device from cache."""
        _, device = self._get_device(device)
        return device

    @property
    def online(self):
        """Last request was able to connect to the API."""
        return self._online

    def _set_online(self, online: bool):
        """Set the online state and fire an event on change."""
        if self._online != online:
            self._online = online
            # inform about state change
            self.events.online(self._online)
        if not online:
            # show all devices as offline
            for device in self.devices:
                self._update_state(GoveeSource.API, device, "online", False)

    async def check_connection(self) -> bool:
        """Check connection to API."""
        if self._api:
            return await self._api.check_connection()
        return self.online

    async def _schedule_get_devices(self):
        """Infinite loop discovering new devices."""
        while True:
            await asyncio.sleep(SCHEDULE_GET_DEVICES_SECONDS)
            _LOGGER.debug(
                "get_devices() started by schedule after %s"
                % SCHEDULE_GET_DEVICES_SECONDS
            )
            await self.get_devices()

    async def get_devices(self) -> Tuple[List[GoveeDevice], str]:
        """Get and cache devices."""
        _LOGGER.debug("get_devices")
        err = ERR_MESSAGE_NO_ACTIVE_IMPL
        if self._api:
            err = None
            _, err_api = await self._api.get_devices()
            if err_api:
                err = f"API: {err_api}"

        return self.devices, err

    def _get_device(self, device: Union[str, GoveeDevice]) -> Tuple[str, GoveeDevice]:
        """Get a device by address or GoveeDevice DTO.

        returns: device_address, device_dto
        """
        device_str = device
        if isinstance(device, GoveeDevice):
            device_str = device.device
            if not device_str in self._devices:
                device = None  # disallow unknown devices
        elif isinstance(device, str) and device_str in self._devices:
            device = self._devices[device_str]
        else:
            raise GoveeDeviceNotFound(device_str)
        return device_str, device

    async def turn_on(self, device: Union[str, GoveeDevice]) -> Tuple[bool, str]:
        """Turn on a device, return success and error message."""
        return await self._turn(device, "on")

    async def turn_off(self, device: Union[str, GoveeDevice]) -> Tuple[bool, str]:
        """Turn off a device, return success and error message."""
        return await self._turn(device, "off")

    async def _turn(
        self, device: Union[str, GoveeDevice], onOff: str
    ) -> Tuple[bool, str]:
        """Turn command called by turn_on and turn_off."""
        success = False
        err = None
        if self._api:
            return await self._api._turn(device, onOff)
        return success, ERR_MESSAGE_NO_ACTIVE_IMPL

    async def set_brightness(
        self, device: Union[str, GoveeDevice], brightness: int
    ) -> Tuple[bool, str]:
        """Set brightness to 0-254."""
        success = False
        err = None
        if self._api:
            return await self._api.set_brightness(device, brightness)
        return success, ERR_MESSAGE_NO_ACTIVE_IMPL

    async def _learn(self, device):
        """Persist learned information from device DTO."""
        learning_infos: Dict[
            str, GoveeLearnedInfo
        ] = await self._learning_storage._read_cached()
        changed = False
        # init Dict and entry for device
        if learning_infos == None:
            learning_infos = {}
        if device.device not in learning_infos:
            learning_infos[device.device] = GoveeLearnedInfo()
        # output what was lerned, and learn
        if (
            learning_infos[device.device].set_brightness_max
            != device.learned_set_brightness_max
        ):
            _LOGGER.debug(
                "learned device %s uses range 0-%s for setting brightness.",
                device.device,
                device.learned_set_brightness_max,
            )
            learning_infos[
                device.device
            ].set_brightness_max = device.learned_set_brightness_max
            changed = True
        if (
            learning_infos[device.device].get_brightness_max
            != device.learned_get_brightness_max
        ):
            _LOGGER.debug(
                "learned device %s uses range 0-%s for getting brightness state.",
                device.device,
                device.learned_get_brightness_max,
            )
            if device.learned_get_brightness_max == 100:
                _LOGGER.info(
                    "brightness range for %s is assumed. If the brightness slider doesn't match the actual brightness pull the brightness up to max once.",
                    device.device,
                )
            changed = True
            learning_infos[
                device.device
            ].get_brightness_max = device.learned_get_brightness_max

        if changed:
            await self._learning_storage._write_cached(learning_infos)

    async def set_color_temp(
        self, device: Union[str, GoveeDevice], color_temp: int
    ) -> Tuple[bool, str]:
        """Set color temperature to 2000-9000."""
        success = False
        err = None
        if self._api:
            return await self._api.set_color_temp(device, color_temp)
        return success, ERR_MESSAGE_NO_ACTIVE_IMPL

    async def set_color(
        self, device: Union[str, GoveeDevice], color: Tuple[int, int, int]
    ) -> Tuple[bool, str]:
        """Set color (r, g, b) where each value may be in range 0-255 """
        success = False
        err = None
        if self._api:
            return await self._api.set_color(device, color)
        return success, ERR_MESSAGE_NO_ACTIVE_IMPL

    async def get_states(self) -> List[GoveeDevice]:
        """Request states for all devices from API."""
        _LOGGER.debug("get_states")
        if self._api:
            for device in self.devices:
                _, err = await self._api._get_device_state(device)
                if err:
                    _LOGGER.warning(
                        "error getting state for device %s: %s",
                        device,
                        err,
                    )
                    device.error = err
                else:
                    device.error = None
        return self.devices
