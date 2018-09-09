# -*- coding: utf-8 -*-


from requests import RequestException

import sys
if sys.version_info[0] < 3:
    # This is built into Python 3.
    class ConnectionError(Exception):
        pass

class PushjetError(Exception):
    """All the errors inherit from this. Therefore, ``except PushjetError`` catches all errors."""

class AccessError(PushjetError):
    """Raised when a secret key is missing for a service method that needs one."""

class NonexistentError(PushjetError):
    """Raised when an attempt to access a nonexistent service is made."""

class SubscriptionError(PushjetError):
    """Raised when an attempt to subscribe to a service that's already subscribed to,
    or to unsubscribe from a service that isn't subscribed to, is made."""

class RequestError(PushjetError, ConnectionError):
    """Raised if something goes wrong in the connection to the API server.
    Inherits from ``ConnectionError`` on Python 3, and can therefore be caught
    with ``except ConnectionError`` there.
    
    :ivar requests_exception: The underlying `requests <http://docs.python-requests.org>`__
        exception. Access this if you want to handle different HTTP request errors in different ways.
    """

    def __str__(self):
        return "requests.{error}: {description}".format(
            error=self.requests_exception.__class__.__name__,
            description=str(self.requests_exception)
        )

    def __init__(self, requests_exception):
        self.requests_exception = requests_exception

class ServerError(PushjetError):
    """Raised if the API server has an error while processing your request.
    This getting raised means there's a bug in the server! If you manage to
    track down what caused it, you can `open an issue on Pushjet's GitHub page 
    <https://github.com/Pushjet/Pushjet-Server-Api/issues>`__.
    """
