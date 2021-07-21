from typing import Any, Iterable, Optional, Union

from . import AppriseAsset, ContentLocation
from .attachment import AttachBase

_Attachment = Union[str, AttachBase]
_Attachments = Iterable[_Attachment]

class AppriseAttachment:
    def __init__(
        self,
        paths: Optional[_Attachments] = ...,
        asset: Optional[AppriseAttachment] = ...,
        cache: bool = ...,
        location: Optional[ContentLocation] = ...,
        **kwargs: Any
    ) -> None: ...
    def add(
        self,
        attachments: _Attachments,
        asset: Optional[AppriseAttachment] = ...,
        cache: Optional[bool] = ...
    ) -> bool: ...
    @staticmethod
    def instantiate(
        url: str,
        asset: Optional[AppriseAsset] = ...,
        cache: Optional[bool] = ...,
        suppress_exceptions: bool = ...
    ) -> NotifyBase: ...
    def clear(self) -> None: ...
    def size(self) -> int: ...
    def pop(self, index: int = ...) -> AttachBase: ...
    def __getitem__(self, index: int) -> AttachBase: ...
    def __bool__(self) -> bool: ...
    def __nonzero__(self) -> bool: ...
    def __iter__(self) -> Iterator[AttachBase]: ...
    def __len__(self) -> int: ...