# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

[ ] According to Govee API-support a batch status update is coming - when it is there we could save requests (which are limited to 60/minute)
  This feature is planned for 2021.

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.1.x] - 2021-04-16

### Added

- Support for H6104 and similar devices (which are controllable, but not retrievable)
- async rate_limit_delay() public available to wait for rate limiting
- better tracking of error 429 (rate limit hit)
- debug log contains full json and object states
- debug log contains rate limiting information
- online/offline state for integration, and each individual bulb
- online event firing once when API goes online, offline
- learning info may configure 'before_set_brightness_turn_on: True', to send a turn_on when setting brightness > 0
- storage example added for devs
- Python 3.9 as test environment (previously 3.7, 3,8)

### Changed

- Setting brightness is different on different devices. Most devices use a Range of 0-100, some use 0-254.
  ~~Default in this client is 0..100, please tell me when we find models which you can only set to 40% brightness to add them to a list.~~
  The ranges for setting and getting brightness from the API are learned now. If you implement this package override GoveeAbstractLearningStorage (as in tests) to save/restore learned information on restarts.
- According to Govee API-support we could fix jumping back to old state after controlling device,
  by delaying status request for 2-3 seconds.
  Status request is answered from cache after any command within two seconds
- GoveeDevice contains device and state information, GoveeDeviceState is removed
- Brightness is setting Power_State now in cached state
- calculated brightness should be more exact when transforming between ranges 0-254/0-100
  this should avoid jumping when the real value from API arrives as we set brightness to what we expect from API
- update most fields in GoveeDevice unsing a centralized method, and made it configurable to ignore some fields set via API or HISTORY. e.g. to ignore online state change coming from API, and ignore power_state from history, call Govee.ignore_device_attributes("API:online;HISTORY:power_state"); This was made to enable users to help themselves when Govee API has issues.
- *BREAKING CHANGE* GoveeDevice.source isn't a str anymore, it's now an Enum GoveeSource.

### Removed

- control color by rgb values - not used by home assistant.

### Fixed

- When getting State API-Error did return None, instead of the error message
- brightness was set with 0-254 Values for devices not supporting it
- Error 429 (hopefully), this error may happen, if other devices use the API from the same IP. It shouldn't happen that often anymore
- Setting brightness to 1 (0-254 Range) did set brightness to 0 (0-100 Range.)

## [0.0.27] - 2020-09-20

### Added

- implementation of Govee API 1.0
- implemented rate limiting
- control on/off, brightness, color temperature, color
- get state for on/off, brightness, color temperature, color, rate limiting details
- build pipeline, deploy to PyPi
