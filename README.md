# 'Govee LED strips' integration

The Govee integration allows you to control an monitor lights using the Govee API.

To set up this integration, click Configuration in the sidebar and then click Integrations. Click the + icon to add "Govee LED strips" to the integrations. An API-Key
is necessary, you need to obtain it in the 'Govee Home' App on your mobile, in the User menu - About us - Request API-Key screen. The key will be sent to you by mail.

## Pulling or assuming state

Some devices do not support pulling state, in this case we use assumed state on your last input.
For others we assume the state just after controlling the light, but will otherwise request from the cloud api.

## What is config/govee_learning.yaml

Usually you don't have to do anything here - just in case something feels wrong read on:

```
40:83:FF:FF:FF:FF:FF:FF:
  set_brightness_max: 100
  get_brightness_max: 100
  before_set_brightness_turn_on: false
  config_offline_is_off: false
```

Different Govee devices use different settings. These will be learned by the used library, or can be configured by you. 

* set_brightness_max: is autolerned, defines the range to set the brightness to 0-100 or 0-254.
* get_brightness_max: is autolerned, defines the range how to interpet brightness state (also0-100 or 0-254).
* before_set_brightness_turn_on: Configurable by you, default false. When true, if the device is off and you set the brightness > 0 the device is turned on first, then after a second the brightness is set. Some device don't turn on with the set brightness command.
* config_offline_is_off: Configurable by you, default false. This is useful if your device is e.g. powered by a TV's USB port, where when the TV is off, the LED is also off. Usually we stay in the state we know, this changes this to OFF state when the device disconnects.

## Support

Support thread is here: <https://community.home-assistant.io/t/govee-led-strips-integration/228516>
There you'll also find links to code repositories and their issue trackers.

For bug reports include debug log, which could be enabled in configuration YAML + restart:

```YAML
logger:
  default: warning
  logs:
    homeassistant.components.govee: debug
    custom_components.govee: debug
    govee_api_laggat: debug
```

Then on Settings - Logs click on “full logs” button and add them to the bug report after removing personal data.

## Caveats

You can set a pull interval, don't set it too low as the API has a limit of 60 requests per minute, and each device needs one request per state pull and control action.
If you have more than one lamp use a higher interval. Govee wants to implement a single request for all devices in 2021.

Once the integration is active you will see all your registered devices, and may control on/off, brightness, color temperature and color.