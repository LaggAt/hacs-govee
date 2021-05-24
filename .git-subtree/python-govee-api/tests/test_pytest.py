from aiohttp import ClientSession
import asyncio
from datetime import datetime
import logging
import pytest
import queue
from time import time
from typing import Any, Dict
import unittest
from unittest.mock import MagicMock, AsyncMock

from govee_api_laggat import (
    Govee,
    GoveeAbstractLearningStorage,
    GoveeDevice,
    GoveeNoLearningStorage,
    GoveeLearnedInfo,
    GoveeSource,
)
from .mockdata import *


# learning state we usually want to persist somehow
class LearningStorage(GoveeAbstractLearningStorage):
    """
    Overriding this abstract storage allows to store learned informations.

    In this example we simply keep some data during one test.
    self.test_data is our source we will read form
    self.write_test_data is the target, we want to persist on

    In your implementation you might want to:
    - implement an 'async def read()' which restores the learned informations (if any) from disk or database
    - implement an 'async def write()' which persists the learned informations to disk or database
    """

    def __init__(self, test_data: Dict[str, GoveeLearnedInfo], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_data = test_data
        self.read_test_data = None
        self.read_call_count = 0
        self.write_test_data = None
        self.write_call_count = 0

    async def read(self) -> Dict[str, GoveeLearnedInfo]:
        self.read_call_count += 1
        self.read_test_data = self.test_data
        return self.test_data

    async def write(self, learned_info: Dict[str, GoveeLearnedInfo]):
        self.write_call_count += 1
        self.write_test_data = learned_info


mock_aiohttp_responses = queue.Queue()


def mock_aiohttp_request(self, *args, **kwargs):
    mock_response = mock_aiohttp_responses.get()
    mock_response.check_kwargs(kwargs)
    return mock_response


@pytest.fixture
def mock_aiohttp(monkeypatch):
    monkeypatch.setattr("aiohttp.ClientSession.get", mock_aiohttp_request)
    monkeypatch.setattr("aiohttp.ClientSession.put", mock_aiohttp_request)


def mock_never_lock_result(self, *args, **kwargs):
    return 0


@pytest.fixture
def mock_never_lock(monkeypatch):
    monkeypatch.setattr(
        "govee_api_laggat.api.GoveeApi._get_lock_seconds", mock_never_lock_result
    )


@pytest.fixture
def mock_logger(monkeypatch):
    mock = MagicMock()
    mock.mock_add_spec(logging.Logger)
    monkeypatch.setattr("govee_api_laggat.govee_api_laggat._LOGGER", mock)
    monkeypatch.setattr("govee_api_laggat.api._LOGGER", mock)
    return mock


@pytest.fixture
def mock_sleep(monkeypatch):
    mock = AsyncMock()
    # mock.mock_add_spec(asyncio.sleep)
    monkeypatch.setattr("asyncio.sleep", mock)
    return mock


@pytest.mark.asyncio
async def test_autobrightness_restore_saved_values(mock_aiohttp, mock_never_lock):
    # arrange
    learning_storage = LearningStorage(copy.deepcopy(LEARNED_S100_G254))

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"data": {"devices": [copy.deepcopy(JSON_DEVICE_H6163)]}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1
        assert learning_storage.read_test_data == {
            get_dummy_device_H6163().device: GoveeLearnedInfo(
                set_brightness_max=100,
                get_brightness_max=254,  # this we learned from brightness state
            )
        }
        assert learning_storage.read_call_count == 1
        assert learning_storage.write_call_count == 0


@pytest.mark.asyncio
async def test_autobrightness_set100_get254(mock_aiohttp, mock_never_lock):
    # arrange
    learning_storage = LearningStorage(copy.deepcopy(LEARNED_NOTHING))

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"data": {"devices": [copy.deepcopy(JSON_DEVICE_H6163)]}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1

        # set brightness to 142, and fail because we set > 100
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=400,
                text="Unsupported Cmd Value",
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "cmd": {"name": "brightness", "value": 142},
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # then set brightness to 55 (142 * 100 // 254), with success
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={"code": 200, "message": "Success", "data": {}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "cmd": {"name": "brightness", "value": 55},
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # call
        success, err = await govee.set_brightness(get_dummy_device_H6163().device, 142)
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert learning_storage.write_test_data == {
            get_dummy_device_H6163().device: GoveeLearnedInfo(
                set_brightness_max=100,  # this we lerned y setting brightness
                get_brightness_max=None,
            )
        }

        # get state
        # state returns a brightness of 142, we learn returning state is 0-254
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={
                    "data": {
                        "device": "40:83:FF:FF:FF:FF:FF:FF",
                        "model": "H6163",
                        "properties": [
                            {"online": True},
                            {"powerState": "on"},
                            {"brightness": 142},
                            {"color": {"r": 0, "b": 0, "g": 0}},
                        ],
                    },
                    "message": "Success",
                    "code": 200,
                },
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/state"
                and kwargs["params"]
                == {"device": "40:83:FF:FF:FF:FF:FF:FF", "model": "H6163"},
            )
        )
        # call
        states = await govee.get_states()
        # assert
        assert mock_aiohttp_responses.empty()
        assert states[0].source == GoveeSource.API
        assert states[0].brightness == 142
        assert learning_storage.write_test_data == {
            get_dummy_device_H6163().device: GoveeLearnedInfo(
                set_brightness_max=100,
                get_brightness_max=254,  # this we learned from brightness state
            )
        }


