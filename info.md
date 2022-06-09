[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]


_Component to integrate with [Govee][hacs-govee]._

**This component will set up the following platforms.**

Platform | Description
-- | --
`light` | Control your lights.

<!-- ![example][exampleimg] -->

{% if not installed %}
## Installation

1. In HACS/Integrations, search for 'Govee' and click install.
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "govee".

{% endif %}

## Configuration is done in the UI

Usually you just add the integration, enter api-key and poll interval and you are good to go. When you need further help you can look here:

* [Documentation on GitHub](https://github.com/LaggAt/hacs-govee/blob/master/README.md)
* [Support thread on Home Assistant Community](https://community.home-assistant.io/t/govee-led-strips-integration/228516/1)
* [Is there an issue with Govee API or the library?](https://raw.githubusercontent.com/LaggAt/actions/main/output/govee-api-up.png)
* [Version statistics taken from Home Assistant Analytics](https://raw.githubusercontent.com/LaggAt/actions/main/output/goveestats_installations.png)

## Sponsor

A lot of effort is going into that integration. So if you can afford it and want to support us:

<a href="https://www.buymeacoffee.com/LaggAt" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

Thank you!

<!---->

***

[hacs-govee]: https://github.com/LaggAt/hacs-govee
[buymecoffee]: https://www.buymeacoffee.com/LaggAt
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[exampleimg]: example.png
[license-shield]: https://img.shields.io/github/license/LaggAt/hacs-govee
[maintenance-shield]: https://img.shields.io/badge/maintainer-Florian%20Lagg-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/custom-components/hacs-govee.svg?style=for-the-badge
[releases]: https://github.com/custom-components/hacs-govee/releases
