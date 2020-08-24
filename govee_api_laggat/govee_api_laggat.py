""" client to connect to the govee API """

import sys
import logging
from dataclasses import dataclass
import requests
from typing import List

_VERSION = "0.0.1" 
_LOGGER = logging.getLogger(__name__)
_API_URL = "https://developer-api.govee.com"

@dataclass
class GoveeLightInfo(object):
    Device: str
    Model: str
    DeviceName: str
    Controllable: bool
    Retrievable: bool
    SupportTurn: bool
    SupportBrightness: bool
    SupportColor: bool
    SupportColorTem: bool

class Govee(object):
    """ client to connect to the govee API """

    def __init__(self, api_key: str):
        """ init with an API_KEY """
        self._api_key = api_key

    def _getAuthHeaders(self):
        return {'Govee-API-Key': self._api_key}
    
    def Ping(self) -> bool:
        _LOGGER.debug("ping")
        url = (_API_URL + "/ping")
        r = requests.get(url=url)
        if not r.ok:
            raise Exception("ping failed: " + str(r.status_code))
        return 'Pong' == r.text

    def GetDevices(self) -> List[GoveeLightInfo]:
        _LOGGER.debug("get devices")
        url = (
            _API_URL
            + "/v1/devices"
        )
        r = requests.get(url=url, headers = self._getAuthHeaders())
        if not r.ok:
            raise Exception("get devices failed: " + str(r.status_code))
        result = r.json()
        light_infos = [
            GoveeLightInfo(
                item["device"],
                item["model"],
                item["deviceName"],
                item["controllable"],
                item["retrievable"],
                "turn" in item["supportCmds"],
                "brightness" in item["supportCmds"],
                "color" in item["supportCmds"],
                "colorTem" in item["supportCmds"]
            ) for item in result["data"]["devices"]
        ]
        return light_infos

if __name__ == '__main__':
    """ test connectivity """
    print("Govee API client v" + _VERSION)
    print()

    if(len(sys.argv) == 1):
        print("python3 govee_api_laggat.py [command <API_KEY>]")
        print("<command>'s: ping, devices")
        print()

    command = "ping"
    api_key = ""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if len(sys.argv) > 2:
            api_key = sys.argv[2]

    govee = Govee(api_key)

    if command=="ping":
        print("Ping success? " + str(govee.Ping()))
    elif command=="devices":
        print("Devices found: " + ", ".join([
            item.DeviceName + " (" + item.Device + ")"
            for item
            in govee.GetDevices()
        ]))
    