@pytest.mark.asyncio
async def test_autobrightness_set254_get100_get254(mock_aiohttp, mock_never_lock):
    # arrange
    learning_storage = LearningStorage(copy.deepcopy(LEARNED_NOTHING))

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"data": {"devices": [copy.deepcopy(JSON_DEVICE_H6163)]}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1

        # set brightness to 142, which is OK for a 0-254 device
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={"code": 200, "message": "Success", "data": {}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "cmd": {"name": "brightness", "value": 142},
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # call
        success, err = await govee.set_brightness(get_dummy_device_H6163().device, 142)
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert learning_storage.write_test_data == {
            get_dummy_device_H6163().device: GoveeLearnedInfo(
                set_brightness_max=254,  # this we lerned y setting brightness
                get_brightness_max=None,
            )
        }

        # get state
        # we get a state <= 100 (42 in this case), we assume get range is 0-100 and show a warning with instructions
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={
                    "data": {
                        "device": "40:83:FF:FF:FF:FF:FF:FF",
                        "model": "H6163",
                        "properties": [
                            {"online": True},
                            {"powerState": "on"},
                            {"brightness": 42},
                            {"color": {"r": 0, "b": 0, "g": 0}},
                        ],
                    },
                    "message": "Success",
                    "code": 200,
                },
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/state"
                and kwargs["params"]
                == {"device": "40:83:FF:FF:FF:FF:FF:FF", "model": "H6163"},
            )
        )
        # call
        states = await govee.get_states()
        # assert
        assert mock_aiohttp_responses.empty()
        assert states[0].source == GoveeSource.API
        assert states[0].brightness == 42 * 254 // 100
        assert learning_storage.write_test_data == {
            get_dummy_device_H6163().device: GoveeLearnedInfo(
                set_brightness_max=254,
                get_brightness_max=100,  # we assume this because we got no brightness state > 100
            )
        }

        # get state
        # we get a state > 100 (142 in this case), now we know the range is 0-254
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={
                    "data": {
                        "device": "40:83:FF:FF:FF:FF:FF:FF",
                        "model": "H6163",
                        "properties": [
                            {"online": True},
                            {"powerState": "on"},
                            {"brightness": 142},
                            {"color": {"r": 0, "b": 0, "g": 0}},
                        ],
                    },
                    "message": "Success",
                    "code": 200,
                },
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/state"
                and kwargs["params"]
                == {"device": "40:83:FF:FF:FF:FF:FF:FF", "model": "H6163"},
            )
        )
        # call
        states = await govee.get_states()
        # assert
        assert mock_aiohttp_responses.empty()
        assert states[0].source == GoveeSource.API
        assert states[0].brightness == 142
        assert learning_storage.write_test_data == {
            get_dummy_device_H6163().device: GoveeLearnedInfo(
                set_brightness_max=254,
                get_brightness_max=254,
            )
        }


