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

## [0.1.x] - 2020-09-21
### Added
- Support for H6104 and similar devices (which are controllable, but not retrievable)
- async rate_limit_delay() public available to wait for rate limiting
### Changed
- According to Govee API-support brightness is set different on different devices:
  0-100: "H6089","H7022","H6086","H6135","H6137","H7005","H6002","H6003" (implemented)
  0-255: all others (this implementation existed)
  I think this information isn't perfectly correct, my model is 0-100 but not listed. Mail sent.
- According to Govee API-support we could fix jumping back to old state after controlling device, 
  by delaying status request for 2-3 seconds. 
  Status request is answered from cache after any command within two seconds
### Removed
- control color by rgb values - not used by home assistant.

## [0.0.27] - 2020-09-20
### Added
- implementation of Govee API 1.0
- implemented rate limiting
- control on/off, brightness, color temperature, color
- get state for on/off, brightness, color temperature, color, rate limiting details
- build pipeline, deploy to PyPi
