import asyncio
import unittest
import pytest
import queue

from aiohttp import ClientSession
from datetime import datetime
from time import time
from typing import Dict

from govee_api_laggat import Govee, GoveeDevice, GoveeAbstractLearningStorage, GoveeLearnedInfo
from .mockdata import *

# learning state we usually want to persist somehow
class LearningStorage(GoveeAbstractLearningStorage):
    """
    Overriding this abstract storage allows to store learned informations.
    
    In this example we simply keep some data during one test.
    self.test_data is our source we will read form
    self.persisted_test_data is the target, we want to persist on

    In your implementation you might want to:
    - implement an 'async def read()' which restores the learned informations (if any) from disk or database
    - implement an 'async def write()' which persists the learned informations to disk or database
    """

    def __init__(self, test_data: Dict[str, GoveeLearnedInfo], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_data = test_data
    
    async def read(self) -> Dict[str, GoveeLearnedInfo]:
        return self.test_data
    
    async def write(self, learned_info: Dict[str, GoveeLearnedInfo]):
        self.persisted_test_data = learned_info


# API rate limit header keys
_RATELIMIT_TOTAL = 'Rate-Limit-Total' # The maximum number of requests you're permitted to make per minute.
_RATELIMIT_REMAINING = 'Rate-Limit-Remaining' # The number of requests remaining in the current rate limit window.
_RATELIMIT_RESET = 'Rate-Limit-Reset' # The time at which the current rate limit window resets in UTC epoch seconds.

class MockAiohttpResponse:
    def __init__(self, *, status = 200, json = None, text = None,
        check_kwargs = lambda kwargs : True
    ):
        self._status = status
        self._json = json
        self._text = text
        self._check_kwargs = check_kwargs
        
    def check_kwargs(self, kwargs):
        ok = self._check_kwargs(kwargs)
        if not ok:
            raise Exception(f"kwargs '{kwargs}' not ok, checked by lambda: '{self._check_kwargs}'")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *error_info):
        return self

    @property
    def headers(self):
        h = {
            _RATELIMIT_TOTAL: 100,
            _RATELIMIT_REMAINING: 100,
            _RATELIMIT_RESET: 0
        }
        return h

    @property
    def status(self):
        return self._status

    async def json(self):
        return self._json

    async def text(self):
        return self._text

mock_aiohttp_responses = queue.Queue()
def mock_aiohttp_request(self, *args, **kwargs):
        mock_response = mock_aiohttp_responses.get()
        mock_response.check_kwargs(kwargs)
        return mock_response

@pytest.fixture
def mock_aiohttp(monkeypatch):
    monkeypatch.setattr('aiohttp.ClientSession.get', mock_aiohttp_request)
    monkeypatch.setattr('aiohttp.ClientSession.put', mock_aiohttp_request)

@pytest.mark.asyncio
async def test_no_initial_learning_data(mock_aiohttp):
    # arrange
    learning_storage = LearningStorage(LEARNED_NOTHING)

    # act
    async with Govee(API_KEY, learning_storage=learning_storage) as govee:
        # request devices list
        mock_aiohttp_responses.put(MockAiohttpResponse(
            json=JSON_DEVICES,
            check_kwargs=lambda kwargs: kwargs['url'] == 'https://developer-api.govee.com/v1/devices'
        ))
        lamps, err = await govee.get_devices()
        assert mock_aiohttp_responses.empty()
        assert not err
        assert len(lamps) == 2

        # set brightness to 142, and fail
        mock_aiohttp_responses.put(MockAiohttpResponse(
            status = 400,
            text="Unsupported Cmd Value",
            check_kwargs=lambda kwargs: kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control' \
                and kwargs['json'] == {'cmd': {'name': 'brightness', 'value': 142}, 'device': '40:83:FF:FF:FF:FF:FF:FF', 'model': 'H6163'}
        ))
        # set brightness to 55 (142 * 100 // 254), with success
        mock_aiohttp_responses.put(MockAiohttpResponse(
            status = 200,
            json = {'code': 200, 'message': 'Success', 'data': {}},
            check_kwargs=lambda kwargs: kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control' \
                and kwargs['json'] == {'cmd': {'name': 'brightness', 'value': 55}, 'device': '40:83:FF:FF:FF:FF:FF:FF', 'model': 'H6163'}
        ))
        success, err = await govee.set_brightness(DUMMY_DEVICE_H6163.device, 142)
        assert mock_aiohttp_responses.empty()
        assert success
        assert not err
        assert learning_storage.persisted_test_data == {
            DUMMY_DEVICE_H6163.device: GoveeLearnedInfo(
                set_brightness_max = 100,
                get_brightness_max = 100,
            )
        }