@pytest.mark.asyncio
async def test_turnonbeforebrightness_brightness1_turnonthenbrightness(
    mock_aiohttp, mock_never_lock, mock_sleep
):
    """
    It's not possible to learn before_set_brightness_turn_on,
    but you can set this in the learning data.
    """
    # arrange
    learning_storage = LearningStorage(copy.deepcopy(LEARNED_TURN_BEFORE_BRIGHTNESS))

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"data": {"devices": [copy.deepcopy(JSON_DEVICE_H6163)]}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1

        # set brightness to 1 (minimum for turning on)
        # this will turn_on first
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={"code": 200, "message": "Success", "data": {}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "cmd": {"name": "turn", "value": "on"},
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # then it will set brightness
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={"code": 200, "message": "Success", "data": {}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "cmd": {"name": "brightness", "value": 1},
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # call
        success, err = await govee.set_brightness(get_dummy_device_H6163().device, 1)
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert govee.device(get_dummy_device_H6163().device).power_state == True
        assert govee.device(get_dummy_device_H6163().device).brightness == 3


@pytest.mark.asyncio
async def test_turnonbeforebrightness_brightness0_setbrihtness0(
    mock_aiohttp, mock_never_lock
):
    """
    It's not possible to learn before_set_brightness_turn_on,
    but you can set this in the learning data.
    Setting brightness to 0 will still only send brightness 0.
    """
    # arrange
    learning_storage = LearningStorage(copy.deepcopy(LEARNED_TURN_BEFORE_BRIGHTNESS))

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"data": {"devices": [copy.deepcopy(JSON_DEVICE_H6163)]}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1

        # set brightness to 1 (minimum for turning on)
        # then it will set brightness
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={"code": 200, "message": "Success", "data": {}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "cmd": {"name": "brightness", "value": 0},
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # call
        success, err = await govee.set_brightness(get_dummy_device_H6163().device, 0)
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert govee.device(get_dummy_device_H6163().device).power_state == False
        assert govee.device(get_dummy_device_H6163().device).brightness == 0


@pytest.mark.asyncio
async def test_offline_laststate(mock_aiohttp, mock_never_lock):
    """
    Device is on, and going offline. Computed state must stay online by default.
    Default is: config_offline_is_off=False
    """
    # arrange
    learning_storage = LearningStorage(copy.deepcopy(LEARNED_S100_G254))

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"data": {"devices": [copy.deepcopy(JSON_DEVICE_H6163)]}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1

        # turn on
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={"code": 200, "message": "Success", "data": {}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "cmd": {"name": "turn", "value": "on"},
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # call
        success, err = await govee.turn_on(get_dummy_device_H6163().device)
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert govee.device(get_dummy_device_H6163().device).power_state == True
        assert govee.device(get_dummy_device_H6163().device).online == True

        # get state - but device is offline
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json=copy.deepcopy(JSON_DEVICE_STATE_OFFLINE),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/state"
                and kwargs["params"]
                == {
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # call
        await govee.get_states()
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert govee.device(get_dummy_device_H6163().device).power_state == True
        assert govee.device(get_dummy_device_H6163().device).online == False


@pytest.mark.asyncio
async def test_offlineIsOffConfig_off(mock_aiohttp, mock_never_lock):
    """
    Device is on, and going offline. Computed state is configured to be OFF when offline.
    config_offline_is_off=True
    """
    # arrange
    learning_storage = LearningStorage(copy.deepcopy(CONFIGURE_OFFLINE_IS_OFF))

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"data": {"devices": [copy.deepcopy(JSON_DEVICE_H6163)]}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1

        # turn on
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={"code": 200, "message": "Success", "data": {}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "cmd": {"name": "turn", "value": "on"},
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # call
        success, err = await govee.turn_on(get_dummy_device_H6163().device)
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert govee.device(get_dummy_device_H6163().device).power_state == True
        assert govee.device(get_dummy_device_H6163().device).online == True

        # get state - but device is offline
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json=copy.deepcopy(JSON_DEVICE_STATE_OFFLINE),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/state"
                and kwargs["params"]
                == {
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # call
        await govee.get_states()
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert govee.device(get_dummy_device_H6163().device).power_state == False
        assert govee.device(get_dummy_device_H6163().device).online == False


@pytest.mark.asyncio
async def test_globalOfflineIsOffConfig_off(mock_aiohttp, mock_never_lock):
    """
    Device is on, and going offline. Computed state is configured to be OFF when offline.
    config_offline_is_off=True
    """
    # arrange
    learning_storage = LearningStorage(copy.deepcopy(LEARNED_S100_G254))

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"data": {"devices": [copy.deepcopy(JSON_DEVICE_H6163)]}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1

        ### set global config_offline_is_off
        govee.config_offline_is_off = True

        # turn on
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={"code": 200, "message": "Success", "data": {}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "cmd": {"name": "turn", "value": "on"},
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # call
        success, err = await govee.turn_on(get_dummy_device_H6163().device)
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert govee.device(get_dummy_device_H6163().device).power_state == True
        assert govee.device(get_dummy_device_H6163().device).online == True

        # get state - but device is offline
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json=copy.deepcopy(JSON_DEVICE_STATE_OFFLINE),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/state"
                and kwargs["params"]
                == {
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # call
        await govee.get_states()
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert govee.device(get_dummy_device_H6163().device).power_state == False
        assert govee.device(get_dummy_device_H6163().device).online == False


@pytest.mark.asyncio
async def test_set_disabled_state(mock_aiohttp, mock_never_lock):
    # arrange
    learning_storage = LearningStorage(copy.deepcopy(LEARNED_NOTHING))

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"data": {"devices": [copy.deepcopy(JSON_DEVICE_H6163)]}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1

        # configure to ignore brightness from history (this test doesn't retrieve API data)
        assert lamps[0].brightness == 0
        assert lamps[0].power_state == False
        govee.ignore_device_attributes("History:brightness;API:power_state")

        # set brightness to 142, which is OK for a 0-254 device
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={"code": 200, "message": "Success", "data": {}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "cmd": {"name": "brightness", "value": 142},
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # call
        success, err = await govee.set_brightness(get_dummy_device_H6163().device, 142)
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        # all state came from HISTORY, so brightness has not changed
        assert lamps[0].brightness == 0
        assert lamps[0].power_state == True

        # configure to ignore power_state from history (this test doesn't retrieve API data)
        lamps[0].brightness = 0
        lamps[0].power_state = False
        govee.ignore_device_attributes("API:brightness;HISTORY:power_state")
        # set brightness to 142, which is OK for a 0-254 device
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=200,
                json={"code": 200, "message": "Success", "data": {}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "cmd": {"name": "brightness", "value": 142},
                    "device": "40:83:FF:FF:FF:FF:FF:FF",
                    "model": "H6163",
                },
            )
        )
        # call
        success, err = await govee.set_brightness(get_dummy_device_H6163().device, 142)
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        # all state came from HISTORY, so brightness has not changed
        assert lamps[0].brightness == 142
        assert lamps[0].power_state == False


@pytest.mark.asyncio
async def test_getNoDevices_initOK(mock_aiohttp, mock_never_lock, mock_logger):
    """
    We can connect the API, but there is not device registered.
    Nothing is wront with that, user may add devices later.
    """
    # arrange
    learning_storage = GoveeNoLearningStorage()

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"code": 200, "message": "success", "data": {}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 0
        expected_log_info_args = (
            "API is connected, but there are no devices connected via Govee API. You may want to use Govee Home to pair your devices and connect them to WIFI.",
        )
        assert expected_log_info_args in [
            call.args for call in mock_logger.info.mock_calls
        ]

        cached_devices = govee.devices
        assert cached_devices == []


@pytest.mark.asyncio
async def test_getDevicesTwice_keepOrAddDevices(mock_aiohttp, mock_never_lock):
    """
    when get_devices() is called twice, keep devices already known without altering.
    devices once in list will never be removed (until restart).
    """
    # arrange
    learning_storage = GoveeNoLearningStorage()

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # empty device list
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"code": 200, "message": "success", "data": {}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 0

        # one device
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"data": {"devices": [copy.deepcopy(JSON_DEVICE_H6163)]}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1
        lamp0 = lamps[0]

        # another device
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={"data": {"devices": [copy.deepcopy(JSON_DEVICE_H6104)]}},
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 2
        assert lamp0 is lamps[0]
        lamp1 = lamps[1]

        # both devices
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json={
                    "data": {
                        "devices": [
                            copy.deepcopy(JSON_DEVICE_H6104),
                            copy.deepcopy(JSON_DEVICE_H6163),
                        ]
                    }
                },
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 2
        assert lamp0 is lamps[0]
        assert lamp1 is lamps[1]


@pytest.mark.asyncio
async def test_rate_limiter(mock_aiohttp, mock_sleep):
    sleep_until = datetime.timestamp(datetime.now()) + 1

    async with Govee(API_KEY) as govee:
        # initial values
        assert govee.rate_limit_on == 5
        assert govee.rate_limit_total == 100
        assert govee.rate_limit_reset == 0
        assert govee.rate_limit_remaining == 100

        # first run uses defaults, so request returns immediatly
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_DEVICES),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
                headers={
                    RATELIMIT_TOTAL: 100,
                    RATELIMIT_REMAINING: 5,  # next time we need to limit
                    RATELIMIT_RESET: f"{sleep_until}",
                },
            )
        )
        _, err1 = await govee.get_devices()
        assert mock_aiohttp_responses.empty()
        assert mock_sleep.call_count == 0
        assert govee.rate_limit_remaining == 5
        assert govee.rate_limit_reset == sleep_until

        # second run, rate limit sleeps until the second is over
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_DEVICES),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        _, err2 = await govee.get_devices()

        # assert
        assert mock_aiohttp_responses.empty()
        assert mock_sleep.call_count == 1
        assert not err1
        assert not err2


@pytest.mark.asyncio
async def test_rate_limit_exceeded(mock_aiohttp):
    async with Govee(API_KEY) as govee:
        sleep_until = datetime.timestamp(datetime.now()) + 1
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=429,  # too many requests
                text="Rate limit exceeded, retry in 1 seconds.",
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
                headers={
                    RATELIMIT_TOTAL: 100,
                    RATELIMIT_REMAINING: 5,  # next time we need to limit
                    RATELIMIT_RESET: f"{sleep_until}",
                },
            )
        )
        assert govee.rate_limit_on == 5
        assert govee.rate_limit_total == 100
        assert govee.rate_limit_reset == 0
        assert govee.rate_limit_remaining == 100
        # first run uses defaults, so ping returns immediatly
        result1, err1 = await govee.get_devices()

        # assert
        assert not result1
        assert err1 == "API: API-Error 429: Rate limit exceeded, retry in 1 seconds."
        assert mock_aiohttp_responses.empty()


@pytest.mark.asyncio
async def test_rate_limiter_custom_threshold(mock_aiohttp):
    async with Govee(API_KEY) as govee:
        sleep_until = datetime.timestamp(datetime.now()) + 1
        govee.rate_limit_on = 4
        assert govee.rate_limit_on == 4  # set did work
        # first run uses defaults, so ping returns immediatly
        start = time()
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_DEVICES),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
                headers={
                    RATELIMIT_TOTAL: 100,
                    RATELIMIT_REMAINING: 5,  # we lower the limit to 4 to not lock
                    RATELIMIT_RESET: f"{sleep_until}",
                },
            )
        )
        _, err1 = await govee.get_devices()
        delay1 = start - time()
        # second run, doesn't rate limit either
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_DEVICES),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
                headers={
                    RATELIMIT_TOTAL: 100,
                    RATELIMIT_REMAINING: 5,  # we lower the limit to 4 to not lock
                    RATELIMIT_RESET: f"{sleep_until}",
                },
            )
        )
        _, err2 = await govee.get_devices()
        delay2 = start - time()

        # assert
        assert delay1 < 0.10  # this should return immediatly
        assert delay2 < 0.10  # this should return immediatly
        assert not err1
        assert not err2
        assert mock_aiohttp_responses.empty()


