# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
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

import re
import six
import mock
import smtplib

from apprise import plugins
from apprise import NotifyType
from apprise import Apprise
from apprise.plugins import NotifyEmailBase

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


TEST_URLS = (
    ##################################
    # NotifyEmail
    ##################################
    ('mailto://', {
        'instance': None,
    }),
    ('mailtos://', {
        'instance': None,
    }),
    ('mailto://:@/', {
        'instance': None
    }),
    # No Username
    ('mailtos://:pass@nuxref.com:567', {
        # Can't prepare a To address using this expression
        'instance': TypeError,
    }),

    # Pre-Configured Email Services
    ('mailto://user:pass@gmail.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@hotmail.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@live.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@prontomail.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@yahoo.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@yahoo.ca', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@fastmail.com', {
        'instance': plugins.NotifyEmail,
    }),

    # Custom Emails
    ('mailtos://user:pass@nuxref.com:567', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@nuxref.com:567?format=html', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailtos://user:pass@nuxref.com:567?to=l2g@nuxref.com', {
        'instance': plugins.NotifyEmail,
    }),
    (
        'mailtos://user:pass@example.com?smtp=smtp.example.com&timeout=5'
        '&name=l2g&from=noreply@example.com', {
            'instance': plugins.NotifyEmail,
        },
    ),
    ('mailto://user:pass@example.com?timeout=invalid.entry', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@example.com?timeout=invalid.entry', {
        'instance': plugins.NotifyEmail,
    }),
    (
        'mailto://user:pass@example.com:2525?user=l2g@example.com'
        '&pass=l2g@apprise!is!Awesome', {
            'instance': plugins.NotifyEmail,
        },
    ),
    (
        'mailto://user:pass@example.com:2525?user=l2g@example.com'
        '&pass=l2g@apprise!is!Awesome&format=text', {
            'instance': plugins.NotifyEmail,
        },
    ),
    # No Password
    ('mailtos://user:@nuxref.com', {
        'instance': plugins.NotifyEmail,
    }),
    # Invalid From Address
    ('mailtos://user:pass@nuxref.com?from=@', {
        'instance': TypeError,
    }),
    # Invalid From Address
    ('mailtos://nuxref.com?user=&pass=.', {
        'instance': TypeError,
    }),
    # Invalid To Address
    ('mailtos://user:pass@nuxref.com?to=@', {
        'instance': TypeError,
    }),
    # Valid URL, but can't structure a proper email
    ('mailtos://nuxref.com?user=%20!&pass=.', {
        'instance': TypeError,
    }),
    # Invalid From (and To) Address
    ('mailtos://nuxref.com?to=test', {
        'instance': TypeError,
    }),
    # Invalid Secure Mode
    ('mailtos://user:pass@example.com?mode=notamode', {
        'instance': TypeError,
    }),
    # STARTTLS flag checking
    ('mailtos://user:pass@gmail.com?mode=starttls', {
        'instance': plugins.NotifyEmail,
    }),
    # SSL flag checking
    ('mailtos://user:pass@gmail.com?mode=ssl', {
        'instance': plugins.NotifyEmail,
    }),
    # Can make a To address using what we have (l2g@nuxref.com)
    ('mailtos://nuxref.com?user=l2g&pass=.', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@localhost:2525', {
        'instance': plugins.NotifyEmail,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_smtplib_exceptions': True,
    }),
)


