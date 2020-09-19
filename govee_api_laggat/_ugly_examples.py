from govee_api_laggat import *

if __name__ == '__main__':
    """ some example usages """

    async def main():
        print("Govee API client")
        print()

        if(len(sys.argv) == 1):
            print("python3 govee_api_laggat.py [command <API_KEY>]")
            print("<command>'s: ping, devices, turn_on, turn_off, get_state, brightness")
            print()

        command = "ping"
        api_key = ""
        if len(sys.argv) > 1:
            command = sys.argv[1]
            if len(sys.argv) > 2:
                api_key = sys.argv[2]
        
        # show usage with content manager
        async with Govee(api_key) as govee:
            if command=="ping":
                ping_ms, err = await govee.ping_async()
                print(f"Ping success? {bool(ping_ms)} after {ping_ms}ms")
            elif command=="devices":
                print("Devices found: " + ", ".join([
                    item.device_name + " (" + item.device + ")"
                    for item
                    in govee.get_devices()
                ]))
            elif command=="turn_on":
                devices, err = await govee.get_devices()
                for lamp in devices:
                    success, err = await govee.turn_on(lamp)
            elif command=="turn_off":
                devices, err = await govee.get_devices()
                for lamp in devices:
                    success, err = await govee.turn_off(lamp.device) # by id here
            elif command=="state":
                devices, err = await govee.get_devices()
                for lamp in devices:
                    state, err = await govee.get_state(lamp)
                    if err:
                        print(f'{lamp.device_name} error getting state: {err}')
                    else:
                        print(f'{lamp.device_name} is powered on? {state.power_state}')
                        print(f'{lamp.device_name} brightness? {state.brightness}')
            elif command=="brightness":
                devices, err = await govee.get_devices()
                for lamp in devices:
                    brightness = 254
                    state, err = await govee.get_state(lamp)
                    if state.brightness > 128:
                        brightness = 128
                    print(f'{lamp.device_name} setting brightness to {brightness}')
                    success, err = await govee.set_brightness(lamp, brightness)
            elif command=="colortemp":
                devices, err = await govee.get_devices()
                for lamp in devices:
                    coltemp = 6000
                    print(f'{lamp.device_name} setting color temperature to {coltemp}')
                    success, err = await govee.set_color_temp(lamp, coltemp)
            elif command=="color":
                devices, err = await govee.get_devices()
                for lamp in devices:
                    color = (254, 0, 0) #red
                    state, err = await govee.get_state(lamp)
                    if state.color[0] > 128:
                        color = (0, 254, 0) #green
                    print(f'{lamp.device_name} setting color to {color}')
                    success, err = await govee.set_color(lamp, color)

        
        # show usage without content manager, but await and close()
        if command=="ping":
            govee = await Govee.create(api_key)
            ping_ms, err = await govee.ping_async()
            print(f"second Ping success? {bool(ping_ms)} after {ping_ms}ms")
            await govee.close()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    