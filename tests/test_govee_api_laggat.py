import asyncio
from asynctest import TestCase, MagicMock, patch, CoroutineMock
from aiohttp import ClientSession

from govee_api_laggat import Govee, GoveeDevices

_API_URL = "https://developer-api.govee.com"
_API_KEY = "SUPER_SECRET_KEY"

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
    def test_get_devices(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value = {
                'data': {
                    'devices': [
                        {
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
                    ]
                }
            }
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
        assert isinstance(result[0], GoveeDevices)
        assert result[0].model == 'H6163'

    @patch('aiohttp.ClientSession.get')
    def test_get_devices_cache(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value = {
                'data': {
                    'devices': [
                        {
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
                    ]
                }
            }
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
        