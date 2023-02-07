# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
from unittest import mock

import pytest
import requests
from json import dumps
from apprise import Apprise

from apprise.plugins.NotifyVoipms import NotifyVoipms
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('voipms://', {
        # No email/password specified
        'instance': TypeError,
    }),
    ('voipms://@:', {
        # Invalid url
        'instance': TypeError,
    }),
    ('voipms://{}/{}'.format('user@example.com', '1' * 11), {
        # No password specified
        'instance': TypeError,
    }),
    ('voipms://:{}'.format('password'), {
        # No email specified
        'instance': TypeError,
    }),
    ('voipms://{}:{}/{}'.format('user@', 'pass', '1' * 11), {
        # Check valid email
        'instance': TypeError,
    }),
    ('voipms://{email}:{password}'.format(
        email='user@example.com',
        password='password'), {

        # No from_phone specified
        'instance': TypeError,
    }),
    # Invalid phone number test
    ('voipms://{email}:{password}/1613'.format(
        email='user@example.com',
        password='password'), {

        # Invalid phone number
        'instance': TypeError,
    }),
    # Invalid country code phone number test
    ('voipms://{email}:{password}/01133122446688'.format(
        email='user@example.com',
        password='password'), {

        # Non North American phone number
        'instance': TypeError,
    }),
    ('voipms://{email}:{password}/{from_phone}/{targets}/'.format(
        email='user@example.com',
        password='password',
        from_phone='16134448888',
        targets='/'.join(['26134442222'])), {

        # Invalid target phone number
        'instance': NotifyVoipms,
        'response': False,
        'requests_response_code': 999,
    }),
    ('voipms://{email}:{password}/{from_phone}'.format(
        email='user@example.com',
        password='password',
        from_phone='16138884444'), {

        'instance': NotifyVoipms,
        # No targets specified
        'response': False,
        'requests_response_code': 999,
    }),
    ('voipms://{email}:{password}/?from={from_phone}'.format(
        email='user@example.com',
        password='password',
        from_phone='16138884444'), {

        'instance': NotifyVoipms,
        # No targets specified
        'response': False,
        'requests_response_code': 999,
    }),
    ('voipms://{email}:{password}/{from_phone}/{targets}/'.format(
        email='user@example.com',
        password='password',
        from_phone='16138884444',
        targets='/'.join(['16134442222'])), {

        # Valid
        'instance': NotifyVoipms,
        'response': True,
        'privacy_url': 'voipms://user@example.com:p...d/16...4',
    }),
    ('voipms://{email}:{password}/{from_phone}/{targets}/'.format(
        email='user@example.com',
        password='password',
        from_phone='16138884444',
        targets='/'.join(['16134442222', '16134443333'])), {

        # Valid multiple targets
        'instance': NotifyVoipms,
        'response': True,
        'privacy_url': 'voipms://user@example.com:p...d/16...4',
    }),
    ('voipms://{email}:{password}/?from={from_phone}&to={targets}'.format(
        email='user@example.com',
        password='password',
        from_phone='16138884444',
        targets='16134448888'), {

        # Valid
        'instance': NotifyVoipms,
    }),
    ('voipms://{email}:{password}/{from_phone}/{targets}/'.format(
        email='user@example.com',
        password='password',
        from_phone='16138884444',
        targets='16134442222'), {

        'instance': NotifyVoipms,
        # Throws a series of errors
        'test_requests_exceptions': True,
    }),
)


def test_plugin_voipms():
    """
    NotifyVoipms() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@ mock.patch('requests.get')
def test_plugin_voipms_edge_cases(mock_get):
    """
    NotifyVoipms() Edge Cases

    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_get.return_value = response

    # Initialize some generic (but valid) tokens
    email = 'user@example.com'
    password = 'password'
    source = '+1 (555) 123-3456'
    targets = '+1 (555) 123-9876'

    # No email specified
    with pytest.raises(TypeError):
        NotifyVoipms(email=None, source=source)

    # a error response is returned
    response.status_code = 400
    response.content = dumps({
        'code': 21211,
        'message': "Unable to process your request.",
    })
    mock_get.return_value = response

    # Initialize our object
    obj = Apprise.instantiate(
        'voipms://{email}:{password}/{source}/{targets}'.format(
            email=email,
            password=password,
            source=source,
            targets=targets))

    assert isinstance(obj, NotifyVoipms)

    # We will fail with the above error code
    assert obj.notify('title', 'body', 'info') is False


@mock.patch('requests.get')
def test_plugin_voipms_non_success_status(mock_get):
    """
    NotifyVoipms() Non Success Status

    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_get.return_value = response

    # A 200 response is returned but non-success message
    response.status_code = 200
    response.content = dumps({
        'status': 'invalid_credentials',
        'message': 'Username or Password is incorrect',
    })

    obj = Apprise.instantiate(
        'voipms://{email}:{password}/{source}/{targets}'.format(
            email='user@example.com',
            password='badpassword',
            source='16134448888',
            targets='16134442222'))

    assert isinstance(obj, NotifyVoipms)

    # We will fail with the above error code
    assert obj.notify('title', 'body', 'info') is False

    response.content = '{'
    assert obj.send('title', 'body') is False