@pytest.mark.asyncio
async def test_get_devices(mock_aiohttp, mock_never_lock):
    async with Govee(API_KEY) as govee:
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_DEVICES),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices"
                and kwargs["headers"] == {"Govee-API-Key": "SUPER_SECRET_KEY"},
            )
        )
        result, err = await govee.get_devices()
        assert err == None
        assert mock_aiohttp_responses.empty()
        assert len(result) == 2
        assert isinstance(result[0], GoveeDevice)
        assert result[0].model == "H6163"
        assert result[1].model == "H6104"


@pytest.mark.asyncio
async def test_get_devices_empty(mock_aiohttp, mock_never_lock):
    async with Govee(API_KEY) as govee:
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_DEVICES_EMPTY),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices"
                and kwargs["headers"] == {"Govee-API-Key": "SUPER_SECRET_KEY"},
            )
        )
        result, err = await govee.get_devices()
        assert result == []
        assert err == None
        assert mock_aiohttp_responses.empty()
        assert len(result) == 0


@pytest.mark.asyncio
async def test_get_devices_cache(mock_aiohttp, mock_never_lock):
    async with Govee(API_KEY) as govee:
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_DEVICES),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices",
            )
        )
        result, err = await govee.get_devices()
        assert not err
        cache = govee.devices
        # assert
        assert mock_aiohttp_responses.empty()
        assert len(result) == 2
        assert result == cache


