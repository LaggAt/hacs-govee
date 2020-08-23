from unittest import TestCase
import requests
import requests_mock
from govee_api import Govee

_API_URL = "https://developer-api.govee.com"
_API_KEY = "SUPER_SECRET_KEY"

class TestGovee(TestCase):
    def test_ping_pong(self):
        # arrange
        with requests_mock.Mocker() as m:
            m.get(_API_URL + "/ping", text='Pong')
            g = Govee(_API_KEY)

            # act
            r = g.Ping()

            # assert
            self.assertTrue(r)
    
    def test_getDevices_DummyDevice(self):
        # arrange
        with requests_mock.Mocker() as m:
            m.get(_API_URL + "/v1/devices", json = {
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
            })
            g = Govee(_API_KEY)

            # act
            r = g.GetDevices()

            # assert
            self.assertTrue(r[0])
    