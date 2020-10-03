import asyncio
import queue
import unittest
from datetime import datetime
from time import time
from typing import Dict

import pytest
from aiohttp import ClientSession
from govee_api_laggat import (Govee, GoveeAbstractLearningStorage, GoveeDevice,
                              GoveeLearnedInfo)

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
    monkeypatch.setattr('aiohttp.ClientSession.get', mock_aiohttp_request)
    monkeypatch.setattr('aiohttp.ClientSession.put', mock_aiohttp_request)

def mock_never_lock_result(self, *args, **kwargs):
    return 0

@pytest.fixture
def mock_never_lock(monkeypatch):
    monkeypatch.setattr('govee_api_laggat.Govee._get_lock_seconds', mock_never_lock_result)

@pytest.mark.asyncio
async def test_autobrightness_restore_saved_values(mock_aiohttp, mock_never_lock):
    # arrange
    learning_storage = LearningStorage(copy.deepcopy(LEARNED_S100_G254))

    #act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(MockAiohttpResponse(
            json={'data': {'devices': [copy.deepcopy(JSON_DEVICE_H6163)]}},
            check_kwargs=lambda kwargs: kwargs['url'] == 'https://developer-api.govee.com/v1/devices'
        ))
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1
        assert learning_storage.read_test_data == {
            DUMMY_DEVICE_H6163.device: GoveeLearnedInfo(
                set_brightness_max = 100,
                get_brightness_max = 254,  # this we learned from brightness state
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
        mock_aiohttp_responses.put(MockAiohttpResponse(
            json={'data': {'devices': [copy.deepcopy(JSON_DEVICE_H6163)]}},
            check_kwargs=lambda kwargs: kwargs['url'] == 'https://developer-api.govee.com/v1/devices'
        ))
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1

        # set brightness to 142, and fail because we set > 100
        mock_aiohttp_responses.put(MockAiohttpResponse(
            status = 400,
            text="Unsupported Cmd Value",
            check_kwargs=lambda kwargs: kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control' \
                and kwargs['json'] == {'cmd': {'name': 'brightness', 'value': 142}, 'device': '40:83:FF:FF:FF:FF:FF:FF', 'model': 'H6163'}
        ))
        # then set brightness to 55 (142 * 100 // 254), with success
        mock_aiohttp_responses.put(MockAiohttpResponse(
            status = 200,
            json = {'code': 200, 'message': 'Success', 'data': {}},
            check_kwargs=lambda kwargs: kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control' \
                and kwargs['json'] == {'cmd': {'name': 'brightness', 'value': 55}, 'device': '40:83:FF:FF:FF:FF:FF:FF', 'model': 'H6163'}
        ))
        # call
        success, err = await govee.set_brightness(DUMMY_DEVICE_H6163.device, 142)
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert learning_storage.write_test_data == {
            DUMMY_DEVICE_H6163.device: GoveeLearnedInfo(
                set_brightness_max = 100,  # this we lerned y setting brightness
                get_brightness_max = None,
            )
        }

        # get state
        # state returns a brightness of 142, we learn returning state is 0-254
        mock_aiohttp_responses.put(MockAiohttpResponse(
            status = 200,
            json = {'data':{'device':'40:83:FF:FF:FF:FF:FF:FF','model':'H6163','properties':[{'online':True},{'powerState':'on'},{'brightness':142},{'color':{'r':0,'b':0,'g':0}}]},'message':'Success','code':200},
            check_kwargs=lambda kwargs: kwargs['url'] == 'https://developer-api.govee.com/v1/devices/state' \
                and kwargs['params'] == {'device': '40:83:FF:FF:FF:FF:FF:FF', 'model': 'H6163' }
        ))
        # call
        states = await govee.get_states()
        # assert
        assert mock_aiohttp_responses.empty()
        assert states[0].source == 'api'
        assert states[0].brightness == 142
        assert learning_storage.write_test_data == {
            DUMMY_DEVICE_H6163.device: GoveeLearnedInfo(
                set_brightness_max = 100,
                get_brightness_max = 254,  # this we learned from brightness state
            )
        }

@pytest.mark.asyncio
async def test_autobrightness_set254_get100_get254(mock_aiohttp, mock_never_lock):
    # arrange
    learning_storage = LearningStorage(copy.deepcopy(LEARNED_NOTHING))

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(MockAiohttpResponse(
            json={'data': {'devices': [copy.deepcopy(JSON_DEVICE_H6163)]}},
            check_kwargs=lambda kwargs: kwargs['url'] == 'https://developer-api.govee.com/v1/devices'
        ))
        # call
        lamps, err = await govee.get_devices()
        # assert
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 1

        # set brightness to 142, which is OK for a 0-254 device
        mock_aiohttp_responses.put(MockAiohttpResponse(
            status = 200,
            json = {'code': 200, 'message': 'Success', 'data': {}},
            check_kwargs=lambda kwargs: kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control' \
                and kwargs['json'] == {'cmd': {'name': 'brightness', 'value': 142}, 'device': '40:83:FF:FF:FF:FF:FF:FF', 'model': 'H6163'}
        ))
        # call
        success, err = await govee.set_brightness(DUMMY_DEVICE_H6163.device, 142)
        # assert
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert learning_storage.write_test_data == {
            DUMMY_DEVICE_H6163.device: GoveeLearnedInfo(
                set_brightness_max = 254,  # this we lerned y setting brightness
                get_brightness_max = None,
            )
        }

        # get state
        # we get a state <= 100 (42 in this case), we assume get range is 0-100 and show a warning with instructions
        mock_aiohttp_responses.put(MockAiohttpResponse(
            status = 200,
            json = {'data':{'device':'40:83:FF:FF:FF:FF:FF:FF','model':'H6163','properties':[{'online':True},{'powerState':'on'},{'brightness':42},{'color':{'r':0,'b':0,'g':0}}]},'message':'Success','code':200},
            check_kwargs=lambda kwargs: kwargs['url'] == 'https://developer-api.govee.com/v1/devices/state' \
                and kwargs['params'] == {'device': '40:83:FF:FF:FF:FF:FF:FF', 'model': 'H6163' }
        ))
        # call
        states = await govee.get_states()
        # assert
        assert mock_aiohttp_responses.empty()
        assert states[0].source == 'api'
        assert states[0].brightness == 42 * 254 // 100
        assert learning_storage.write_test_data == {
            DUMMY_DEVICE_H6163.device: GoveeLearnedInfo(
                set_brightness_max = 254,
                get_brightness_max = 100,  # we assume this because we got no brightness state > 100
            )
        }

        # get state
        # we get a state > 100 (142 in this case), now we know the range is 0-254
        mock_aiohttp_responses.put(MockAiohttpResponse(
            status = 200,
            json = {'data':{'device':'40:83:FF:FF:FF:FF:FF:FF','model':'H6163','properties':[{'online':True},{'powerState':'on'},{'brightness':142},{'color':{'r':0,'b':0,'g':0}}]},'message':'Success','code':200},
            check_kwargs=lambda kwargs: kwargs['url'] == 'https://developer-api.govee.com/v1/devices/state' \
                and kwargs['params'] == {'device': '40:83:FF:FF:FF:FF:FF:FF', 'model': 'H6163' }
        ))
        # call
        states = await govee.get_states()
        # assert
        assert mock_aiohttp_responses.empty()
        assert states[0].source == 'api'
        assert states[0].brightness == 142
        assert learning_storage.write_test_data == {
            DUMMY_DEVICE_H6163.device: GoveeLearnedInfo(
                set_brightness_max = 254,
                get_brightness_max = 254,
            )
        }
