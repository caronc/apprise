from collections.abc import Iterable
from logging import logger
from typing import Any

class URLBase:
    service_name: str | None
    protocol: str | None
    secure_protocol: str | None
    request_rate_per_sec: int
    socket_connect_timeout: float
    socket_read_timeout: float
    tags: set[str]
    verify_certificate: bool
    logger: logger
    def url(self, privacy: bool = ..., *args: Any, **kwargs: Any) -> str: ...
    def __contains__(self, tags: Iterable[str]) -> bool: ...
    def __str__(self) -> str: ...