@pytest.mark.asyncio
async def test_get_devices_invalid_key(mock_aiohttp, mock_never_lock):
    invalid_key = "INVALIDAPI_KEY"
    async with Govee(invalid_key) as govee:
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=401,
                text="invalid key",
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices"
                and kwargs["headers"] == {"Govee-API-Key": invalid_key},
            )
        )
        result, err = await govee.get_devices()
        assert err
        assert "401" in err
        assert "invalid key" in err
        assert mock_aiohttp_responses.empty()
        assert len(result) == 0


@pytest.mark.asyncio
async def test_turn_on(mock_aiohttp, mock_never_lock):
    async with Govee(API_KEY) as govee:
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_OK_RESPONSE),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "device": get_dummy_device_H6163().device,
                    "model": get_dummy_device_H6163().model,
                    "cmd": {"name": "turn", "value": "on"},
                },
            )
        )
        # inject a device for testing
        govee._devices = {get_dummy_device_H6163().device: get_dummy_device_H6163()}
        success, err = await govee.turn_on(get_dummy_device_H6163())
        assert mock_aiohttp_responses.empty()
        assert err == None
        assert success == True


@pytest.mark.asyncio
async def test_turn_on_auth_failure(mock_aiohttp, mock_never_lock):
    async with Govee(API_KEY) as govee:
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                status=401,
                text="Test auth failed",
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "device": get_dummy_device_H6163().device,
                    "model": get_dummy_device_H6163().model,
                    "cmd": {"name": "turn", "value": "on"},
                }
                and kwargs["headers"] == {"Govee-API-Key": "SUPER_SECRET_KEY"},
            )
        )
        # inject a device for testing
        govee._devices = {get_dummy_device_H6163().device: get_dummy_device_H6163()}
        success, err = await govee.turn_on(get_dummy_device_H6163())
        assert mock_aiohttp_responses.empty()
        assert success == False
        assert "401" in err  # http status
        assert "Test auth failed" in err  # http message
        assert "turn" in err  # command used
        assert get_dummy_device_H6163().device in err  # device used


