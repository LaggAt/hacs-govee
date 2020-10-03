from abc import abstractmethod
from dataclasses import dataclass
import logging
from typing import Dict, Optional, Any

_LOGGER = logging.getLogger(__name__)

@dataclass
class GoveeLearnedInfo:
    set_brightness_max: Optional[int] = None
    get_brightness_max: Optional[int] = None

class GoveeAbstractLearningStorage(object):
    """Abstract class used for loading and storing of learning information."""

    def __init__(self):
        self._learned_info = {}
        self._is_cached = False

    async def _read_cached(self) -> Dict[str, GoveeLearnedInfo]:
        """Do not override, this will cache the current state."""
        if not self._is_cached:
            # read into cache once
            self._learned_info = await self.read()
            self._is_cached = True
        return self._learned_info

    async def _write_cached(self, learned_info: Dict[str, GoveeLearnedInfo]):
        """Do not override, uses the write() to save learned information."""
        self._learned_info = learned_info
        self._is_cached = True
        await self.write(self._learned_info)

    @abstractmethod
    async def read(self) -> Dict[str, GoveeLearnedInfo]:
        """Read the learning information."""
        _LOGGER.warning("Implement GoveeAbstractLearningStorage and overwrite write/read methods to persist and restore learned lamp properties.")
        return {}

    @abstractmethod
    async def write(self, learned_info: Dict[str, GoveeLearnedInfo]):
        """Write updated learning information."""
        _LOGGER.warning("Implement GoveeAbstractLearningStorage and overwrite write/read methods to persist and restore learned lamp properties.")