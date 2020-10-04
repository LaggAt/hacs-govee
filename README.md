# govee-api-laggat Package

Python implementation of the govee API 1.0 to control the cheap and colorful LED strips.

## Why / Motivation

I want to use this package in an Home Assistant Component to control my new light strips.

![demo of integration](doc/media/demo_20200920.gif)

Remember: this is NOT the integration, but the library the integration uses.

The integration project lives here: [github.com/LaggAt/home-assistant-core](https://github.com/LaggAt/home-assistant-core/tree/feature/govee-led-strips/homeassistant/components/govee)

## Usage in your project

```python
### using as async content manager
async with Govee(api_key, learning_storage = your_learning_storage) as govee:
    # i will explain that learning_storage below.

    # /ping endpoint in Govee API (uses no api_key)
    ping_ms, err = await govee.ping()
    # get devices list
    devices, err = await govee.get_devices()
    # get states (you must get the devices first)
    devices, err = get_states(self)  # yes, states returns the same object containing device and state info
    # once you have called get_devices() once, you can get this list from cache:
    cache_devices = govee.devices
    # or a specific device from cache
    cache_devices = govee.device(devices[0].device)  # .device returns device-ID
    # turn a device on/off (using device-object or device-id works for all calls)
    success, err = await govee.turn_on(devices[0])
    success, err = await govee.turn_off(devices[0].device)
    # set brightness of a device (we scale all ranges to 0-254, Govee uses 0-100 sometimes)
    success, err = await govee.set_brightness(devices[0], 254)
    # set color temperature (2000-9000)
    success, err = await govee.set_color_temp(devices[0], 6000)
    # set color in RGB (each 0-255)
    red = 0
    green = 0
    blue = 255
    success, err = await govee.set_color_temp(devices[0], (red, green, blue))

    ### rate limiting:
    # set requests left before the rate limiter stops us
    govee.rate_limit_on = 5  # 5 requests is the default
    current_rate_limit_on = govee.rate_limit_on
    # see also these properties:
    total = govee.rate_limit_total
    remaining = govee.rate_limit_remaining
    reset = govee.rate_limit_reset  # ... or more readable:
    reset_seconds = govee.rate_limit_reset_seconds


### without async content manager:
govee = await Govee.create(api_key, learning_storage = your_learning_storage)
ping_ms, err = await govee.ping()  # all commands as above
print(f"second Ping success? {bool(ping_ms)} after {ping_ms}ms")
await govee.close()

### so what is that: learning_storage = your_learning_storage
# as we control led strips and get state values from them we also learn how a specific led strip behaves.
# e.g. if the brightness is set in a range from 0-254 or 0-100, as some models use this or the other range.
# no configuration is needed from your user, but you as developer should consider saving/restoring those values.
# if you don't do this, learning will start with no information on every restart. Do not do this in production.

# to make this easy you can just implement GoveeAbstractLearningStorage and override two methods:
class YourLearningStorage(GoveeAbstractLearningStorage):
    async def read(self) -> Dict[str, GoveeLearnedInfo]:
        return {}  # get the last saved learning information from disk, database, ... and return it.
    async def write(self, learned_info: Dict[str, GoveeLearnedInfo]):
        persist_this_somewhere = learned_info  # save this dictionary to disk
# then
your_learning_storage = YourLearnignStorage()
# and your are good to go
async with Govee(api_key, learning_storage = your_learning_storage) as govee:
    pass
```

## Govee trademark

<img src="doc/media/govee_logo_orig.jpg" alt="Govee logo" width="300" height="91">

Govee and the Govee logo are trademarks or registered trademarks of Shenzhen Intellirock Company Limited, and used by Govee with permission. Neither your use of the Govee Logo grant you any right, title, or interest in, or any license to reproduce or otherwise use, the Govee logo. You shall not at any time, nor shall you assist others to, challenge Govee's right, title, or interest in, or the validity of, the Govee Marks.

## Links

- PyPi project and python package: [pypi.org/project/govee-api-laggat](https://pypi.org/project/govee-api-laggat/)
- Home Assistant integration Git: [github.com/LaggAt/home-assistant-core](https://github.com/LaggAt/home-assistant-core/tree/feature/govee-led-strips/homeassistant/components/govee)

## API Key

To get an api key you need to install the 'Govee Home' app on your mobile and browse the user tab - About - Request API key. Usually you get your key within seconds by mail.

## Issues / Improvements

There are two projects, this one is the API implementation for python. 
The second project is the integration into Home Assistant which currently lives [here: github.com/LaggAt/home-assistant-core](https://github.com/LaggAt/home-assistant-core/tree/feature/govee-led-strips/homeassistant/components/govee)

Feel free to fork and start a pull request in your feature/bug branch. 
If you cannot fix or extend it yourself, you may want to add an issue in the correct project, but it may take a bit longer.

## development

* pip install setuptools wheel tox
* Fork and clone the repository
* Make a 'feature/NAME' or 'bug/NAME' branch
* Run tests: tox
* commit and start a pull request