@mock.patch('smtplib.SMTP')
@mock.patch('smtplib.SMTP_SSL')
def test_email_plugin(mock_smtp, mock_smtpssl):
    """
    API: NotifyEmail Plugin()

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.NotifyBase.request_rate_per_sec = 0

    # iterate over our dictionary and test it out
    for (url, meta) in TEST_URLS:

        # Our expected instance
        instance = meta.get('instance', None)

        # Our expected server objects
        self = meta.get('self', None)

        # Our expected Query response (True, False, or exception type)
        response = meta.get('response', True)

        test_smtplib_exceptions = meta.get(
            'test_smtplib_exceptions', False)

        # Our mock of our socket action
        mock_socket = mock.Mock()
        mock_socket.starttls.return_value = True
        mock_socket.login.return_value = True

        # Create a mock SMTP Object
        mock_smtp.return_value = mock_socket
        mock_smtpssl.return_value = mock_socket

        if test_smtplib_exceptions:
            # Handle exception testing; first we turn the boolean flag ito
            # a list of exceptions
            test_smtplib_exceptions = (
                smtplib.SMTPHeloError(
                    0, 'smtplib.SMTPHeloError() not handled'),
                smtplib.SMTPException(
                    0, 'smtplib.SMTPException() not handled'),
                RuntimeError(
                    0, 'smtplib.HTTPError() not handled'),
                smtplib.SMTPRecipientsRefused(
                    'smtplib.SMTPRecipientsRefused() not handled'),
                smtplib.SMTPSenderRefused(
                    0, 'smtplib.SMTPSenderRefused() not handled',
                    'addr@example.com'),
                smtplib.SMTPDataError(
                    0, 'smtplib.SMTPDataError() not handled'),
                smtplib.SMTPServerDisconnected(
                    'smtplib.SMTPServerDisconnected() not handled'),
            )

        try:
            obj = Apprise.instantiate(url, suppress_exceptions=False)

            if obj is None:
                # We're done (assuming this is what we were expecting)
                assert instance is None
                continue

            if instance is None:
                # Expected None but didn't get it
                print('%s instantiated %s (but expected None)' % (
                    url, str(obj)))
                assert(False)

            assert(isinstance(obj, instance))

            if isinstance(obj, plugins.NotifyBase.NotifyBase):
                # We loaded okay; now lets make sure we can reverse this url
                assert(isinstance(obj.url(), six.string_types) is True)

                # Instantiate the exact same object again using the URL from
                # the one that was already created properly
                obj_cmp = Apprise.instantiate(obj.url())

                # Our object should be the same instance as what we had
                # originally expected above.
                if not isinstance(obj_cmp, plugins.NotifyBase.NotifyBase):
                    # Assert messages are hard to trace back with the way
                    # these tests work. Just printing before throwing our
                    # assertion failure makes things easier to debug later on
                    print('TEST FAIL: {} regenerated as {}'.format(
                        url, obj.url()))
                    assert(False)

            if self:
                # Iterate over our expected entries inside of our object
                for key, val in self.items():
                    # Test that our object has the desired key
                    assert(hasattr(key, obj))
                    assert(getattr(key, obj) == val)

            try:
                if test_smtplib_exceptions is False:
                    # check that we're as expected
                    assert obj.notify(
                        title='test', body='body',
                        notify_type=NotifyType.INFO) == response

                else:
                    for exception in test_smtplib_exceptions:
                        mock_socket.sendmail.side_effect = exception
                        try:
                            assert obj.notify(
                                title='test', body='body',
                                notify_type=NotifyType.INFO) is False

                        except AssertionError:
                            # Don't mess with these entries
                            raise

                        except Exception:
                            # We can't handle this exception type
                            raise

            except AssertionError:
                # Don't mess with these entries
                print('%s AssertionError' % url)
                raise

            except Exception as e:
                # Check that we were expecting this exception to happen
                if not isinstance(e, response):
                    raise

        except AssertionError:
            # Don't mess with these entries
            print('%s AssertionError' % url)
            raise

        except Exception as e:
            # Handle our exception
            if(instance is None):
                raise

            if not isinstance(e, instance):
                raise


@mock.patch('smtplib.SMTP')
@mock.patch('smtplib.SMTP_SSL')
def test_webbase_lookup(mock_smtp, mock_smtpssl):
    """
    API: Web Based Lookup Tests

    """

    # Insert a test email at the head of our table
    NotifyEmailBase.WEBBASE_LOOKUP_TABLE = (
        (
            # Testing URL
            'Testing Lookup',
            re.compile(r'^(?P<id>[^@]+)@(?P<domain>l2g\.com)$', re.I),
            {
                'port': 123,
                'smtp_host': 'smtp.l2g.com',
                'secure': True,
                'login_type': (NotifyEmailBase.WebBaseLogin.USERID, )
            },
        ),
    ) + NotifyEmailBase.WEBBASE_LOOKUP_TABLE

    obj = Apprise.instantiate(
        'mailto://user:pass@l2g.com', suppress_exceptions=True)

    assert(isinstance(obj, plugins.NotifyEmail))
    assert obj.to_addr == 'user@l2g.com'
    assert obj.from_addr == 'user@l2g.com'
    assert obj.password == 'pass'
    assert obj.user == 'user'
    assert obj.secure is True
    assert obj.port == 123
    assert obj.smtp_host == 'smtp.l2g.com'


@mock.patch('smtplib.SMTP')
def test_smtplib_init_fail(mock_smtplib):
    """
    API: Test exception handling when calling smtplib.SMTP()

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.NotifyBase.request_rate_per_sec = 0

    obj = Apprise.instantiate(
        'mailto://user:pass@gmail.com', suppress_exceptions=False)
    assert(isinstance(obj, plugins.NotifyEmail))

    # Support Exception handling of smtplib.SMTP
    mock_smtplib.side_effect = RuntimeError('Test')

    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is False

    # A handled and expected exception
    mock_smtplib.side_effect = smtplib.SMTPException('Test')
    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is False


@mock.patch('smtplib.SMTP')
def test_smtplib_send_okay(mock_smtplib):
    """
    API: Test a successfully sent email

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.NotifyBase.request_rate_per_sec = 0

    # Defaults to HTML
    obj = Apprise.instantiate(
        'mailto://user:pass@gmail.com', suppress_exceptions=False)
    assert(isinstance(obj, plugins.NotifyEmail))

    # Support an email simulation where we can correctly quit
    mock_smtplib.starttls.return_value = True
    mock_smtplib.login.return_value = True
    mock_smtplib.sendmail.return_value = True
    mock_smtplib.quit.return_value = True

    assert(obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is True)

    # Set Text
    obj = Apprise.instantiate(
        'mailto://user:pass@gmail.com?format=text', suppress_exceptions=False)
    assert(isinstance(obj, plugins.NotifyEmail))

    assert(obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is True)


def test_email_url_escaping():
    """
    API: Test that user/passwords are properly escaped from URL

    """
    # quote(' %20')
    passwd = '%20%2520'

    # Basically we want to check that ' ' equates to %20 and % equates to %25
    # So the above translates to ' %20' (a space in front of %20).  We want
    # to verify the handling of the password escaping and when it happens.
    # a very bad response would be '  ' (double space)
    obj = plugins.NotifyEmail.parse_url(
        'mailto://user:{}@gmail.com?format=text'.format(passwd))

    assert isinstance(obj, dict) is True
    assert 'password' in obj

    # Escaping doesn't happen at this stage because we want to leave this to
    # the plugins discretion
    assert obj.get('password') == '%20%2520'

    obj = Apprise.instantiate(
        'mailto://user:{}@gmail.com?format=text'.format(passwd),
        suppress_exceptions=False)
    assert isinstance(obj, plugins.NotifyEmail) is True

    # The password is escapped 'once' at this point
    assert obj.password == ' %20'
