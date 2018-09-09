# -*- coding: utf-8 -*-

import re
import sys
from decorator import decorator
from .errors import AccessError

# Help class(...es? Nah. Just singular for now.)

class NoNoneDict(dict):
    """A dict that ignores values that are None. Not completely API-compatible
    with dict, but contains all that's needed.
    """
    def __repr__(self):
        return "NoNoneDict({dict})".format(dict=dict.__repr__(self))
    
    def __init__(self, initial={}):
        self.update(initial)

    def __setitem__(self, key, value):
        if value is not None:
            dict.__setitem__(self, key, value)
    
    def update(self, data):
        for key, value in data.items():
            self[key] = value

# Decorators / factories

@decorator
def requires_secret_key(func, self, *args, **kwargs):
    """Raise an error if the method is called without a secret key."""
    if self.secret_key is None:
        raise AccessError("The Service doesn't have a secret "
            "key provided, and therefore lacks write permission.")
    return func(self, *args, **kwargs)

def with_api_bound(cls, api):
    new_cls = type(cls.__name__, (cls,), {
        '_api': api,
        '__doc__': (
            "Create a :class:`~pushjet.{name}` bound to the API. "
            "See :class:`pushjet.{name}` for documentation."
        ).format(name=cls.__name__)
    })
    return new_cls

# Helper functions

UUID_RE = re.compile(r'^[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}$')
PUBLIC_KEY_RE = re.compile(r'^[A-Za-z0-9]{4}-[A-Za-z0-9]{6}-[A-Za-z0-9]{12}-[A-Za-z0-9]{5}-[A-Za-z0-9]{9}$')
SECRET_KEY_RE = re.compile(r'^[A-Za-z0-9]{32}$')

is_valid_uuid = lambda s: UUID_RE.match(s) is not None
is_valid_public_key = lambda s: PUBLIC_KEY_RE.match(s) is not None
is_valid_secret_key = lambda s: SECRET_KEY_RE.match(s) is not None

def repr_format(s):
    s = s.replace('\n', ' ').replace('\r', '')
    original_length = len(s)
    s = s[:30]
    s += '...' if len(s) != original_length else ''
    s = s.encode(sys.stdout.encoding, errors='replace')
    return s
