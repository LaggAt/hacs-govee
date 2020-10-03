import copy
from govee_api_laggat import GoveeDevice

API_URL = "https://developer-api.govee.com"
API_KEY = "SUPER_SECRET_KEY"
# The maximum number of requests you're permitted to make per minute.
RATELIMIT_TOTAL = 'Rate-Limit-Total'
# The number of requests remaining in the current rate limit window.
RATELIMIT_REMAINING = 'Rate-Limit-Remaining'
# The time at which the current rate limit window resets in UTC epoch seconds.
RATELIMIT_RESET = 'Rate-Limit-Reset'

# json results for lights
JSON_DEVICE_H6163 = {
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
JSON_DEVICE_H6104 = {
    'device': '99:F8:FF:FF:FF:FF:FF:FF',
    'model': 'H6104',
    'deviceName': 'H6104_22DC',
    'controllable': True,
    'retrievable': False,
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
            JSON_DEVICE_H6163,
            JSON_DEVICE_H6104
        ]
    }
}
JSON_DEVICES_EMPTY = {
    'data': {
        'devices': []
    }
}
JSON_OK_RESPONSE = {'code': 200, 'data': {}, 'message': 'Success'}
# light device
DUMMY_DEVICE_H6163 = GoveeDevice(
    device=JSON_DEVICE_H6163['device'],
    model=JSON_DEVICE_H6163['model'],
    device_name=JSON_DEVICE_H6163['deviceName'],
    controllable=JSON_DEVICE_H6163['controllable'],
    retrievable=JSON_DEVICE_H6163['retrievable'],
    support_cmds=JSON_DEVICE_H6163['supportCmds'],
    support_turn='turn' in JSON_DEVICE_H6163['supportCmds'],
    support_brightness='brightness' in JSON_DEVICE_H6163['supportCmds'],
    support_color='color' in JSON_DEVICE_H6163['supportCmds'],
    support_color_tem='colorTem' in JSON_DEVICE_H6163['supportCmds'],
    online=True,
    power_state=True,
    brightness=254,
    color=(139, 0, 255),
    timestamp = 0,
    source = 'api', # this device supports status
    error = None,
    lock_set_until = 0,
    lock_get_until = 0,
    learned_set_brightness_max = 100,
    learned_get_brightness_max = 254,
)
DUMMY_DEVICE_H6104 = GoveeDevice(
    device=JSON_DEVICE_H6104['device'],
    model=JSON_DEVICE_H6104['model'],
    device_name=JSON_DEVICE_H6104['deviceName'],
    controllable=JSON_DEVICE_H6104['controllable'],
    retrievable=JSON_DEVICE_H6104['retrievable'],
    support_cmds=JSON_DEVICE_H6104['supportCmds'],
    support_turn='turn' in JSON_DEVICE_H6104['supportCmds'],
    support_brightness='brightness' in JSON_DEVICE_H6104['supportCmds'],
    support_color='color' in JSON_DEVICE_H6104['supportCmds'],
    support_color_tem='colorTem' in JSON_DEVICE_H6104['supportCmds'],
    online=True,
    power_state=False,
    brightness=0,
    color=(0, 0, 0),
    timestamp = 0,
    source = 'history',
    error = None,
    lock_set_until = 0,
    lock_get_until = 0,
    learned_set_brightness_max = 254,
    learned_get_brightness_max = None,
)
DUMMY_DEVICES = {
    DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163,
    DUMMY_DEVICE_H6104.device: DUMMY_DEVICE_H6104,
}

# json results for light states
JSON_DEVICE_STATE = {
    "data": {
        "device": JSON_DEVICE_H6163['device'],
        "model": JSON_DEVICE_H6163['model'],
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
def JSON_DEVICE_STATE_WITH_BRIGHTNESS(brightness):
    val = copy.deepcopy(JSON_DEVICE_STATE)
    val["data"]["properties"][2]['brightness'] = brightness
    return val
                



# learning infos
LEARNED_NOTHING = {}
