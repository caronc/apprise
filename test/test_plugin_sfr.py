# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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
# POSSIBILITY OF SUCH DAMAGE.

from unittest import mock
import pytest
import requests

from apprise.plugins.sfr import NotifySFR
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('sfr://', {
        'instance': TypeError,
    }),
    ('sfr://:@/', {
        'instance': TypeError,
    }),
    ('sfr://:service_password', {
        'instance': TypeError,
    }),
    ('sfr://:service_password@', {
        'instance': TypeError,
    }),
    ('sfr://:service_password@/', {
        'instance': TypeError,
    }),
    ('sfr://:service_password@%s', {
        'instance': TypeError,
    }),
    ('sfr://:service_password@%s/', {
        'instance': TypeError,
    }),
    ('sfr://:service_password@%s/to', {
        'instance': TypeError,
    }),
    ('sfr://:service_password@space_id/to?media=TEST', {
        'instance': TypeError,
    }),
    ('sfr://service_id:', {
        'instance': TypeError,
    }),
    ('sfr://service_id:@', {
        'instance': TypeError,
    }),
    ('sfr://service_id:@{}'.format(
        '0' * 8), {
        'instance': TypeError,
    }),
    ('sfr://service_id:@{}/'.format(
        '0' * 8), {
        'instance': TypeError,
    }),
    ('sfr://service_id:@{}/to'.format(
        '0' * 8), {
        'instance': TypeError,
    }),
    ('sfr://service_id:@{}/to?media=TEST'.format(
        '0' * 8), {
        'instance': TypeError,
    }),
    ('sfr://service_id:service_password@{}/{}?from=MyApp&timeout=30'.format(
        '0' * 8, '0' * 10), {
        'instance': NotifySFR,
        'requests_response_code': requests.codes.ok,
    }),
    ('sfr://srv_id:srv_pwd@{}/{}?ttsVoice=laura8k&lang=en_US'.format(
        '0' * 8, '0' * 10), {
        'instance': NotifySFR,
        'requests_response_code': requests.codes.ok,
    }),
    ('sfr://service_id:service_password@{}/{}?media=SMSLong'.format(
        '0' * 8, '0' * 10), {
        'instance': NotifySFR,
        'requests_response_code': requests.codes.ok,
    }),
    ('sfr://service_id:service_password@{}/{}?media=SMS'.format(
        '0' * 8, '0' * 10), {
        'instance': NotifySFR,
        'requests_response_code': requests.codes.ok,
    }),
    ('sfr://service_id:service_password@{}/{}'.format(
        '0' * 8, '0' * 10), {
        'instance': NotifySFR,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
)


def test_plugin_sfr_urls():
    """
    NotifySFR() Apprise URLs
    """
    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_sfr_notification_ok(mock_post):
    """
    NotifySFR() Notifications Ok response
    """
    # Prepare Mock
    # Create a mock response object
    mock_response = mock.Mock()
    mock_response.status_code = requests.codes.ok
    mock_response.json.return_value = {
        'success': True,
        'response': 6710530753
    }
    mock_post.return_value = mock_response

    # Test our URL parsing
    results = NotifySFR.parse_url(
        'sfr://srv:pwd@{}/{}?media=SMSLong'.format('1' * 8, '0' * 10))

    assert isinstance(results, dict)
    assert results['user'] == 'srv'
    assert results['password'] == 'pwd'
    assert results['space_id'] == '11111111'
    assert results['to'] == '0000000000'
    assert results['media'] == 'SMSLong'

    instance = NotifySFR(**results)
    assert isinstance(instance, NotifySFR)

    response = instance.send(body="test")
    assert response is True
    assert mock_post.call_count == 1


@mock.patch('requests.post')
def test_plugin_sfr_notification_ko(mock_post):
    """
    NotifySFR() Notifications ko response
    """
    # Reset our object
    mock_post.reset_mock()
    # Prepare Mock
    # Create a mock response object
    mock_response = mock.Mock()
    mock_response.status_code = requests.codes.ok
    mock_response.json.return_value = {
        'success': False,
        'errorCode': 'AUTHENTICATION_FAILED',
        'errorDetail': 'Authentification échouée',
        'fatal': True,
        'invalidParams': True
    }
    mock_post.return_value = mock_response

    # Test "real" parameters
    results = NotifySFR.parse_url(
        'sfr://{}:other_fjv&8password@{}/{}?timeout=30&media=SMS'.format(
            '4' * 6, '1' * 8, '8' * 10))

    assert isinstance(results, dict)
    assert results['user'] == '444444'
    assert results['password'] == 'other_fjv&8password'
    assert results['space_id'] == '11111111'
    assert results['to'] == '8888888888'
    assert results['media'] == 'SMS'
    assert results['from'] == ''
    assert results['timeout'] == 30

    instance = NotifySFR(**results)
    assert isinstance(instance, NotifySFR)

    response = instance.send(body="test")
    assert response is False
    assert mock_post.call_count == 1

    # Test error handling
    mock_post.return_value.status_code = requests.codes.ok
    response = instance.send(body="test")
    assert response is False
    assert mock_post.call_count == 2


@mock.patch('requests.post')
def test_plugin_sfr_notification_exceptions(mock_post):
    """
    NotifySFR() Notifications exceptions
    """
    mock_post.reset_mock()
    # Prepare Mock
    # Create a mock response object
    mock_response = mock.Mock()
    mock_response.status_code = requests.codes.internal_server_error
    mock_post.return_value = mock_response

    # Test "real" parameters
    results = NotifySFR.parse_url(
        'sfr://{}:str0*fn_ppw0rd@{}/{}'.format(
            "404ghwo89144", '9993384', '+33959290404'))

    assert isinstance(results, dict)
    assert results['user'] == '404ghwo89144'
    assert results['password'] == 'str0*fn_ppw0rd'
    assert results['space_id'] == '9993384'
    assert results['to'] == '+33959290404'
    assert results['media'] == 'SMSUnicode'
    assert results['timeout'] == 2880

    instance = NotifySFR(**results)
    assert isinstance(instance, NotifySFR)

    response = instance.send(body="my other test 1234")
    # Must return False
    assert response is False
    assert mock_post.call_count == 1


@mock.patch('requests.post')
def test_plugin_sfr_failure(mock_post):
    """
    NotifySFR() Failure Cases
    """
    mock_post.reset_mock()
    # Prepare Mock
    # Create a mock response object
    mock_response = mock.Mock()
    mock_response.status_code = requests.codes.no_content
    mock_post.return_value = mock_response

    # Invalid service_id
    with pytest.raises(TypeError):
        NotifySFR(
            user=None,
            password="service_password",
            space_id="space_id",
            to="to",
        )

    # Invalid service_password
    with pytest.raises(TypeError):
        NotifySFR(
            user="service_id",
            password=None,
            space_id="space_id",
            to="to",
        )

    # Invalid space_id
    with pytest.raises(TypeError):
        NotifySFR(
            user="service_id",
            password="service_password",
            space_id=None,
            to="to",
        )

    # Invalid to
    with pytest.raises(TypeError):
        NotifySFR(
            user="service_id",
            password="service_password",
            space_id="space_id",
            to=None,
        )
