# This module is intentionally kept minimal,
# so that it can be imported without triggering imports outside stdlib.
import io
import sys
from urllib.request import urlopen

if sys.platform == "emscripten" and "pyodide" in sys.modules:
    from pyodide.http import open_url
else:

    def open_url(url: str) -> io.StringIO:
        if not url.startswith(("http:", "https:")):
            raise ValueError("URL must start with 'http:' or 'https:'")
        with urlopen(url) as response:  # noqa: S310
            return io.StringIO(response.read().decode("utf-8"))
