import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

#
class GoveeBle(object):
    """Govee BLE client."""

    async def __aenter__(self):
        """Async context manager enter."""
        return self

    async def __aexit__(self, *err):
        """Async context manager exit."""
        pass

    def __init__(
        self,
        govee,
    ):
        """Init with an API_KEY and storage for learned values."""
        self._govee = govee

    @classmethod
    async def create(
        cls,
        govee,
    ):
        """Use create method if you want to use this Client without an async context manager."""
        self = GoveeBle(govee)
        await self.__aenter__()
        return self

    async def close(self):
        """Use close when your are finished with the Client without using an async context manager."""
        await self.__aexit__()