@pytest.mark.asyncio
async def test_turn_off_by_address(mock_aiohttp, mock_never_lock):
    async with Govee(API_KEY) as govee:
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_OK_RESPONSE),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "device": get_dummy_device_H6163().device,
                    "model": get_dummy_device_H6163().model,
                    "cmd": {"name": "turn", "value": "off"},
                }
                and kwargs["headers"] == {"Govee-API-Key": "SUPER_SECRET_KEY"},
            )
        )
        # inject a device for testing
        govee._devices = {get_dummy_device_H6163().device: get_dummy_device_H6163()}
        # use device address here
        success, err = await govee.turn_off(get_dummy_device_H6163().device)
        # assert
        assert err == None
        assert mock_aiohttp_responses.empty()
        assert success == True


@pytest.mark.asyncio
async def test_get_states(mock_aiohttp, mock_never_lock):
    changed_device = copy.deepcopy(get_dummy_device_H6163())
    unchangeable_device = copy.deepcopy(get_dummy_device_H6104())
    async with Govee(API_KEY) as govee:
        assert mock_aiohttp_responses.empty()
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_DEVICE_STATE),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/state"
                and kwargs["params"]
                == {
                    "device": get_dummy_device_H6163().device,
                    "model": get_dummy_device_H6163().model,
                }
                and kwargs["headers"] == {"Govee-API-Key": "SUPER_SECRET_KEY"},
            )
        )
        # inject two devices for testing, one supports state
        govee._devices = copy.deepcopy(DUMMY_DEVICES)
        states = await govee.get_states()

        assert mock_aiohttp_responses.empty()
        assert len(states) == 2
        # to compare the
        assert states[0].timestamp > get_dummy_device_H6163().timestamp
        assert states[0].source == GoveeSource.API
        # set timestamp and source to equal before comparing
        changed_device.timestamp = states[0].timestamp
        changed_device.source = GoveeSource.API
        assert states[0] == changed_device  # changed
        # timestamp also updated here, but still history state
        assert states[1].timestamp > get_dummy_device_H6104().timestamp
        unchangeable_device.timestamp = states[1].timestamp
        states[1].source = GoveeSource.HISTORY
        assert states[1] == unchangeable_device  # unchanged / no state supported


