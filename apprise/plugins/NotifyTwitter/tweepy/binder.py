# Tweepy
# Copyright 2009-2010 Joshua Roesslein
# See LICENSE for details.

from __future__ import print_function

import time
import re

from six.moves.urllib.parse import quote, urlencode
import requests

import logging

from .error import TweepError, RateLimitError, is_rate_limit_error_message
from .utils import convert_to_utf8_str
from .models import Model
import six
import sys


re_path_template = re.compile(r'{\w+}')

log = logging.getLogger('tweepy.binder')

def bind_api(**config):

    class APIMethod(object):

        api = config['api']
        path = config['path']
        payload_type = config.get('payload_type', None)
        payload_list = config.get('payload_list', False)
        allowed_param = config.get('allowed_param', [])
        method = config.get('method', 'GET')
        require_auth = config.get('require_auth', False)
        search_api = config.get('search_api', False)
        upload_api = config.get('upload_api', False)
        use_cache = config.get('use_cache', True)
        session = requests.Session()

        def __init__(self, args, kwargs):
            api = self.api
            # If authentication is required and no credentials
            # are provided, throw an error.
            if self.require_auth and not api.auth:
                raise TweepError('Authentication required!')

            self.post_data = kwargs.pop('post_data', None)
            self.retry_count = kwargs.pop('retry_count',
                                          api.retry_count)
            self.retry_delay = kwargs.pop('retry_delay',
                                          api.retry_delay)
            self.retry_errors = kwargs.pop('retry_errors',
                                           api.retry_errors)
            self.wait_on_rate_limit = kwargs.pop('wait_on_rate_limit',
                                                 api.wait_on_rate_limit)
            self.wait_on_rate_limit_notify = kwargs.pop('wait_on_rate_limit_notify',
                                                        api.wait_on_rate_limit_notify)
            self.parser = kwargs.pop('parser', api.parser)
            self.session.headers = kwargs.pop('headers', {})
            self.build_parameters(args, kwargs)

            # Pick correct URL root to use
            if self.search_api:
                self.api_root = api.search_root
            elif self.upload_api:
                self.api_root = api.upload_root
            else:
                self.api_root = api.api_root

            # Perform any path variable substitution
            self.build_path()

            if self.search_api:
                self.host = api.search_host
            elif self.upload_api:
                self.host = api.upload_host
            else:
                self.host = api.host

            # Manually set Host header to fix an issue in python 2.5
            # or older where Host is set including the 443 port.
            # This causes Twitter to issue 301 redirect.
            # See Issue https://github.com/tweepy/tweepy/issues/12
            self.session.headers['Host'] = self.host
            # Monitoring rate limits
            self._remaining_calls = None
            self._reset_time = None

        def build_parameters(self, args, kwargs):
            self.session.params = {}
            for idx, arg in enumerate(args):
                if arg is None:
                    continue
                try:
                    self.session.params[self.allowed_param[idx]] = convert_to_utf8_str(arg)
                except IndexError:
                    raise TweepError('Too many parameters supplied!')

            for k, arg in kwargs.items():
                if arg is None:
                    continue
                if k in self.session.params:
                    raise TweepError('Multiple values for parameter %s supplied!' % k)

                self.session.params[k] = convert_to_utf8_str(arg)

            log.debug("PARAMS: %r", self.session.params)

        def build_path(self):
            for variable in re_path_template.findall(self.path):
                name = variable.strip('{}')

                if name == 'user' and 'user' not in self.session.params and self.api.auth:
                    # No 'user' parameter provided, fetch it from Auth instead.
                    value = self.api.auth.get_username()
                else:
                    try:
                        value = quote(self.session.params[name])
                    except KeyError:
                        raise TweepError('No parameter value found for path variable: %s' % name)
                    del self.session.params[name]

                self.path = self.path.replace(variable, value)

        def execute(self):
            self.api.cached_result = False

            # Build the request URL
            url = self.api_root + self.path
            full_url = 'https://' + self.host + url

            # Query the cache if one is available
            # and this request uses a GET method.
            if self.use_cache and self.api.cache and self.method == 'GET':
                cache_result = self.api.cache.get('%s?%s' % (url, urlencode(self.session.params)))
                # if cache result found and not expired, return it
                if cache_result:
                    # must restore api reference
                    if isinstance(cache_result, list):
                        for result in cache_result:
                            if isinstance(result, Model):
                                result._api = self.api
                    else:
                        if isinstance(cache_result, Model):
                            cache_result._api = self.api
                    self.api.cached_result = True
                    return cache_result

            # Continue attempting request until successful
            # or maximum number of retries is reached.
            retries_performed = 0
            while retries_performed < self.retry_count + 1:
                # handle running out of api calls
                if self.wait_on_rate_limit:
                    if self._reset_time is not None:
                        if self._remaining_calls is not None:
                            if self._remaining_calls < 1:
                                sleep_time = self._reset_time - int(time.time())
                                if sleep_time > 0:
                                    if self.wait_on_rate_limit_notify:
                                        log.warning("Rate limit reached. Sleeping for: %d" % sleep_time)
                                    time.sleep(sleep_time + 5)  # sleep for few extra sec

                # if self.wait_on_rate_limit and self._reset_time is not None and \
                #                 self._remaining_calls is not None and self._remaining_calls < 1:
                #     sleep_time = self._reset_time - int(time.time())
                #     if sleep_time > 0:
                #         if self.wait_on_rate_limit_notify:
                #             log.warning("Rate limit reached. Sleeping for: %d" % sleep_time)
                #         time.sleep(sleep_time + 5)  # sleep for few extra sec

                # Apply authentication
                auth = None
                if self.api.auth:
                    auth = self.api.auth.apply_auth()

                # Request compression if configured
                if self.api.compression:
                    self.session.headers['Accept-encoding'] = 'gzip'

                # Execute request
                try:
                    resp = self.session.request(self.method,
                                                full_url,
                                                data=self.post_data,
                                                timeout=self.api.timeout,
                                                auth=auth,
                                                proxies=self.api.proxy)
                except Exception as e:
                    six.reraise(TweepError, TweepError('Failed to send request: %s' % e), sys.exc_info()[2])

                rem_calls = resp.headers.get('x-rate-limit-remaining')

                if rem_calls is not None:
                    self._remaining_calls = int(rem_calls)
                elif isinstance(self._remaining_calls, int):
                    self._remaining_calls -= 1
                reset_time = resp.headers.get('x-rate-limit-reset')
                if reset_time is not None:
                    self._reset_time = int(reset_time)
                if self.wait_on_rate_limit and self._remaining_calls == 0 and (
                        # if ran out of calls before waiting switching retry last call
                        resp.status_code == 429 or resp.status_code == 420):
                    continue
                retry_delay = self.retry_delay
                # Exit request loop if non-retry error code
                if resp.status_code == 200:
                    break
                elif (resp.status_code == 429 or resp.status_code == 420) and self.wait_on_rate_limit:
                    if 'retry-after' in resp.headers:
                        retry_delay = float(resp.headers['retry-after'])
                elif self.retry_errors and resp.status_code not in self.retry_errors:
                    break

                # Sleep before retrying request again
                time.sleep(retry_delay)
                retries_performed += 1

            # If an error was returned, throw an exception
            self.api.last_response = resp
            if resp.status_code and not 200 <= resp.status_code < 300:
                try:
                    error_msg, api_error_code = \
                        self.parser.parse_error(resp.text)
                except Exception:
                    error_msg = "Twitter error response: status code = %s" % resp.status_code
                    api_error_code = None

                if is_rate_limit_error_message(error_msg):
                    raise RateLimitError(error_msg, resp)
                else:
                    raise TweepError(error_msg, resp, api_code=api_error_code)

            # Parse the response payload
            result = self.parser.parse(self, resp.text)

            # Store result into cache if one is available.
            if self.use_cache and self.api.cache and self.method == 'GET' and result:
                self.api.cache.store('%s?%s' % (url, urlencode(self.session.params)), result)

            return result

    def _call(*args, **kwargs):
        method = APIMethod(args, kwargs)
        if kwargs.get('create'):
            return method
        else:
            return method.execute()

    # Set pagination mode
    if 'cursor' in APIMethod.allowed_param:
        _call.pagination_mode = 'cursor'
    elif 'max_id' in APIMethod.allowed_param:
        if 'since_id' in APIMethod.allowed_param:
            _call.pagination_mode = 'id'
    elif 'page' in APIMethod.allowed_param:
        _call.pagination_mode = 'page'

    return _call
