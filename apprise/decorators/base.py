# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import inspect

from .. import common
from ..logger import logger
from ..manager_plugins import NotificationManager
from ..plugins.base import NotifyBase
from ..utils.logic import dict_full_update
from ..utils.parse import URL_DETAILS_RE, parse_url, url_assembly

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()


class CustomNotifyPlugin(NotifyBase):
    """Apprise Custom Plugin Hook.

    This gets initialized based on @notify decorator definitions
    """

    # Our Custom notification
    service_url = "https://github.com/caronc/apprise/wiki/Custom_Notification"

    # Over-ride our category since this inheritance of the NotifyBase class
    # should be treated differently.
    category = "custom"

    # Support Attachments
    attachment_support = True

    # Allow persistent storage support
    storage_mode = common.PersistentStoreMode.AUTO

    # Define object templates
    templates = ("{schema}://",)

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns arguments retrieved."""
        return parse_url(url, verify_host=False, simple=True)

    def url(self, privacy=False, *args, **kwargs):
        """General URL assembly."""
        return f"{self.secure_protocol}://"

    @staticmethod
    def instantiate_plugin(url, send_func, name=None):
        """The function used to add a new notification plugin based on the
        schema parsed from the provided URL into our supported matrix
        structure."""

        if not isinstance(url, str):
            msg = (
                f"An invalid custom notify url/schema ({url}) provided in "
                f"function {send_func.__name__}."
            )
            logger.warning(msg)
            return None

        # Validate that our schema is okay
        re_match = URL_DETAILS_RE.match(url)
        if not re_match:
            msg = (
                f"An invalid custom notify url/schema ({url}) provided in "
                f"function {send_func.__name__}."
            )
            logger.warning(msg)
            return None

        # Acquire our schema
        schema = re_match.group("schema").lower()

        if not re_match.group("base"):
            url = f"{schema}://"

        # Keep a default set of arguments to apply to all called references
        base_args = parse_url(
            url, default_schema=schema, verify_host=False, simple=True
        )

        if schema in N_MGR:
            # we're already handling this object
            msg = (
                f"The schema ({url}) is already defined and could not be "
                f"loaded from custom notify function {send_func.__name__}."
            )
            logger.warning(msg)
            return None

        # We define our own custom wrapper class so that we can initialize
        # some key default configuration values allowing calls to our
        # `Apprise.details()` to correctly differentiate one custom plugin
        # that was loaded from another
        class CustomNotifyPluginWrapper(CustomNotifyPlugin):

            # Our Service Name
            service_name = (
                name
                if isinstance(name, str) and name
                else f"Custom - {schema}"
            )

            # Store our matched schema
            secure_protocol = schema

            requirements = {
                # Define our required packaging in order to work
                "details": f"Source: {inspect.getfile(send_func)}"
            }

            # Assign our send() function
            __send = staticmethod(send_func)

            # Update our default arguments
            _base_args = base_args

            def __init__(self, **kwargs):
                """Our initialization."""
                #  init parent
                super().__init__(**kwargs)

                self._default_args = {}

                # Some variables do not need to be set
                kwargs.pop("secure", None)

                # Apply our updates based on what was parsed
                dict_full_update(self._default_args, self._base_args)
                dict_full_update(self._default_args, kwargs)

                # Update our arguments (applying them to what we originally)
                # initialized as
                self._default_args["url"] = url_assembly(**self._default_args)

            def send(
                self,
                body,
                title="",
                notify_type=common.NotifyType.INFO,
                *args,
                **kwargs,
            ):
                """Our send() call which triggers our hook."""

                response = False
                try:
                    # Enforce a boolean response
                    result = self.__send(
                        body,
                        title,
                        notify_type.value,
                        *args,
                        meta=self._default_args,
                        **kwargs,
                    )

                    # None and True are both considered successful
                    # False however is passed along further upstream
                    response = True if result is None else bool(result)

                except Exception as e:
                    # Unhandled Exception
                    self.logger.warning(
                        "An exception occured sending a %s notification.",
                        N_MGR[self.secure_protocol].service_name,
                    )
                    self.logger.debug(
                        "%s Exception: %s", N_MGR[self.secure_protocol], str(e)
                    )
                    return False

                if response:
                    self.logger.info(
                        "Sent %s notification.",
                        N_MGR[self.secure_protocol].service_name,
                    )
                else:
                    self.logger.warning(
                        "Failed to send %s notification.",
                        N_MGR[self.secure_protocol].service_name,
                    )
                return response

        # Store our plugin into our core map file
        return N_MGR.add(
            plugin=CustomNotifyPluginWrapper,
            schemas=schema,
            send_func=send_func,
            url=url,
        )
