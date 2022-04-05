import argparse
import asyncio

from govee_api_laggat import Govee


async def foo(api_key):
    # this is for testing bug #72
    async with Govee(api_key) as govee:
        devices, err = await govee.get_devices()
        while True:
            for dev in devices:
                # configure each device to turn on before seting brightness
                dev.before_set_brightness_turn_on = True
                dev.learned_set_brightness_max = 100
                # turn and set bright
                success, err = await govee.set_brightness(dev, 254)
                print("set")
            await asyncio.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="govee_api_laggat examples")
    parser.add_argument("--api-key", dest="api_key", type=str, required=True)
    args = parser.parse_args()

    # going async ...
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(foo(args.api_key))
    finally:
        loop.close()
