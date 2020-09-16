import asyncio
from asynctest import TestCase, MagicMock, patch, CoroutineMock
from aiohttp import ClientSession
import datetime

from govee_api_laggat import Govee, GoveeDevice, GoveeDeviceState

_API_URL = "https://developer-api.govee.com"
_API_KEY = "SUPER_SECRET_KEY"
_RATELIMIT_TOTAL = 'Rate-Limit-Total' # The maximum number of requests you're permitted to make per minute.
_RATELIMIT_REMAINING = 'Rate-Limit-Remaining' # The number of requests remaining in the current rate limit window.
_RATELIMIT_RESET = 'Rate-Limit-Reset' # The time at which the current rate limit window resets in UTC epoch seconds.

# json results for lights
JSON_DEVICE = {
    'device': '40:83:FF:FF:FF:FF:FF:FF',
    'model': 'H6163',
    'deviceName': 'H6131_FFFF',
    'controllable': True,
    'retrievable': True,
    'supportCmds': [
        'turn',
        'brightness',
        'color',
        'colorTem'
    ]
}
JSON_DEVICES = {
    'data': {
        'devices': [
            JSON_DEVICE
        ]
    }
}
# light device
DUMMY_DEVICE = GoveeDevice(
    device = JSON_DEVICE['device'],
    model = JSON_DEVICE['model'],
    device_name = JSON_DEVICE['deviceName'],
    controllable = JSON_DEVICE['controllable'],
    retrievable = JSON_DEVICE['retrievable'],
    support_turn = 'turn' in JSON_DEVICE['supportCmds'],
    support_brightness = 'brightness' in JSON_DEVICE['supportCmds'],
    support_color = 'color' in JSON_DEVICE['supportCmds'],
    support_color_tem = 'colorTem' in JSON_DEVICE['supportCmds'],
)
# json results for light states
JSON_DEVICE_STATE = {
    "data": {
        "device": JSON_DEVICE['device'],
        "model": JSON_DEVICE['model'],
        "properties": [
            {
                "online": True
            },
            {
                "powerState": "on"
            },
            {
                "brightness": 254
            },
            {
                "color": {
                    "r": 139,
                    "b": 255,
                    "g": 0
                }
            }
        ]
    },
    "message": "Success",
    "code": 200
}
# light device state
DUMMY_DEVICE_STATE = GoveeDeviceState(
    device = JSON_DEVICE['device'],
    model = JSON_DEVICE['model'],
    online = True,
    power_state = True,
    brightness = 254,
    color = (139, 0, 255)
)

