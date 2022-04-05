import argparse
import asyncio
from typing import Dict

from govee_api_laggat import Govee, GoveeAbstractLearningStorage, GoveeLearnedInfo


async def all_examples(api_key, your_learning_storage):
    ### using as async content manager
    async with Govee(api_key, learning_storage=your_learning_storage) as govee:
        # i will explain that learning_storage below.

        # check connection: never fails, just tells if we can connect the API.
        online = await govee.check_connection()
        # you may also register for an event, when api is going offline/online
        govee.events.online += lambda is_online: print(f"API is online: {is_online}")
        # you may also ask if the client was online the last time it tried to connect:
        _ = govee.online
        # get devices list - this is mandatory, you need to successfully get the devices first!
        devices, err = await govee.get_devices()
        if err:  # TODO: Put in proper exception for async context manager
            print(err)
            await govee.close()
            return
        if not devices:
            print("No devices found")
            await govee.close()
            return
        # get states
        devices = (
            await govee.get_states()
        )  # yes, states returns the same object containing device and state info
        # once you have called get_devices() once, you can get this list from cache:
        cache_devices = govee.devices
        # or a specific device from cache
        cache_device = govee.device(devices[0].device)  # .device returns device-ID
        # turn a device on/off (using device-object or device-id works for all calls)
        success, err = await govee.turn_on(cache_device)
        success, err = await govee.turn_off(cache_device.device)
        # set brightness of a device (we scale all ranges to 0-254, Govee uses 0-100 sometimes)
        success, err = await govee.set_brightness(cache_device, 254)
        # set color temperature (2000-9000)
        success, err = await govee.set_color_temp(cache_device, 6000)
        # set color in RGB (each 0-255)
        red = 0
        green = 0
        blue = 255
        success, err = await govee.set_color(cache_device, (red, green, blue))

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
    govee = await Govee.create(api_key, learning_storage=your_learning_storage)
    if err:
        print(err)
        await govee.close()
        return
    # don't forget the mandatory get_devices!
    devices, err = await govee.get_devices()
    if not devices:
        print("No devices found")
        await govee.close()
        return
    # let's turn off the light at the end
    success, err = await govee.turn_off(cache_device.device)
    await govee.close()


### so what is that: learning_storage = your_learning_storage
# as we control led strips and get state values from them we also learn how a specific led strip behaves.
# e.g. if the brightness is set in a range from 0-254 or 0-100, as some models use this or the other range.
# no configuration is needed from your user, but you as developer should consider saving/restoring those values.
# if you don't do this, learning will start with no information on every restart. Do not do this in production.

# to make this easy you can just implement GoveeAbstractLearningStorage and override two methods:
class YourLearningStorage(GoveeAbstractLearningStorage):
    async def read(self) -> Dict[str, GoveeLearnedInfo]:
        return (
            {}
        )  # get the last saved learning information from disk, database, ... and return it.

    async def write(self, learned_info: Dict[str, GoveeLearnedInfo]):
        persist_this_somewhere = learned_info  # save this dictionary to disk


# then
your_learning_storage = YourLearningStorage()

# and your are good to go
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="govee_api_laggat examples")
    parser.add_argument("--api-key", dest="api_key", type=str, required=True)
    args = parser.parse_args()

    # going async ...
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(all_examples(args.api_key, your_learning_storage))
    finally:
        loop.close()
