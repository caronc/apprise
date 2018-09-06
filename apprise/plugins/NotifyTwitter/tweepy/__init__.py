# Tweepy
# Copyright 2009-2010 Joshua Roesslein
# See LICENSE for details.

"""
Tweepy Twitter API library
"""
__version__ = '3.6.0'
__author__ = 'Joshua Roesslein'
__license__ = 'MIT'

from .models import Status, User, DirectMessage, Friendship, SavedSearch, SearchResults, ModelFactory, Category
from .error import TweepError, RateLimitError
from .api import API
from .cache import Cache, MemoryCache, FileCache
from .auth import OAuthHandler, AppAuthHandler
from .streaming import Stream, StreamListener
from .cursor import Cursor

# Global, unauthenticated instance of API
api = API()

def debug(enable=True, level=1):
    from six.moves.http_client import HTTPConnection
    HTTPConnection.debuglevel = level
