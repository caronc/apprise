import types
import typing as t


class NotifyType:
    INFO: NotifyType
    SUCCESS: NotifyType
    WARNING: NotifyType
    FAILURE: NotifyType

class NotifyFormat:
    TEXT: NotifyFormat
    HTML: NotifyFormat
    MARKDOWN: NotifyFormat

class ContentLocation:
    LOCAL: ContentLocation
    HOSTED: ContentLocation
    INACCESSIBLE: ContentLocation


NOTIFY_MODULE_MAP: t.Dict[str, t.Dict[str, t.Union[t.Type["NotifyBase"], types.ModuleType]]]
