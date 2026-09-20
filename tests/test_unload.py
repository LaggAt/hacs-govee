"""Tests for Govee config-entry unloading."""

from custom_components.govee import _unload_component_entry


class _ConfigEntries:
    async def async_forward_entry_unload(self, entry, component):
        """Return the result asynchronously, like Home Assistant does."""
        return False


class _Hass:
    config_entries = _ConfigEntries()


async def test_unload_component_entry_awaits_result():
    """The unload helper must await Home Assistant's coroutine."""
    result = await _unload_component_entry(_Hass(), object(), "light")

    assert result is False
