from collections.abc import Iterable
from typing import Any, Union

from . import AppriseAsset, ContentLocation
from .attachment import AttachBase

_Attachment = Union[str, AttachBase]
_Attachments = Iterable[_Attachment]

class AppriseAttachment:
    def __init__(
        self,
        paths: _Attachments | None = ...,
        asset: AppriseAttachment | None = ...,
        cache: bool = ...,
        location: ContentLocation | None = ...,
        **kwargs: Any,
    ) -> None: ...
    def add(
        self,
        attachments: _Attachments,
        asset: AppriseAttachment | None = ...,
        cache: bool | None = ...,
    ) -> bool: ...
    @staticmethod
    def instantiate(
        url: str,
        asset: AppriseAsset | None = ...,
        cache: bool | None = ...,
        suppress_exceptions: bool = ...,
    ) -> NotifyBase: ...
    def clear(self) -> None: ...
    def size(self) -> int: ...
    def pop(self, index: int = ...) -> AttachBase: ...
    def __getitem__(self, index: int) -> AttachBase: ...
    def __bool__(self) -> bool: ...
    def __iter__(self) -> Iterator[AttachBase]: ...
    def __len__(self) -> int: ...
