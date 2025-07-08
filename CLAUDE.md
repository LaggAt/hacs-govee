# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Home Assistant custom component for Govee LED strips and devices. It integrates with the Govee API to control lights, switches, and monitor device status. The component is distributed via HACS (Home Assistant Community Store).

## Development Commands

### Testing and Linting
- `tox` - Run tests and linting for Python 3.12 and 3.13 environments
- `flake8 .` - Run style checks (configured in tox.ini and setup.cfg)
- `pytest` - Run unit tests
- `black .` - Format code with Black formatter
- `isort .` - Sort imports according to configuration

### Dependencies
- Development dependencies are in `requirements_test.txt`
- Runtime dependencies are specified in `manifest.json` under `requirements`

## Code Architecture

### Component Structure
The integration follows Home Assistant's custom component pattern:

- **`custom_components/govee/`** - Main integration directory
  - `__init__.py` - Component setup, platform loading, and lifecycle management
  - `config_flow.py` - Configuration flow for user setup
  - `const.py` - Constants and configuration keys
  - `light.py` - Light platform implementation
  - `learning_storage.py` - Device learning and configuration storage
  - `manifest.json` - Component metadata and dependencies

### Key Dependencies
- `govee-api-laggat==0.2.2` - Core Govee API client library
- `dacite==1.8.0` - Data structure conversion

### Integration Flow
1. User configures via config flow with API key
2. Component creates Govee API client with learning storage
3. Devices are discovered and registered as light entities
4. Learning storage manages device-specific settings in `config/govee_learning.yaml`

### Device Learning System
The component includes a learning system that auto-discovers device capabilities:
- Brightness ranges (0-100 vs 0-254)
- Power-on behavior for brightness changes
- Offline handling preferences

### Configuration Options
- **Disable Attribute Updates** - Allows disabling specific state updates from API or history
- **Offline Is Off** - Treats offline devices as off (useful for USB-powered devices)
- **Use Assumed State** - Controls state assumption behavior

## Code Style
- Line length: 88 characters (Black formatter standard)
- Import sorting with isort
- Flake8 linting with specific ignores for Black compatibility
- Type hints encouraged but not strictly enforced

## Testing
- Tests located in `tests/` directory
- Uses pytest with Home Assistant test framework
- Async testing with pytest-asyncio
- GitHub Actions run tests on Python 3.12 and 3.13

## Implementation Notes

### SSL Blocking Operations Fix
The `govee-api-laggat` library's `Govee.create()` method internally performs blocking SSL certificate verification (`load_verify_locations()`) which violates Home Assistant's asyncio guidelines. This integration includes a workaround that:

1. **Pre-creates SSL context** in a thread pool using `hass.async_add_executor_job()`
2. **Temporarily patches** `ssl.create_default_context()` to return the pre-created context
3. **Allows `Govee.create()`** to proceed without blocking the event loop
4. **Restores** the original SSL function after creation

This approach eliminates the SSL blocking warning while maintaining full compatibility with the external library. The implementation is in the `async_create_govee_safely()` function in `__init__.py`.

### pkg_resources Deprecation Warning
A deprecation warning may appear about `pkg_resources` being deprecated in favor of `importlib.metadata`. This warning comes from upstream dependencies (particularly the `google` package) and cannot be resolved at the integration level. The warning is harmless and will be resolved when upstream dependencies migrate to the new APIs.

## Git Subtree
The project includes the `python-govee-api` library as a git subtree in `.git-subtree/python-govee-api/`. Changes to the underlying API library should be made there and pushed to the separate repository.