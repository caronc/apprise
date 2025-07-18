from collections.abc import Iterable, Iterator
from typing import Any

from . import (
    AppriseAsset,
    AppriseAttachment,
    AppriseConfig,
    ConfigBase,
    NotifyBase,
    NotifyFormat,
    NotifyType,
)
from .common import ContentLocation

_Server = Union[str, ConfigBase, NotifyBase, AppriseConfig]
_Servers = Union[_Server, dict[Any, _Server], Iterable[_Server]]
# Can't define this recursively as mypy doesn't support recursive types:
# https://github.com/python/mypy/issues/731
_Tag = Union[str, Iterable[Union[str, Iterable[str]]]]

class Apprise:
    def __init__(
        self,
        servers: _Servers = ...,
        asset: AppriseAsset | None = ...,
        location: ContentLocation | None = ...,
        debug: bool = ...,
    ) -> None: ...
    @staticmethod
    def instantiate(
        url: Union[str, dict[str, NotifyBase]],
        asset: AppriseAsset | None = ...,
        tag: _Tag | None = ...,
        suppress_exceptions: bool = ...,
    ) -> NotifyBase: ...
    def add(
        self,
        servers: _Servers = ...,
        asset: AppriseAsset | None = ...,
        tag: _Tag | None = ...,
    ) -> bool: ...
    def clear(self) -> None: ...
    def find(self, tag: str = ...) -> Iterator[Apprise]: ...
    def notify(
        self,
        body: str,
        title: str = ...,
        notify_type: NotifyType = ...,
        body_format: NotifyFormat = ...,
        tag: _Tag = ...,
        attach: AppriseAttachment | None = ...,
        interpret_escapes: bool | None = ...,
    ) -> bool: ...
    async def async_notify(
        self,
        body: str,
        title: str = ...,
        notify_type: NotifyType = ...,
        body_format: NotifyFormat = ...,
        tag: _Tag = ...,
        attach: AppriseAttachment | None = ...,
        interpret_escapes: bool | None = ...,
    ) -> bool: ...
    def details(self, lang: str | None = ...) -> dict[str, Any]: ...
    def urls(self, privacy: bool = ...) -> Iterable[str]: ...
    def pop(self, index: int) -> ConfigBase: ...
    def __getitem__(self, index: int) -> ConfigBase: ...
    def __bool__(self) -> bool: ...
    def __iter__(self) -> Iterator[ConfigBase]: ...
    def __len__(self) -> int: ...
