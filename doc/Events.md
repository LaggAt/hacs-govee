# govee-api-laggat

## Events you may subscribe to

### Govee().events.online(bool)

Informs you if the Govee API is reachable by the library.

### Govee().events.new_device(GoveeDevice)

When a new device is found, passes you the device.

This may happen 
* when you called get_devices()
* when we're checking for devices regularly every 100 seconds