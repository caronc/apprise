from typing import Dict, Optional

from . import NotifyFormat, NotifyType

class AppriseAsset:
    app_id: str
    app_desc: str
    app_url: str
    html_notify_map: Dict[NotifyType, str]
    default_html_color: str
    default_extension: str
    theme: Optional[str]
    image_url_mask: str
    image_url_logo: str
    image_path_mask: Optional[str]
    body_format: Optional[NotifyFormat]
    async_mode: bool
    interpret_escapes: bool
    def __init__(
        self,
        app_id: str = ...,
        app_desc: str = ...,
        app_url: str = ...,
        html_notify_map: Dict[NotifyType, str] = ...,
        default_html_color: str = ...,
        default_extension: str = ...,
        theme: Optional[str] = ...,
        image_url_mask: str = ...,
        image_url_logo: str = ...,
        image_path_mask: Optional[str] = ...,
        body_format: Optional[NotifyFormat] = ...,
        async_mode: bool = ...,
        interpret_escapes: bool = ...
    ) -> None: ...