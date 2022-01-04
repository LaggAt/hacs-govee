# 'Govee' integration

The Govee integration allows you to control and monitor lights and switches using the Govee API.

## Installation

* The installation is done inside [HACS](https://hacs.xyz/) (Home Assistant Community Store). If you don't have HACS, you must install it before adding this integration. [Installation instructions here.](https://hacs.xyz/docs/setup/download)
* Once HACS is installed, navigate to the 'Integrations' tab in HACS and search for the 'Govee' integration there. Click "Download this repository in HACS". On the next screen, select "Download". Once fully downloaded, restart HomeAssistant.
* In the sidebar, click 'Configuration', then 'Devices & Services'. Click the + icon to add "Govee" to your Home Assistant installation. An API key
is required, you need to obtain it in the 'Govee Home' app on your mobile device. This can be done from the Account Page (Far right icon at the bottom) > Settings (top right icon) > About Us > Apply for API Key. The key will be sent to your account email.

## Sponsor

A lot of effort is going into that integration. So if you can afford it and want to support us:

<a href="https://www.buymeacoffee.com/LaggAt" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

Thank you!

## Is it stable?

We think so. It is used often, and the support thread is active.

![usage statistics per version](https://raw.githubusercontent.com/LaggAt/actions/main/output/goveestats_installations.png)

Usage Data is taken from Home Assistant analytics, and plotted over time by us. You need to enable analytics if you want to show here.

## Is there an issue right now?

This graph uses the same library to do simple checks. If you see round dots on the right of the graph (= today), probably there is an issue.

![Govee API running?](https://raw.githubusercontent.com/LaggAt/actions/main/output/govee-api-up.png)

## Pulling or assuming state

Some devices do not support pulling state. In this case we assume the state on your last input.
For others, we assume the state just after controlling the light, but will otherwise request it from the cloud API.

## DISABLING state updates for specific attributes

You shouldn't use this feature in normal operation, but if something is broke e.g. on Govee API you could help yourself and others on the forum with a little tweak.

Not all attribute updates can be disabled, but most can. Fiddling here could also lead to other misbehavours, but it could help with some issues.

Let's talk about an example:

### What if power_state isn't correctly returned from API?

We can have state from two sources: 'API' and 'HISTORY'. History for example means, when we turn on a light we already guess the state will be on, so we set a history state of on before we get data from the API. In the default configuration you could also see this, as it shows two buttons until the final state from API arrives.

![two-button-state](https://community-assets.home-assistant.io/original/3X/d/7/d7d2ee09520672e7671fdeed5bb461fcfaab8493.png)

So let's say we have an issue, that the ON/OFF state from API is wrong, we always get OFF. (This happended, and this is why I developed that feature). If we disable the power state we get from API we could work around this, and thats exactly what we do:

1. 'API' or 'History': state from which source do we want to disable? In our example the API state is wrong, as we could see in logs, so we choose 'API'
2. Look up the attribute you want to disable in GoveeDevice data class. Don't worry, you don't need to understand any of the code here. [Here is that data class (click)](https://github.com/LaggAt/python-govee-api/blob/master/govee_api_laggat/govee_dtos.py). In our Example we will find 'power_state'
3. Next, in Home Assistant we open Configuration - Integrations and click on the options on the Govee integration. Here is an example how this config option could look:

![DISABLE state updates option](https://community-assets.home-assistant.io/original/3X/6/c/6cffe0de8b100ef4efc0e460482ff659b8f9444c.png)

4. With the information from 1. and 2. we could write a string disabling power_state from API. This will do the trick for our case:
```
API:power_state
```

IF you want to disable a state from both sources, do that separately. You may have as many disables as you like.
```
API:online;HISTORY:online
```

[If you fix an issue like that, consider helping other users on the forum thread (click).](https://community.home-assistant.io/t/govee-integration/228516/438?u=laggat)

ALWAYS REMEMBER: this should always be a temporarly workaround, if you use it in daily business you should probably request a feature or bug fix :)

To remind you disabling it asap, this wil log a warning on every update.

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

* set_brightness_max: is autolearned, defines the range to set the brightness to 0-100 or 0-254.
* get_brightness_max: is autolearned, defines the range how to interpet brightness state (also 0-100 or 0-254).
* before_set_brightness_turn_on: Configurable by you, default false. When true, if the device is off and you set the brightness > 0 the device is turned on first, then after a second the brightness is set. Some device don't turn on with the set brightness command.
* config_offline_is_off: Configurable by you, default false. This is useful if your device is e.g. powered by a TV's USB port, where when the TV is off, the LED is also off. Usually we stay in the state we know, this changes this to OFF state when the device disconnects.

## Support

Support thread is here: <https://community.home-assistant.io/t/govee-led-strips-integration/228516>
There you'll also find links to code repositories and their issue trackers.

For bug reports, include the debug log, which can be enabled in configuration YAML + restart:

```YAML
logger:
  default: warning
  logs:
    homeassistant.components.govee: debug
    custom_components.govee: debug
    govee_api_laggat: debug
```

Then in Settings - Logs click on “full logs” button and add them to the bug report after removing personal data.

## Caveats

You can set a pull interval, but don't set it too low as the API has a limit of 60 requests per minute, and each device needs one request per state pull and control action.
If you have more than one lamp use a higher interval. Govee wants to implement a single request for all devices in 2021.

Once the integration is active, you will see all your registered devices, and may control on/off, brightness, color temperature and color.
