"""Govee platform."""

from datetime import timedelta, datetime
import logging

from propcache import cached_property

from govee_api_laggat import Govee, GoveeDevice, GoveeError
from govee_api_laggat.govee_dtos import GoveeSource

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_DELAY
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import color

from .const import (
    DOMAIN,
    CONF_OFFLINE_IS_OFF,
    CONF_USE_ASSUMED_STATE,
    COLOR_TEMP_KELVIN_MIN,
    COLOR_TEMP_KELVIN_MAX,
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Govee Light platform."""
    _LOGGER.debug("Setting up Govee lights")
    config = entry.data
    options = entry.options
    hub = hass.data[DOMAIN]["hub"]

    # refresh
    update_interval = timedelta(
        seconds=options.get(CONF_DELAY, config.get(CONF_DELAY, 10))
    )
    coordinator = GoveeDataUpdateCoordinator(
        hass, _LOGGER, update_interval=update_interval, config_entry=entry
    )
    # Fetch initial data so we have data when entities subscribe
    hub.events.new_device += lambda device: add_entity(
        async_add_entities, hub, entry, coordinator, device
    )
    await coordinator.async_refresh()

    # Add devices
    for device in hub.devices:
        add_entity(async_add_entities, hub, entry, coordinator, device)
    # async_add_entities(
    #     [
    #         GoveeLightEntity(hub, entry.title, coordinator, device)
    #         for device in hub.devices
    #     ],
    #     update_before_add=False,
    # )


def add_entity(async_add_entities, hub, entry, coordinator, device):
    async_add_entities(
        [GoveeLightEntity(hub, entry.title, coordinator, device)],
        update_before_add=False,
    )


class GoveeDataUpdateCoordinator(DataUpdateCoordinator):
    """Device state update handler."""

    def __init__(self, hass, logger, update_interval=None, *, config_entry):
        """Initialize global data updater."""
        self._config_entry = config_entry

        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=update_interval,
            update_method=self._async_update,
        )

    @property
    def use_assumed_state(self):
        """Use assumed states."""
        return self._config_entry.options.get(CONF_USE_ASSUMED_STATE, True)

    @property
    def config_offline_is_off(self):
        """Interpret offline led's as off (global config)."""
        return self._config_entry.options.get(CONF_OFFLINE_IS_OFF, False)

    async def _async_update(self):
        """Fetch data."""
        self.logger.debug("_async_update")
        if "govee" not in self.hass.data:
            raise UpdateFailed("Govee instance not available")
        try:
            hub = self.hass.data[DOMAIN]["hub"]

            if not hub.online:
                # when offline, check connection, this will set hub.online
                await hub.check_connection()

            if hub.online:
                # set global options to library
                if self.config_offline_is_off:
                    hub.config_offline_is_off = True
                else:
                    hub.config_offline_is_off = None  # allow override in learning info

                # govee will change this to a single request in 2021
                device_states = await hub.get_states()
                for device in device_states:
                    if device.error:
                        self.logger.warning(
                            "update failed for %s: %s", device.device, device.error
                        )
                return device_states
        except GoveeError as ex:
            raise UpdateFailed(f"Exception on getting states: {ex}") from ex


class GoveeLightEntity(LightEntity):
    """Representation of a stateful light entity."""

    def __init__(
        self,
        hub: Govee,
        title: str,
        coordinator: GoveeDataUpdateCoordinator,
        device: GoveeDevice,
    ):
        """Init a Govee light strip."""
        self._hub = hub
        self._title = title
        self._coordinator = coordinator
        self._device = device

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

    @property
    def _state(self):
        """Lights internal state."""
        return self._device  # self._hub.state(self._device)

    @cached_property
    def supported_color_modes(self) -> set[ColorMode]:
        """Get supported color modes."""
        color_mode = set()
        if self._device.support_color:
            color_mode.add(ColorMode.HS)
        if self._device.support_color_tem:
            color_mode.add(ColorMode.COLOR_TEMP)
        if not color_mode:
            # brightness or on/off must be the only supported mode
            if self._device.support_brightness:
                color_mode.add(ColorMode.BRIGHTNESS)
            else:
                color_mode.add(ColorMode.ONOFF)
        return color_mode

    async def async_turn_on(self, **kwargs):
        """Turn device on."""
        _LOGGER.debug(
            "async_turn_on for Govee light %s, kwargs: %s", self._device.device, kwargs
        )
        err = None

        just_turn_on = True
        if ATTR_HS_COLOR in kwargs:
            hs_color = kwargs.pop(ATTR_HS_COLOR)
            just_turn_on = False
            col = color.color_hs_to_RGB(hs_color[0], hs_color[1])
            _, err = await self._hub.set_color(self._device, col)
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs.pop(ATTR_BRIGHTNESS)
            just_turn_on = False
            bright_set = brightness - 1
            _, err = await self._hub.set_brightness(self._device, bright_set)
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp = kwargs.pop(ATTR_COLOR_TEMP_KELVIN)
            just_turn_on = False
            if color_temp > COLOR_TEMP_KELVIN_MAX:
                color_temp = COLOR_TEMP_KELVIN_MAX
            elif color_temp < COLOR_TEMP_KELVIN_MIN:
                color_temp = COLOR_TEMP_KELVIN_MIN
            _, err = await self._hub.set_color_temp(self._device, color_temp)

        # if there is no known specific command - turn on
        if just_turn_on:
            _, err = await self._hub.turn_on(self._device)
        # debug log unknown commands
        if kwargs:
            _LOGGER.debug(
                "async_turn_on doesnt know how to handle kwargs: %s", repr(kwargs)
            )
        # warn on any error
        if err:
            _LOGGER.warning(
                "async_turn_on failed with '%s' for %s, kwargs: %s",
                err,
                self._device.device,
                kwargs,
            )

    async def async_turn_off(self, **kwargs):
        """Turn device off."""
        _LOGGER.debug("async_turn_off for Govee light %s", self._device.device)
        await self._hub.turn_off(self._device)

    @property
    def unique_id(self):
        """Return the unique ID."""
        return f"govee_{self._title}_{self._device.device}"

    @property
    def device_id(self):
        """Return the ID."""
        return self.unique_id

    @property
    def name(self):
        """Return the name."""
        return self._device.device_name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self.name,
            "manufacturer": "Govee",
            "model": self._device.model,
        }

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.power_state

    @property
    def assumed_state(self):
        """
        Return true if the state is assumed.

        This can be disabled in options.
        """
        return (
            self._coordinator.use_assumed_state
            and self._device.source == GoveeSource.HISTORY
        )

    @property
    def available(self):
        """Return if light is available."""
        return self._device.online

    @property
    def hs_color(self):
        """Return the hs color value."""
        return color.color_RGB_to_hs(
            self._device.color[0],
            self._device.color[1],
            self._device.color[2],
        )

    @property
    def rgb_color(self):
        """Return the rgb color value."""
        return [
            self._device.color[0],
            self._device.color[1],
            self._device.color[2],
        ]

    @property
    def brightness(self):
        """Return the brightness value."""
        # govee is reporting 0 to 254 - home assistant uses 1 to 255
        return self._device.brightness + 1

    @property
    def color_temp(self):
        """Return the color_temp of the light."""
        return self._device.color_temp

    @property
    def min_color_temp_kelvin(self):
        """Return the coldest color_temp that this light supports."""
        return COLOR_TEMP_KELVIN_MAX

    @property
    def max_color_temp_kelvin(self):
        """Return the warmest color_temp that this light supports."""
        return COLOR_TEMP_KELVIN_MIN

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return {
            # rate limiting information on Govee API
            "rate_limit_total": self._hub.rate_limit_total,
            "rate_limit_remaining": self._hub.rate_limit_remaining,
            "rate_limit_reset_seconds": round(self._hub.rate_limit_reset_seconds, 2),
            "rate_limit_reset": datetime.fromtimestamp(
                self._hub.rate_limit_reset
            ).isoformat(),
            "rate_limit_on": self._hub.rate_limit_on,
            # general information
            "manufacturer": "Govee",
            "model": self._device.model,
        }
