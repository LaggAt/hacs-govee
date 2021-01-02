"""Config flow for Govee LED strips integration."""

import logging

from govee_api_laggat import Govee

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_API_KEY, CONF_DELAY
from homeassistant.core import callback
import voluptuous as vol

from .const import DOMAIN, CONF_USE_ASSUMED_STATE, CONF_OFFLINE_IS_OFF

_LOGGER = logging.getLogger(__name__)

async def validate_input(hass: core.HomeAssistant, user_input):
    """.
    """
    return user_input

async def validate_api_key(hass: core.HomeAssistant, user_input):
    """Validate the user input allows us to connect.

    Return info that you want to store in the config entry.
    """
    api_key = user_input[CONF_API_KEY]
    async with Govee(api_key) as hub:
        _, error = await hub.get_devices()
        if error:
            raise CannotConnect(error)

    # Return info that you want to store in the config entry.
    return user_input


@config_entries.HANDLERS.register(DOMAIN)
class GoveeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee LED strips."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                user_input = await validate_api_key(self.hass, user_input)

                return self.async_create_entry(title=DOMAIN, data=user_input)
            except CannotConnect as conn_ex:
                _LOGGER.exception("Cannot connect: %s", conn_ex)
                errors["base"] = "cannot_connect"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", ex)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(CONF_DELAY, default=10): int,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow."""
        return GoveeOptionsFlowHandler(config_entry)


class GoveeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    VERSION = 1

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Manage the options."""
        # get the current value for API key for comparison and default value
        old_api_key = self.config_entry.options.get(
            CONF_API_KEY, self.config_entry.data.get(CONF_API_KEY, "")
        )

        errors = {}
        if user_input is not None:
            # check if API Key changed and is valid
            try:
                api_key = user_input[CONF_API_KEY]
                if old_api_key != api_key:
                    user_input = await validate_api_key(self.hass, user_input)

                # update options flow values
                self.options.update(user_input)
                return await self._update_options()
                # for later - extend with options you don't want in config but option flow
                # return await self.async_step_options_2()
            except CannotConnect as conn_ex:
                _LOGGER.exception("Cannot connect: %s", conn_ex)
                errors["base"] = "cannot_connect"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", ex)
                errors["base"] = "unknown"

        options_schema = vol.Schema(
            {
                # to config flow
                vol.Required(
                    CONF_API_KEY,
                    default=old_api_key,
                ): str,
                vol.Optional(
                    CONF_DELAY,
                    default=self.config_entry.options.get(
                        CONF_DELAY, self.config_entry.data.get(CONF_DELAY, 10)
                    ),
                ): int,
                # to options flow
                vol.Required(
                    CONF_USE_ASSUMED_STATE,
                    default=self.config_entry.options.get(CONF_USE_ASSUMED_STATE, True),
                ): bool,
                vol.Required(
                    CONF_OFFLINE_IS_OFF,
                    default=self.config_entry.options.get(CONF_OFFLINE_IS_OFF, False),
                ): bool,
            },
        )

        return self.async_show_form(
            step_id="user",
            data_schema=options_schema,
            errors=errors,
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(title=DOMAIN, data=self.options)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
