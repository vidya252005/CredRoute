"""Explicit provider failures. Programming bugs must not be treated as lender errors."""


class ProviderError(Exception):
    """Base class for adapter/provider failures."""


class ProviderTimeout(ProviderError, TimeoutError):
    pass


class ProviderUnavailable(ProviderError):
    pass


class ProviderRateLimited(ProviderError):
    pass


class ProviderProtocolError(ProviderError):
    pass
