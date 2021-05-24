"""Config flow for Govee integration."""

import logging

from govee_api_laggat import Govee, GoveeNoLearningStorage
from govee_api_laggat.govee_api_laggat import GoveeError

from homeassistant import config_entries, core, exceptions
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_API_KEY, CONF_DELAY
from homeassistant.core import callback
import voluptuous as vol
from typing import Any

from .const import (
    CONF_DISABLE_ATTRIBUTE_UPDATES,
    CONF_OFFLINE_IS_OFF,
    CONF_USE_ASSUMED_STATE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def validate_api_key(hass: core.HomeAssistant, user_input):
    """Validate the user input allows us to connect.

    Return info that you want to store in the config entry.
    """
    api_key = user_input[CONF_API_KEY]
    async with Govee(api_key, learning_storage=GoveeNoLearningStorage()) as hub:
        _, error = await hub.get_devices()
        if error:
            raise CannotConnect(error)

    # Return info that you want to store in the config entry.
    return user_input


async def validate_disabled_attribute_updates(hass: core.HomeAssistant, user_input):
    """Validate format of the ignore_device_attributes parameter string

    Return info that you want to store in the config entry.
    """
    disable_str = user_input[CONF_DISABLE_ATTRIBUTE_UPDATES]
    if disable_str:
        # we have something to check, connect without API key
        async with Govee("", learning_storage=GoveeNoLearningStorage()) as hub:
            # this will throw an GoveeError if something fails
            hub.ignore_device_attributes(disable_str)

    # Return info that you want to store in the config entry.
    return user_input


@config_entries.HANDLERS.register(DOMAIN)
class GoveeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                user_input = await validate_api_key(self.hass, user_input)

            except CannotConnect as conn_ex:
                _LOGGER.exception("Cannot connect: %s", conn_ex)
                errors[CONF_API_KEY] = "cannot_connect"
            except GoveeError as govee_ex:
                _LOGGER.exception("Govee library error: %s", govee_ex)
                errors["base"] = "govee_ex"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", ex)
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(title=DOMAIN, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): cv.string,
                    vol.Optional(CONF_DELAY, default=10): cv.positive_int,
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

            except CannotConnect as conn_ex:
                _LOGGER.exception("Cannot connect: %s", conn_ex)
                errors[CONF_API_KEY] = "cannot_connect"
            except GoveeError as govee_ex:
                _LOGGER.exception("Govee library error: %s", govee_ex)
                errors["base"] = "govee_ex"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", ex)
                errors["base"] = "unknown"

            # check validate_disabled_attribute_updates
            try:
                user_input = await validate_disabled_attribute_updates(
                    self.hass, user_input
                )

                # apply settings to the running instance
                if DOMAIN in self.hass.data and "hub" in self.hass.data[DOMAIN]:
                    hub = self.hass.data[DOMAIN]["hub"]
                    if hub:
                        disable_str = user_input[CONF_DISABLE_ATTRIBUTE_UPDATES]
                        hub.ignore_device_attributes(disable_str)
            except GoveeError as govee_ex:
                _LOGGER.exception(
                    "Wrong input format for validate_disabled_attribute_updates: %s",
                    govee_ex,
                )
                errors[
                    CONF_DISABLE_ATTRIBUTE_UPDATES
                ] = "disabled_attribute_updates_wrong"

            if not errors:
                # update options flow values
                self.options.update(user_input)
                return await self._update_options()
                # for later - extend with options you don't want in config but option flow
                # return await self.async_step_options_2()

        options_schema = vol.Schema(
            {
                # to config flow
                vol.Required(
                    CONF_API_KEY,
                    default=old_api_key,
                ): cv.string,
                vol.Optional(
                    CONF_DELAY,
                    default=self.config_entry.options.get(
                        CONF_DELAY, self.config_entry.data.get(CONF_DELAY, 10)
                    ),
                ): cv.positive_int,
                # to options flow
                vol.Required(
                    CONF_USE_ASSUMED_STATE,
                    default=self.config_entry.options.get(CONF_USE_ASSUMED_STATE, True),
                ): cv.boolean,
                vol.Required(
                    CONF_OFFLINE_IS_OFF,
                    default=self.config_entry.options.get(CONF_OFFLINE_IS_OFF, False),
                ): cv.boolean,
                # TODO: validator doesn't work, change to list?
                vol.Optional(
                    CONF_DISABLE_ATTRIBUTE_UPDATES,
                    default=self.config_entry.options.get(
                        CONF_DISABLE_ATTRIBUTE_UPDATES, ""
                    ),
                ): cv.string,
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
