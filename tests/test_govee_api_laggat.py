import asyncio
from asynctest import TestCase, MagicMock, patch, CoroutineMock
from aiohttp import ClientSession

from govee_api_laggat import Govee, GoveeLightInfo

_API_URL = "https://developer-api.govee.com"
_API_KEY = "SUPER_SECRET_KEY"

class GoveeTests(TestCase):

    @patch('aiohttp.ClientSession.get')
    def test_ping_pong(self, mock_get):
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
        result = loop.run_until_complete(ping())
        # assert
        assert mock_get.call_count == 1
        assert mock_get.call_args.kwargs['url'] == 'https://developer-api.govee.com/ping'
        assert result == True

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
        result = loop.run_until_complete(getDevices())
        # assert
        assert mock_get.call_count == 1
        assert mock_get.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices'
        assert mock_get.call_args.kwargs['headers'] == {'Govee-API-Key': 'SUPER_SECRET_KEY'}
        assert len(result) == 1
        assert isinstance(result[0], GoveeLightInfo)
        assert result[0].model == 'H6163'

    