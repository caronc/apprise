from __future__ import print_function

import six
import logging

from .error import TweepError
from .api import API
import requests
from requests_oauthlib import OAuth1Session, OAuth1
from requests.auth import AuthBase
from six.moves.urllib.parse import parse_qs

WARNING_MESSAGE = """Warning! Due to a Twitter API bug, signin_with_twitter
and access_type don't always play nice together. Details
https://dev.twitter.com/discussions/21281"""


class AuthHandler(object):

    def apply_auth(self, url, method, headers, parameters):
        """Apply authentication headers to request"""
        raise NotImplementedError

    def get_username(self):
        """Return the username of the authenticated user"""
        raise NotImplementedError


class OAuthHandler(AuthHandler):
    """OAuth authentication handler"""
    OAUTH_HOST = 'api.twitter.com'
    OAUTH_ROOT = '/oauth/'

    def __init__(self, consumer_key, consumer_secret, callback=None):
        if type(consumer_key) == six.text_type:
            consumer_key = consumer_key.encode('ascii')

        if type(consumer_secret) == six.text_type:
            consumer_secret = consumer_secret.encode('ascii')

        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.access_token = None
        self.access_token_secret = None
        self.callback = callback
        self.username = None
        self.oauth = OAuth1Session(consumer_key,
                                   client_secret=consumer_secret,
                                   callback_uri=self.callback)

    def _get_oauth_url(self, endpoint):
        return 'https://' + self.OAUTH_HOST + self.OAUTH_ROOT + endpoint

    def apply_auth(self):
        return OAuth1(self.consumer_key,
                      client_secret=self.consumer_secret,
                      resource_owner_key=self.access_token,
                      resource_owner_secret=self.access_token_secret,
                      decoding=None)

    def _get_request_token(self, access_type=None):
        try:
            url = self._get_oauth_url('request_token')
            if access_type:
                url += '?x_auth_access_type=%s' % access_type
            return self.oauth.fetch_request_token(url)
        except Exception as e:
            raise TweepError(e)

    def set_access_token(self, key, secret):
        self.access_token = key
        self.access_token_secret = secret

    def get_authorization_url(self,
                              signin_with_twitter=False,
                              access_type=None):
        """Get the authorization URL to redirect the user"""
        try:
            if signin_with_twitter:
                url = self._get_oauth_url('authenticate')
                if access_type:
                    logging.warning(WARNING_MESSAGE)
            else:
                url = self._get_oauth_url('authorize')
            self.request_token = self._get_request_token(access_type=access_type)
            return self.oauth.authorization_url(url)
        except Exception as e:
            raise TweepError(e)

    def get_access_token(self, verifier=None):
        """
        After user has authorized the request token, get access token
        with user supplied verifier.
        """
        try:
            url = self._get_oauth_url('access_token')
            self.oauth = OAuth1Session(self.consumer_key,
                                       client_secret=self.consumer_secret,
                                       resource_owner_key=self.request_token['oauth_token'],
                                       resource_owner_secret=self.request_token['oauth_token_secret'],
                                       verifier=verifier, callback_uri=self.callback)
            resp = self.oauth.fetch_access_token(url)
            self.access_token = resp['oauth_token']
            self.access_token_secret = resp['oauth_token_secret']
            return self.access_token, self.access_token_secret
        except Exception as e:
            raise TweepError(e)

    def get_xauth_access_token(self, username, password):
        """
        Get an access token from an username and password combination.
        In order to get this working you need to create an app at
        http://twitter.com/apps, after that send a mail to api@twitter.com
        and request activation of xAuth for it.
        """
        try:
            url = self._get_oauth_url('access_token')
            oauth = OAuth1(self.consumer_key,
                           client_secret=self.consumer_secret)
            r = requests.post(url=url,
                              auth=oauth,
                              headers={'x_auth_mode': 'client_auth',
                                       'x_auth_username': username,
                                       'x_auth_password': password})

            credentials = parse_qs(r.content)
            return credentials.get('oauth_token')[0], credentials.get('oauth_token_secret')[0]
        except Exception as e:
            raise TweepError(e)

    def get_username(self):
        if self.username is None:
            api = API(self)
            user = api.verify_credentials()
            if user:
                self.username = user.screen_name
            else:
                raise TweepError('Unable to get username,'
                                 ' invalid oauth token!')
        return self.username


class OAuth2Bearer(AuthBase):
    def __init__(self, bearer_token):
        self.bearer_token = bearer_token

    def __call__(self, request):
        request.headers['Authorization'] = 'Bearer ' + self.bearer_token
        return request


class AppAuthHandler(AuthHandler):
    """Application-only authentication handler"""

    OAUTH_HOST = 'api.twitter.com'
    OAUTH_ROOT = '/oauth2/'

    def __init__(self, consumer_key, consumer_secret):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self._bearer_token = ''

        resp = requests.post(self._get_oauth_url('token'),
                             auth=(self.consumer_key,
                                   self.consumer_secret),
                             data={'grant_type': 'client_credentials'})
        data = resp.json()
        if data.get('token_type') != 'bearer':
            raise TweepError('Expected token_type to equal "bearer", '
                             'but got %s instead' % data.get('token_type'))

        self._bearer_token = data['access_token']

    def _get_oauth_url(self, endpoint):
        return 'https://' + self.OAUTH_HOST + self.OAUTH_ROOT + endpoint

    def apply_auth(self):
        return OAuth2Bearer(self._bearer_token)
