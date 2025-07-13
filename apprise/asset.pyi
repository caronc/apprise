from . import NotifyFormat, NotifyType

class AppriseAsset:
    app_id: str
    app_desc: str
    app_url: str
    html_notify_map: dict[NotifyType, str]
    default_html_color: str
    default_extension: str
    theme: str | None
    image_url_mask: str
    image_url_logo: str
    image_path_mask: str | None
    body_format: NotifyFormat | None
    async_mode: bool
    interpret_escapes: bool
    def __init__(
        self,
        app_id: str = ...,
        app_desc: str = ...,
        app_url: str = ...,
        html_notify_map: dict[NotifyType, str] = ...,
        default_html_color: str = ...,
        default_extension: str = ...,
        theme: str | None = ...,
        image_url_mask: str = ...,
        image_url_logo: str = ...,
        image_path_mask: str | None = ...,
        body_format: NotifyFormat | None = ...,
        async_mode: bool = ...,
        interpret_escapes: bool = ...,
    ) -> None: ...
