"""Govee platform."""

from datetime import timedelta, datetime
import logging
from typing import Optional

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

    update_interval = timedelta(
        seconds=options.get(CONF_DELAY, config.get(CONF_DELAY, 10))
    )
    coordinator = GoveeDataUpdateCoordinator(
        hass, _LOGGER, update_interval=update_interval, config_entry=entry
    )
    
    hub.events.new_device += lambda device: add_entity(
        async_add_entities, hub, entry, coordinator, device
    )
    await coordinator.async_refresh()

    for device in hub.devices:
        add_entity(async_add_entities, hub, entry, coordinator, device)


def add_entity(async_add_entities, hub, entry, coordinator, device):
    """Add Govee entities, splitting dual plugs into two independent socket entities."""
    if device.model == "H5082":
        async_add_entities(
            [
                GoveeLightEntity(hub, entry.title, coordinator, device, socket=1),
                GoveeLightEntity(hub, entry.title, coordinator, device, socket=2),
            ],
            update_before_add=False,
        )
    else:
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
                await hub.check_connection()

            if hub.online:
                if self.config_offline_is_off:
                    hub.config_offline_is_off = True
                else:
                    hub.config_offline_is_off = None

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
    """Representation of a stateful light or socket entity."""

    def __init__(
        self,
        hub: Govee,
        title: str,
        coordinator: GoveeDataUpdateCoordinator,
        device: GoveeDevice,
        socket: Optional[int] = None,
    ):
        """Init a Govee light strip or socket entity."""
        self._hub = hub
        self._title = title
        self._coordinator = coordinator
        self._device = device
        self._socket = socket
        # Local optimistic state tracking for split sockets
        self._assumed_socket_state = False  

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
        return self._device

    @cached_property
    def supported_color_modes(self) -> set[ColorMode]:
        """Get supported color modes."""
        color_mode = set()
        if self._device.support_color:
            color_mode.add(ColorMode.HS)
        if self._device.support_color_tem:
            color_mode.add(ColorMode.COLOR_TEMP)
        if not color_mode:
            if self._device.support_brightness:
                color_mode.add(ColorMode.BRIGHTNESS)
            else:
                color_mode.add(ColorMode.ONOFF)
        return color_mode
        
    @property
    def color_mode(self):
        """Return the active color mode."""
        if self._device.support_color:
            return ColorMode.HS
        if self._device.support_color_tem:
            return ColorMode.COLOR_TEMP
        if self._device.support_brightness:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    async def async_turn_on(self, **kwargs):
        """Turn device on optimistically."""
        _LOGGER.debug(
            "async_turn_on for Govee entity %s (socket: %s)",
            self._device.device,
            self._socket,
        )
        err = None

        if self._socket is not None:
            _, err = await self._hub.turn_on(self._device, socket=self._socket)
            if not err:
                self._assumed_socket_state = True
        else:
            _, err = await self._hub.turn_on(self._device)

        if err:
            _LOGGER.warning(
                "async_turn_on failed with '%s' for %s", err, self._device.device
            )
            
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn device off optimistically."""
        _LOGGER.debug(
            "async_turn_off for Govee entity %s (socket: %s)",
            self._device.device,
            self._socket,
        )
        if self._socket is not None:
            await self._hub.turn_off(self._device, socket=self._socket)
            self._assumed_socket_state = False
        else:
            await self._hub.turn_off(self._device)
        
        self.async_write_ha_state()

    @property
    def unique_id(self):
        """Return the unique ID."""
        if self._socket is not None:
            return f"govee_{self._title}_{self._device.device}_socket_{self._socket}"
        return f"govee_{self._title}_{self._device.device}"

    @property
    def device_id(self):
        """Return the ID."""
        return self.unique_id

    @property
    def name(self):
        """Return the name with socket suffix."""
        if self._socket is not None:
            return f"{self._device.device_name} Outlet {self._socket}"
        return self._device.device_name

    @property
    def device_info(self):
        """Group both outlets under a single physical device."""
        return {
            "identifiers": {(DOMAIN, f"govee_{self._title}_{self._device.device}")},
            "name": self._device.device_name,
            "manufacturer": "Govee",
            "model": self._device.model,
        }

    @property
    def is_on(self):
        """Return true if device is on using optimistic tracking."""
        if self._socket is not None:
            return self._assumed_socket_state
        return self._device.power_state

    @property
    def assumed_state(self):
        """Return true since state is optimistically assumed."""
        return self._socket is not None or (
            self._coordinator.use_assumed_state
            and self._device.source == GoveeSource.HISTORY
        )

    @property
    def available(self):
        """Return if device is available."""
        return self._device.online

    @property
    def hs_color(self):
        return color.color_RGB_to_hs(*self._device.color)

    @property
    def rgb_color(self):
        return list(self._device.color)

    @property
    def brightness(self):
        return self._device.brightness + 1

    @property
    def color_temp(self):
        return self._device.color_temp

    @property
    def min_color_temp_kelvin(self):
        return COLOR_TEMP_KELVIN_MAX

    @property
    def max_color_temp_kelvin(self):
        return COLOR_TEMP_KELVIN_MIN

    @property
    def extra_state_attributes(self):
        return {
            "manufacturer": "Govee",
            "model": self._device.model,
            "socket": self._socket,
        }