@pytest.mark.asyncio
async def test_set_brightness_to_high(mock_aiohttp, mock_never_lock):
    brightness = 255  # not allowed value
    async with Govee(API_KEY) as govee:
        # inject a device for testing
        govee._devices = {get_dummy_device_H6163().device: get_dummy_device_H6163()}
        success, err = await govee.set_brightness(get_dummy_device_H6163(), brightness)

        assert success == False
        assert mock_aiohttp_responses.empty()
        assert "255" in err
        assert "254" in err
        assert "brightness" in err


@pytest.mark.asyncio
async def test_set_brightness_to_low(mock_aiohttp, mock_never_lock):
    brightness = -1  # not allowed value
    async with Govee(API_KEY) as govee:
        # inject a device for testing
        govee._devices = {get_dummy_device_H6163().device: get_dummy_device_H6163()}
        success, err = await govee.set_brightness(get_dummy_device_H6163(), brightness)

        assert success == False
        assert mock_aiohttp_responses.empty()
        assert "-1" in err
        assert "254" in err
        assert "brightness" in err


@pytest.mark.asyncio
async def test_set_brightness(mock_aiohttp, mock_never_lock):
    async with Govee(API_KEY) as govee:
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_OK_RESPONSE),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "device": get_dummy_device_H6163().device,
                    "model": get_dummy_device_H6163().model,
                    "cmd": {
                        "name": "brightness",
                        # we need to control brightness betweenn 0 .. 100
                        "value": 42 * 100 // 254,
                    },
                }
                and kwargs["headers"] == {"Govee-API-Key": "SUPER_SECRET_KEY"},
            )
        )

        # inject a device for testing
        govee._devices = {get_dummy_device_H6163().device: get_dummy_device_H6163()}
        success, err = await govee.set_brightness(get_dummy_device_H6163().device, 42)

        # assert
        assert err == None
        assert mock_aiohttp_responses.empty()
        assert govee.devices[0].power_state == True
        assert success == True


