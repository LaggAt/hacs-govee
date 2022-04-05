"""Govee errors."""


class GoveeError(Exception):
    """Base Exception thrown from govee_api_laggat."""


class GoveeDeviceNotFound(GoveeError):
    """Device is unknown."""
