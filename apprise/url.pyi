from logging import logger
from typing import Any, Iterable, Set, Optional

class URLBase:
    service_name: Optional[str]
    protocol: Optional[str]
    secure_protocol: Optional[str]
    request_rate_per_sec: int
    socket_connect_timeout: float
    socket_read_timeout: float
    tags: Set[str]
    verify_certificate: bool
    logger: logger
    def url(self, privacy: bool = ..., *args: Any, **kwargs: Any) -> str: ...
    def __contains__(self, tags: Iterable[str]) -> bool: ...
    def __str__(self) -> str: ...