@pytest.mark.asyncio
async def test_set_color_temp(mock_aiohttp, mock_never_lock):
    async with Govee(API_KEY) as govee:
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_OK_RESPONSE),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "device": get_dummy_device_H6163().device,
                    "model": get_dummy_device_H6163().model,
                    "cmd": {"name": "colorTem", "value": 6000},
                }
                and kwargs["headers"] == {"Govee-API-Key": "SUPER_SECRET_KEY"},
            )
        )

        # inject a device for testing
        govee._devices = {get_dummy_device_H6163().device: get_dummy_device_H6163()}
        success, err = await govee.set_color_temp(get_dummy_device_H6163().device, 6000)
        # assert
        assert err == None
        assert mock_aiohttp_responses.empty()
        assert success == True


@pytest.mark.asyncio
async def test_set_color(mock_aiohttp, mock_never_lock):
    async with Govee(API_KEY) as govee:
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_OK_RESPONSE),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "device": get_dummy_device_H6163().device,
                    "model": get_dummy_device_H6163().model,
                    "cmd": {"name": "color", "value": {"r": 42, "g": 43, "b": 44}},
                }
                and kwargs["headers"] == {"Govee-API-Key": "SUPER_SECRET_KEY"},
            )
        )
        # act
        # inject a device for testing
        govee._devices = {get_dummy_device_H6163().device: get_dummy_device_H6163()}
        success, err = await govee.set_color(
            get_dummy_device_H6163().device, (42, 43, 44)
        )

        # assert
        assert err == None
        assert mock_aiohttp_responses.empty()
        assert success == True


@pytest.mark.asyncio
async def test_turn_on_and_get_cache_state(mock_aiohttp):
    """Test that the state immediatly after switching is returned from cache.
    Just after switching the API has the wrong state.
    mock_never_lock may not be used here, because a lock is
    """
    async with Govee(API_KEY) as govee:
        # arrange
        mock_aiohttp_responses.put(
            MockAiohttpResponse(
                json=copy.deepcopy(JSON_OK_RESPONSE),
                check_kwargs=lambda kwargs: kwargs["url"]
                == "https://developer-api.govee.com/v1/devices/control"
                and kwargs["json"]
                == {
                    "device": get_dummy_device_H6163().device,
                    "model": get_dummy_device_H6163().model,
                    "cmd": {"name": "turn", "value": "on"},
                }
                and kwargs["headers"] == {"Govee-API-Key": "SUPER_SECRET_KEY"},
            )
        )
        no_dequeue_message = "get_states() must not request this"
        mock_aiohttp_responses.put(MockAiohttpResponse(text=no_dequeue_message))
        # act
        # inject a device for testing
        govee._devices = {get_dummy_device_H6163().device: get_dummy_device_H6163()}
        test_device = govee.devices[0]
        # turn on
        await govee.turn_on(test_device)
        assert test_device.source == GoveeSource.HISTORY
        # getting state to early (before 2s after switching)
        states = await govee.get_states()
        # assert
        assert states[0].source == GoveeSource.HISTORY
        # only turn_on result is mocked, no state must be requestet because it's too early after controlling
        assert mock_aiohttp_responses.qsize()
        # empty the queue
        mock_aiohttp_responses.get()
