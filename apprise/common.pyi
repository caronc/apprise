import types

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

NOTIFY_MODULE_MAP: dict[str, dict[str, type[NotifyBase] | types.ModuleType]]
