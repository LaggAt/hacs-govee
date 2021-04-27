import asyncio
from datetime import datetime
from time import time

from aiohttp import ClientSession, ClientError
from asynctest import CoroutineMock, MagicMock, TestCase, patch

from govee_api_laggat import (
    Govee,
    GoveeAbstractLearningStorage,
    GoveeDevice,
    GoveeLearnedInfo,
    GoveeSource
)

from .mockdata import *


class GoveeTests(TestCase):
    @patch("aiohttp.ClientSession.get")
    def test_ping(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.text = CoroutineMock(
            return_value="Pong"
        )
        # act

        async def ping():
            async with Govee(API_KEY) as govee:
                return await govee.ping()

        result, err = loop.run_until_complete(ping())
        # assert
        assert not err
        assert result
        assert mock_get.call_count == 1
        assert (
            mock_get.call_args.kwargs["url"] == "https://developer-api.govee.com/ping"
        )

    @patch("aiohttp.ClientSession.get")
    @patch("asyncio.sleep")
    def test_rate_limiter(self, mock_sleep, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICES
        )
        sleep_until = datetime.timestamp(datetime.now()) + 1
        mock_get.return_value.__aenter__.return_value.headers = {
            RATELIMIT_TOTAL: "100",
            RATELIMIT_REMAINING: "5",
            RATELIMIT_RESET: f"{sleep_until}",
        }
        mock_sleep.return_value.__aenter__.return_value.text = CoroutineMock()
        # act
        async def get_devices():
            async with Govee(API_KEY) as govee:
                assert govee.rate_limit_on == 5
                assert govee.rate_limit_total == 100
                assert govee.rate_limit_reset == 0
                assert govee.rate_limit_remaining == 100
                # first run uses defaults, so ping returns immediatly
                _, err1 = await govee.get_devices()
                assert mock_sleep.call_count == 0
                assert govee.rate_limit_remaining == 5
                assert govee.rate_limit_reset == sleep_until
                # second run, rate limit sleeps until the second is over
                _, err2 = await govee.get_devices()
                assert mock_sleep.call_count == 1
                return err1, err2

        err1, err2 = loop.run_until_complete(get_devices())
        # assert
        assert not err1
        assert not err2
        assert mock_get.call_count == 2

    @patch("aiohttp.ClientSession.get")
    def test_rate_limit_exceeded(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 429  # too many requests
        mock_get.return_value.__aenter__.return_value.text = CoroutineMock(
            return_value="Rate limit exceeded, retry in 1 seconds."
        )
        sleep_until = datetime.timestamp(datetime.now()) + 1
        mock_get.return_value.__aenter__.return_value.headers = {
            RATELIMIT_TOTAL: "100",
            RATELIMIT_REMAINING: "5",
            RATELIMIT_RESET: f"{sleep_until}",
        }
        # act
        async def get_devices():
            async with Govee(API_KEY) as govee:
                assert govee.rate_limit_on == 5
                assert govee.rate_limit_total == 100
                assert govee.rate_limit_reset == 0
                assert govee.rate_limit_remaining == 100
                # first run uses defaults, so ping returns immediatly
                return await govee.get_devices()

        result1, err1 = loop.run_until_complete(get_devices())
        # assert
        assert not result1
        assert err1 == "API-Error 429: Rate limit exceeded, retry in 1 seconds."
        assert mock_get.call_count == 1

    @patch("aiohttp.ClientSession.get")
    def test_rate_limiter_custom_threshold(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICES
        )
        sleep_until = datetime.timestamp(datetime.now()) + 1
        mock_get.return_value.__aenter__.return_value.headers = {
            RATELIMIT_TOTAL: "100",
            RATELIMIT_REMAINING: "5",  # by default below 5 it is sleeping
            RATELIMIT_RESET: f"{sleep_until}",
        }
        # act
        async def get_devices():
            async with Govee(API_KEY) as govee:
                govee.rate_limit_on = 4
                assert govee.rate_limit_on == 4  # set did work
                # first run uses defaults, so ping returns immediatly
                start = time()
                _, err1 = await govee.get_devices()
                delay1 = start - time()
                # second run, doesn't rate limit either
                _, err2 = await govee.get_devices()
                delay2 = start - time()
                return delay1, err1, delay2, err2

        delay1, err1, delay2, err2 = loop.run_until_complete(get_devices())
        # assert
        assert delay1 < 0.10  # this should return immediatly
        assert delay2 < 0.10  # this should return immediatly
        assert not err1
        assert not err2
        assert mock_get.call_count == 2

    @patch("aiohttp.ClientSession.get")
    def test_get_devices(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICES
        )
        # act
        async def getDevices():
            async with Govee(API_KEY) as govee:
                return await govee.get_devices()

        result, err = loop.run_until_complete(getDevices())
        # assert
        assert err == None
        assert mock_get.call_count == 1
        assert (
            mock_get.call_args.kwargs["url"]
            == "https://developer-api.govee.com/v1/devices"
        )
        assert mock_get.call_args.kwargs["headers"] == {
            "Govee-API-Key": "SUPER_SECRET_KEY"
        }
        assert len(result) == 2
        assert isinstance(result[0], GoveeDevice)
        assert result[0].model == "H6163"
        assert result[1].model == "H6104"

    @patch("aiohttp.ClientSession.get")
    def test_get_devices_empty(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICES_EMPTY
        )
        # act
        async def getDevices():
            async with Govee(API_KEY) as govee:
                return await govee.get_devices()

        result, err = loop.run_until_complete(getDevices())
        # assert
        assert result == []
        assert err == None
        assert mock_get.call_count == 1
        assert (
            mock_get.call_args.kwargs["url"]
            == "https://developer-api.govee.com/v1/devices"
        )
        assert mock_get.call_args.kwargs["headers"] == {
            "Govee-API-Key": "SUPER_SECRET_KEY"
        }
        assert len(result) == 0

    @patch("aiohttp.ClientSession.get")
    def test_get_devices_cache(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICES
        )
        # act

        async def getDevices():
            async with Govee(API_KEY) as govee:
                result, err = await govee.get_devices()
                assert not err
                cache = govee.devices
                return result, cache

        result, cache = loop.run_until_complete(getDevices())
        # assert
        assert mock_get.call_count == 1
        assert len(result) == 2
        assert result == cache

    @patch("aiohttp.ClientSession.get")
    def test_get_devices_invalid_key(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 401
        mock_get.return_value.__aenter__.return_value.text = CoroutineMock(
            return_value={"INVALIDAPI_KEY"}
        )
        # act

        async def getDevices():
            async with Govee("INVALIDAPI_KEY") as govee:
                return await govee.get_devices()

        result, err = loop.run_until_complete(getDevices())
        # assert
        assert err
        assert "401" in err
        assert "INVALIDAPI_KEY" in err
        assert mock_get.call_count == 1
        assert (
            mock_get.call_args.kwargs["url"]
            == "https://developer-api.govee.com/v1/devices"
        )
        assert mock_get.call_args.kwargs["headers"] == {
            "Govee-API-Key": "INVALIDAPI_KEY"
        }
        assert len(result) == 0

    @patch("aiohttp.ClientSession.put")
    def test_turn_on(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_OK_RESPONSE
        )
        # act

        async def turn_on():
            async with Govee(API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.turn_on(DUMMY_DEVICE_H6163)

        success, err = loop.run_until_complete(turn_on())
        # assert
        assert err == None
        assert mock_put.call_count == 1
        assert (
            mock_put.call_args.kwargs["url"]
            == "https://developer-api.govee.com/v1/devices/control"
        )
        assert mock_put.call_args.kwargs["headers"] == {
            "Govee-API-Key": "SUPER_SECRET_KEY"
        }
        assert mock_put.call_args.kwargs["json"] == {
            "device": DUMMY_DEVICE_H6163.device,
            "model": DUMMY_DEVICE_H6163.model,
            "cmd": {"name": "turn", "value": "on"},
        }
        assert success == True

    @patch("aiohttp.ClientSession.put")
    def test_turn_on_auth_failure(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 401
        mock_put.return_value.__aenter__.return_value.text = CoroutineMock(
            return_value="Test auth failed"
        )
        # act

        async def turn_on():
            async with Govee(API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.turn_on(DUMMY_DEVICE_H6163)

        success, err = loop.run_until_complete(turn_on())
        # assert
        assert mock_put.call_count == 1
        assert (
            mock_put.call_args.kwargs["url"]
            == "https://developer-api.govee.com/v1/devices/control"
        )
        assert mock_put.call_args.kwargs["headers"] == {
            "Govee-API-Key": "SUPER_SECRET_KEY"
        }
        assert mock_put.call_args.kwargs["json"] == {
            "device": DUMMY_DEVICE_H6163.device,
            "model": DUMMY_DEVICE_H6163.model,
            "cmd": {"name": "turn", "value": "on"},
        }
        assert success == False
        assert "401" in err  # http status
        assert "Test auth failed" in err  # http message
        assert "turn" in err  # command used
        assert DUMMY_DEVICE_H6163.device in err  # device used

    @patch("aiohttp.ClientSession.put")
    def test_turn_off_by_address(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_OK_RESPONSE
        )
        # act

        async def turn_off():
            async with Govee(API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                # use device address here
                return await govee.turn_off(DUMMY_DEVICE_H6163.device)

        success, err = loop.run_until_complete(turn_off())
        # assert
        assert err == None
        assert mock_put.call_count == 1
        assert (
            mock_put.call_args.kwargs["url"]
            == "https://developer-api.govee.com/v1/devices/control"
        )
        assert mock_put.call_args.kwargs["headers"] == {
            "Govee-API-Key": "SUPER_SECRET_KEY"
        }
        assert mock_put.call_args.kwargs["json"] == {
            "device": DUMMY_DEVICE_H6163.device,
            "model": DUMMY_DEVICE_H6163.model,
            "cmd": {"name": "turn", "value": "off"},
        }
        assert success == True

    @patch("aiohttp.ClientSession.get")
    def test_get_states(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICE_STATE
        )
        # act
        async def getDevices():
            async with Govee(API_KEY) as govee:
                # inject devices for testing
                govee._devices = DUMMY_DEVICES
                # for dev in DUMMY_DEVICES:
                #    results_per_device[dev], errors_per_device[dev] = await govee.get_state(dev)
                states = await govee.get_states()
                return states

        states = loop.run_until_complete(getDevices())
        # assert
        assert mock_get.call_count == 1  # only retrievable devices
        assert (
            mock_get.call_args.kwargs["url"]
            == "https://developer-api.govee.com/v1/devices/state"
        )
        assert mock_get.call_args.kwargs["headers"] == {
            "Govee-API-Key": "SUPER_SECRET_KEY"
        }
        assert (
            mock_get.call_args.kwargs["params"]["device"] == DUMMY_DEVICE_H6163.device
        )
        assert mock_get.call_args.kwargs["params"]["model"] == DUMMY_DEVICE_H6163.model
        assert len(states) == 2
        # to compare the
        DUMMY_DEVICE_H6163.timestamp = states[0].timestamp
        assert states[0] == DUMMY_DEVICE_H6163
        assert states[1] == DUMMY_DEVICE_H6104

    @patch("aiohttp.ClientSession.put")
    def test_set_brightness_to_high(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        brightness = 255  # too high

        # act
        async def set_brightness():
            async with Govee(API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.set_brightness(DUMMY_DEVICE_H6163, brightness)

        success, err = loop.run_until_complete(set_brightness())
        # assert
        assert success == False
        assert mock_put.call_count == 0
        assert "254" in err
        assert "brightness" in err

    @patch("aiohttp.ClientSession.put")
    def test_set_brightness_to_low(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        brightness = -1  # too high

        # act
        async def set_brightness():
            async with Govee(API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.set_brightness(DUMMY_DEVICE_H6163, brightness)

        success, err = loop.run_until_complete(set_brightness())
        # assert
        assert success == False
        assert mock_put.call_count == 0
        assert "254" in err
        assert "brightness" in err

    @patch("aiohttp.ClientSession.put")
    def test_set_brightness(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_OK_RESPONSE
        )
        # act
        async def set_brightness():
            async with Govee(API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                success, err = await govee.set_brightness(DUMMY_DEVICE_H6163.device, 42)
                return success, err, govee.devices

        success, err, devices = loop.run_until_complete(set_brightness())
        # assert
        assert err == None
        assert mock_put.call_count == 1
        assert (
            mock_put.call_args.kwargs["url"]
            == "https://developer-api.govee.com/v1/devices/control"
        )
        assert mock_put.call_args.kwargs["headers"] == {
            "Govee-API-Key": "SUPER_SECRET_KEY"
        }
        assert mock_put.call_args.kwargs["json"] == {
            "device": DUMMY_DEVICE_H6163.device,
            "model": DUMMY_DEVICE_H6163.model,
            "cmd": {
                "name": "brightness",
                "value": 42
                * 100
                // 254,  # we need to control brightness betweenn 0 .. 100
            },
        }
        assert devices[0].power_state == True
        assert success == True

    @patch("aiohttp.ClientSession.put")
    def test_set_color_temp(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_OK_RESPONSE
        )
        # act

        async def set_color_temp():
            async with Govee(API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.set_color_temp(DUMMY_DEVICE_H6163.device, 6000)

        success, err = loop.run_until_complete(set_color_temp())
        # assert
        assert err == None
        assert mock_put.call_count == 1
        assert (
            mock_put.call_args.kwargs["url"]
            == "https://developer-api.govee.com/v1/devices/control"
        )
        assert mock_put.call_args.kwargs["headers"] == {
            "Govee-API-Key": "SUPER_SECRET_KEY"
        }
        assert mock_put.call_args.kwargs["json"] == {
            "device": DUMMY_DEVICE_H6163.device,
            "model": DUMMY_DEVICE_H6163.model,
            "cmd": {"name": "colorTem", "value": 6000},
        }
        assert success == True

    @patch("aiohttp.ClientSession.put")
    def test_set_color(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_OK_RESPONSE
        )
        # act

        async def set_color():
            async with Govee(API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.set_color(DUMMY_DEVICE_H6163.device, (42, 43, 44))

        success, err = loop.run_until_complete(set_color())
        # assert
        assert err == None
        assert mock_put.call_count == 1
        assert (
            mock_put.call_args.kwargs["url"]
            == "https://developer-api.govee.com/v1/devices/control"
        )
        assert mock_put.call_args.kwargs["headers"] == {
            "Govee-API-Key": "SUPER_SECRET_KEY"
        }
        assert mock_put.call_args.kwargs["json"] == {
            "device": DUMMY_DEVICE_H6163.device,
            "model": DUMMY_DEVICE_H6163.model,
            "cmd": {"name": "color", "value": {"r": 42, "g": 43, "b": 44}},
        }
        assert success == True

    @patch("aiohttp.ClientSession.put")
    @patch("aiohttp.ClientSession.get")
    def test_turn_on_and_get_cache_state(self, mock_get, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_OK_RESPONSE
        )
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICE_STATE  # never touched
        )
        # act
        async def turn_on_and_get_state():
            async with Govee(API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                await govee.turn_on(DUMMY_DEVICE_H6163)
                # getting state to early (2s after switching)
                return await govee.get_states()

        states = loop.run_until_complete(turn_on_and_get_state())
        # assert
        assert states[0].source == GoveeSource.HISTORY
        assert mock_put.call_count == 1
        assert mock_get.call_count == 0  # may not get state