class GoveeTests(TestCase):

    @patch('aiohttp.ClientSession.get')
    def test_ping(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.text = CoroutineMock(
            return_value="Pong"
        )
        # act
        async def ping():
            async with Govee(_API_KEY) as govee:
                return await govee.ping_async()
        result, err = loop.run_until_complete(ping())
        # assert
        assert not err
        assert result
        assert mock_get.call_count == 1
        assert mock_get.call_args.kwargs['url'] == 'https://developer-api.govee.com/ping'

    @patch('aiohttp.ClientSession.get')
    def test_rate_limiter(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.text = CoroutineMock(
            return_value="Pong"
        )
        sleep_until = datetime.datetime.utcnow().timestamp() + 1
        mock_get.return_value.__aenter__.return_value.headers = {
            _RATELIMIT_TOTAL: 100,
            _RATELIMIT_REMAINING: 5, # by default below 5 it is sleeping
            _RATELIMIT_RESET: sleep_until
        }
        # act
        async def ping():
            async with Govee(_API_KEY) as govee:
                # first run uses defaults, so ping returns immediatly
                delay1, err1 = await govee.ping_async()
                # second run, rate limit sleeps until the second is over
                delay2, err2 = await govee.ping_async()
                return delay1, err1, delay2, err2
        delay1, err1, delay2, err2 = loop.run_until_complete(ping())
        # assert
        assert delay1 < 10 # this should return immediatly
        assert delay2 > 900 # this should sleep for around 1s
        assert not err1
        assert not err2
        assert mock_get.call_count == 2

    @patch('aiohttp.ClientSession.get')
    def test_rate_limiter_custom_threshold(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.text = CoroutineMock(
            return_value="Pong"
        )
        sleep_until = datetime.datetime.utcnow().timestamp() + 1
        mock_get.return_value.__aenter__.return_value.headers = {
            _RATELIMIT_TOTAL: 100,
            _RATELIMIT_REMAINING: 5, # by default below 5 it is sleeping
            _RATELIMIT_RESET: sleep_until
        }
        # act
        async def ping():
            async with Govee(_API_KEY) as govee:
                govee.rate_limit_on = 4
                assert govee.rate_limit_on == 4 # set did work
                # first run uses defaults, so ping returns immediatly
                delay1, err1 = await govee.ping_async()
                # second run, doesn't rate limit either
                delay2, err2 = await govee.ping_async()
                return delay1, err1, delay2, err2
        delay1, err1, delay2, err2 = loop.run_until_complete(ping())
        # assert
        assert delay1 < 10 # this should return immediatly
        assert delay2 < 10 # this should return immediatly
        assert not err1
        assert not err2
        assert mock_get.call_count == 2

    @patch('aiohttp.ClientSession.get')
    def test_get_devices(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value = JSON_DEVICES
        )
        # act
        async def getDevices():
            async with Govee(_API_KEY) as govee:
                return await govee.get_devices()
        result, err = loop.run_until_complete(getDevices())
        # assert
        assert err == None
        assert mock_get.call_count == 1
        assert mock_get.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices'
        assert mock_get.call_args.kwargs['headers'] == {'Govee-API-Key': 'SUPER_SECRET_KEY'}
        assert len(result) == 1
        assert isinstance(result[0], GoveeDevice)
        assert result[0].model == 'H6163'

    @patch('aiohttp.ClientSession.get')
    def test_get_devices_cache(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value = JSON_DEVICES
        )
        # act
        async def getDevices():
            async with Govee(_API_KEY) as govee:
                result, err = await govee.get_devices()
                cache = govee.devices
                return result, cache
        result, cache = loop.run_until_complete(getDevices())
        # assert
        assert mock_get.call_count == 1
        assert len(result) == 1
        assert result == cache
        
    @patch('aiohttp.ClientSession.get')
    def test_get_devices_invalid_key(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 401
        mock_get.return_value.__aenter__.return_value.text = CoroutineMock(
            return_value = {
                "INVALID_API_KEY"
            }
        )
        # act
        async def getDevices():
            async with Govee("INVALID_API_KEY") as govee:
                return await govee.get_devices()
        result, err = loop.run_until_complete(getDevices())
        # assert
        assert err
        assert "401" in err
        assert "INVALID_API_KEY" in err
        assert mock_get.call_count == 1
        assert mock_get.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices'
        assert mock_get.call_args.kwargs['headers'] == {'Govee-API-Key': 'INVALID_API_KEY'}
        assert len(result) == 0
    
    @patch('aiohttp.ClientSession.put')
    def test_turn_on(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value = {'code': 200, 'data': {}, 'message': 'Success'}
        )
        # act
        async def turn_on():
            async with Govee(_API_KEY) as govee:
                # inject a device for testing
                govee._devices = [DUMMY_DEVICE]
                return await govee.turn_on(DUMMY_DEVICE)
        success, err = loop.run_until_complete(turn_on())
        # assert
        assert err == None
        assert mock_put.call_count == 1
        assert mock_put.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control'
        assert mock_put.call_args.kwargs['headers'] == {'Govee-API-Key': 'SUPER_SECRET_KEY'}
        assert mock_put.call_args.kwargs['json'] == {
            "device": DUMMY_DEVICE.device,
            "model": DUMMY_DEVICE.model,
            "cmd": {
                "name": "turn",
                "value": "on"
            }
        }
        assert success == True

    @patch('aiohttp.ClientSession.put')
    def test_turn_off_by_address(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value = {'code': 200, 'data': {}, 'message': 'Success'}
        )
        # act
        async def turn_off():
            async with Govee(_API_KEY) as govee:
                # inject a device for testing
                govee._devices = [DUMMY_DEVICE]
                return await govee.turn_off(DUMMY_DEVICE.device) #use device address here
        success, err = loop.run_until_complete(turn_off())
        # assert
        assert err == None
        assert mock_put.call_count == 1
        assert mock_put.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control'
        assert mock_put.call_args.kwargs['headers'] == {'Govee-API-Key': 'SUPER_SECRET_KEY'}
        assert mock_put.call_args.kwargs['json'] == {
            "device": DUMMY_DEVICE.device,
            "model": DUMMY_DEVICE.model,
            "cmd": {
                "name": "turn",
                "value": "off"
            }
        }
        assert success == True

    @patch('aiohttp.ClientSession.get')
    def test_get_state(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value = JSON_DEVICE_STATE
        )
        # act
        async def getDevices():
            async with Govee(_API_KEY) as govee:
                # inject a device for testing
                govee._devices = [DUMMY_DEVICE]
                return await govee.get_state(DUMMY_DEVICE)
        result, err = loop.run_until_complete(getDevices())
        # assert
        assert err == None
        assert mock_get.call_count == 1
        assert mock_get.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices/state'
        assert mock_get.call_args.kwargs['headers'] == {'Govee-API-Key': 'SUPER_SECRET_KEY'}
        assert mock_get.call_args.kwargs['params'] == {'device': DUMMY_DEVICE.device, 'model': DUMMY_DEVICE.model}
        assert isinstance(result, GoveeDeviceState)
        assert result == DUMMY_DEVICE_STATE
