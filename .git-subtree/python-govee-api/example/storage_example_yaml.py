"""Example YAML storage in user's home."""

import argparse
import asyncio
import logging
import os
from typing import Dict

import bios
import dacite
from dataclasses import asdict
from govee_api_laggat import Govee, GoveeAbstractLearningStorage, GoveeLearnedInfo

_LOGGER = logging.getLogger(__name__)


class YamlLearningStorage(GoveeAbstractLearningStorage):
    """Storage for govee_api_laggat to Save/Restore learned informations for lamps."""

    def __init__(self, *args, **kwargs):
        """If you override __init__, call super."""
        self._filename = os.path.expanduser("~/.govee_learning.yaml")
        super().__init__(*args, **kwargs)

    async def read(self) -> Dict[str, GoveeLearnedInfo]:
        """get the last saved learning information from disk, database, ... and return it."""
        learned_info = {}
        try:
            device_dict = bios.read(self._filename)
            learned_info = {
                dacite.from_dict(
                    data_class=GoveeLearnedInfo, data=device_dict[device_str]
                )
                for device_str in device_dict
            }
            _LOGGER.info(
                "Loaded learning information from %s.",
                self._filename,
            )
        except Exception as ex:
            _LOGGER.warning(
                "Unable to load goove learned config from %s: %s. This is normal on first use.",
                self._filename,
                ex,
            )
        return learned_info

    async def write(self, learned_info: Dict[str, GoveeLearnedInfo]):
        """Save this dictionary to disk."""
        leaned_dict = {device: asdict(learned_info[device]) for device in learned_info}
        bios.write(self._filename, leaned_dict)
        _LOGGER.info(
            "Stored learning information to %s.",
            self._filename,
        )


if __name__ == "__main__":
    """Test this out."""
    parser = argparse.ArgumentParser(description="govee_api_laggat examples")
    parser.add_argument("--api-key", dest="api_key", type=str, required=True)
    args = parser.parse_args()

    async def some_light_commands(api_key: str, storage: GoveeAbstractLearningStorage):
        """We get the device list, set them to max brightness, sleep, get device state."""
        async with Govee(api_key, learning_storage=storage) as govee:
            devices, err = await govee.get_devices()

            # once setting the state > 100 we learn if we need to set in the range of 0-254 or 0-100
            for device in devices:
                success, err = await govee.set_brightness(device, 254)

            # we sleep to get a live status - client is blocking immediate status request after control
            # because they return invalid values. A calculated state is available before that.
            await asyncio.sleep(5)

            # once getting state we guess how to interpret the result.
            # if brightness reaches >100 one time we know we are in range of 0-254 instead of 0-100
            # some devices do not support state, in this case every state is calculated from known values
            await govee.get_states()
            print(f"See {storage._filename} for leaned configuration.")

    # going async ...
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            some_light_commands(args.api_key, YamlLearningStorage())
        )
    finally:
        loop.close()
