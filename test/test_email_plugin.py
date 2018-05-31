# -*- coding: utf-8 -*-
#
# NotifyEmail - Unit Tests
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

from apprise import plugins
from apprise import NotifyType
from apprise import Apprise
import smtplib
import mock
import re


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
        'exception': TypeError,
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
        'exception': TypeError,
    }),
    # Invalid From Address
    ('mailtos://nuxref.com?user=&pass=.', {
        'exception': TypeError,
    }),
    # Invalid To Address
    ('mailtos://user:pass@nuxref.com?to=@', {
        'exception': TypeError,
    }),
    # Valid URL, but can't structure a proper email
    ('mailtos://nuxref.com?user=%20!&pass=.', {
        'exception': TypeError,
    }),
    # Invalid From (and To) Address
    ('mailtos://nuxref.com?to=test', {
        'exception': TypeError,
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
def test_email_plugin(mock_smtp):
    """
    API: NotifyEmail Plugin()

    """

    # iterate over our dictionary and test it out
    for (url, meta) in TEST_URLS:

        # Our expected instance
        instance = meta.get('instance', None)

        # Our expected exception
        exception = meta.get('exception', None)

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

            assert(exception is None)

            if obj is None:
                # We're done
                continue

            if instance is None:
                # Expected None but didn't get it
                print('%s instantiated %s' % (url, str(obj)))
                assert(False)

            assert(isinstance(obj, instance))

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

                        except Exception as e:
                            # We can't handle this exception type
                            print('%s / %s' % (url, str(e)))
                            assert False

            except AssertionError:
                # Don't mess with these entries
                raise

            except Exception as e:
                # Check that we were expecting this exception to happen
                assert isinstance(e, response)

        except AssertionError:
            # Don't mess with these entries
            print('%s AssertionError' % url)
            raise

        except Exception as e:
            # Handle our exception
            print('%s / %s' % (url, str(e)))
            assert(exception is not None)
            assert(isinstance(e, exception))


@mock.patch('smtplib.SMTP')
def test_webbase_lookup(mock_smtp):
    """
    API: Web Based Lookup Tests

    """

    from apprise.plugins import NotifyEmailBase

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
