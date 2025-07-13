from collections.abc import Iterable, Iterator
from typing import Any, Union

from . import AppriseAsset, NotifyBase
from .config import ConfigBase

_Configs = Union[ConfigBase, str, Iterable[str]]

class AppriseConfig:
    def __init__(
        self,
        paths: _Configs | None = ...,
        asset: AppriseAsset | None = ...,
        cache: bool = ...,
        recursion: int = ...,
        insecure_includes: bool = ...,
        **kwargs: Any,
    ) -> None: ...
    def add(
        self,
        configs: _Configs,
        asset: AppriseAsset | None = ...,
        cache: bool = ...,
        recursion: bool | None = ...,
        insecure_includes: bool | None = ...,
    ) -> bool: ...
    def add_config(
        self,
        content: str,
        asset: AppriseAsset | None = ...,
        tag: str | None = ...,
        format: str | None = ...,
        recursion: int | None = ...,
        insecure_includes: bool | None = ...,
    ) -> bool: ...
    def servers(
        self, tag: str = ..., *args: Any, **kwargs: Any
    ) -> list[ConfigBase]: ...
    def instantiate(
        url: str,
        asset: AppriseAsset | None = ...,
        tag: str | None = ...,
        cache: bool | None = ...,
    ) -> NotifyBase: ...
    def clear(self) -> None: ...
    def server_pop(self, index: int) -> ConfigBase: ...
    def pop(self, index: int = ...) -> ConfigBase: ...
    def __getitem__(self, index: int) -> ConfigBase: ...
    def __bool__(self) -> bool: ...
    def __iter__(self) -> Iterator[ConfigBase]: ...
    def __len__(self) -> int: ...
