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

import logging
import os
import re
from unittest import mock

import smtplib
from email.header import decode_header

from apprise import NotifyType, NotifyBase
from apprise import Apprise
from apprise import AttachBase
from apprise import AppriseAttachment
from apprise.plugins.NotifyEmail import NotifyEmail
from apprise.plugins import NotifyEmail as NotifyEmailModule

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)


# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

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
        'instance': NotifyEmail,
    }),
    ('mailto://user:pass@hotmail.com', {
        'instance': NotifyEmail,
    }),
    ('mailto://user:pass@live.com', {
        'instance': NotifyEmail,
    }),
    ('mailto://user:pass@prontomail.com', {
        'instance': NotifyEmail,
    }),
    ('mailto://user:pass@yahoo.com', {
        'instance': NotifyEmail,
    }),
    ('mailto://user:pass@yahoo.ca', {
        'instance': NotifyEmail,
    }),
    ('mailto://user:pass@fastmail.com', {
        'instance': NotifyEmail,
    }),
    ('mailto://user:pass@sendgrid.com', {
        'instance': NotifyEmail,
    }),

    # Yandex
    ('mailto://user:pass@yandex.com', {
        'instance': NotifyEmail,
    }),
    ('mailto://user:pass@yandex.ru', {
        'instance': NotifyEmail,
    }),
    ('mailto://user:pass@yandex.fr', {
        'instance': NotifyEmail,
    }),

    # Custom Emails
    ('mailtos://user:pass@nuxref.com:567', {
        'instance': NotifyEmail,
    }),
    ('mailto://user:pass@nuxref.com?mode=ssl', {
        # mailto:// with mode=ssl causes us to convert to ssl
        'instance': NotifyEmail,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'mailtos://user:****@nuxref.com',
    }),
    ('mailto://user:pass@nuxref.com:567?format=html', {
        'instance': NotifyEmail,
    }),
    ('mailtos://user:pass@nuxref.com:567?to=l2g@nuxref.com', {
        'instance': NotifyEmail,
    }),
    ('mailtos://user:pass@domain.com?user=admin@mail-domain.com', {
        'instance': NotifyEmail,
    }),
    ('mailtos://%20@domain.com?user=admin@mail-domain.com', {
        'instance': NotifyEmail,
    }),
    ('mailtos://user:pass@nuxref.com:567/l2g@nuxref.com', {
        'instance': NotifyEmail,
    }),
    (
        'mailto://user:pass@example.com:2525?user=l2g@example.com'
        '&pass=l2g@apprise!is!Awesome', {
            'instance': NotifyEmail,
        },
    ),
    (
        'mailto://user:pass@example.com:2525?user=l2g@example.com'
        '&pass=l2g@apprise!is!Awesome&format=text', {
            'instance': NotifyEmail,
        },
    ),
    (
        # Test Carbon Copy
        'mailtos://user:pass@example.com?smtp=smtp.example.com'
        '&name=l2g&cc=noreply@example.com,test@example.com', {
            'instance': NotifyEmail,
        },
    ),
    (
        # Test Blind Carbon Copy
        'mailtos://user:pass@example.com?smtp=smtp.example.com'
        '&name=l2g&bcc=noreply@example.com,test@example.com', {
            'instance': NotifyEmail,
        },
    ),
    (
        # Test Carbon Copy with bad email
        'mailtos://user:pass@example.com?smtp=smtp.example.com'
        '&name=l2g&cc=noreply@example.com,@', {
            'instance': NotifyEmail,
        },
    ),
    (
        # Test Blind Carbon Copy with bad email
        'mailtos://user:pass@example.com?smtp=smtp.example.com'
        '&name=l2g&bcc=noreply@example.com,@', {
            'instance': NotifyEmail,
        },
    ),
    (
        # Test Reply To
        'mailtos://user:pass@example.com?smtp=smtp.example.com'
        '&name=l2g&reply=test@example.com,test2@example.com', {
            'instance': NotifyEmail,
        },
    ),
    (
        # Test Reply To with bad email
        'mailtos://user:pass@example.com?smtp=smtp.example.com'
        '&name=l2g&reply=test@example.com,@', {
            'instance': NotifyEmail,
        },
    ),
    # headers
    ('mailto://user:pass@localhost.localdomain'
        '?+X-Customer-Campaign-ID=Apprise', {
            'instance': NotifyEmail,
        }),
    # No Password
    ('mailtos://user:@nuxref.com', {
        'instance': NotifyEmail,
    }),
    # Invalid From Address; but just gets put as the from name instead
    # Hence the below generats From: "@ <user@nuxref.com>"
    ('mailtos://user:pass@nuxref.com?from=@', {
        'instance': NotifyEmail,
    }),
    # Invalid From Address
    ('mailtos://nuxref.com?user=&pass=.', {
        'instance': TypeError,
    }),
    # Invalid To Address is accepted, but we won't be able to properly email
    # using the notify() call
    ('mailtos://user:pass@nuxref.com?to=@', {
        'instance': NotifyEmail,
        'response': False,
    }),
    # Valid URL, but can't structure a proper email
    ('mailtos://nuxref.com?user=%20"&pass=.', {
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
        'instance': NotifyEmail,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'mailtos://user:****@gmail.com',
    }),
    # SSL flag checking
    ('mailtos://user:pass@gmail.com?mode=ssl', {
        'instance': NotifyEmail,
    }),
    # Can make a To address using what we have (l2g@nuxref.com)
    ('mailtos://nuxref.com?user=l2g&pass=.', {
        'instance': NotifyEmail,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'mailtos://l2g:****@nuxref.com',
    }),
    ('mailto://user:pass@localhost:2525', {
        'instance': NotifyEmail,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_smtplib_exceptions': True,
    }),
    # Use of both 'name' and 'from' together; these are synonymous
    ('mailtos://user:pass@nuxref.com?'
     'from=jack@gmail.com&name=Jason<jason@gmail.com>', {
         'instance': NotifyEmail}),
    # Test no auth at all
    ('mailto://localhost?from=test@example.com&to=test@example.com', {
        'instance': NotifyEmail,
        'privacy_url': 'mailto://localhost',
    }),
    # Test multi-emails where some are bad
    ('mailto://user:pass@localhost/test@example.com/test2@/$@!/', {
        'instance': NotifyEmail,
        'privacy_url': 'mailto://user:****@localhost/'
    }),
    ('mailto://user:pass@localhost/?bcc=test2@,$@!/', {
        'instance': NotifyEmail,
    }),
    ('mailto://user:pass@localhost/?cc=test2@,$@!/', {
        'instance': NotifyEmail,
    }),
    ('mailto://user:pass@localhost/?reply=test2@,$@!/', {
        'instance': NotifyEmail,
    }),
)


@mock.patch('smtplib.SMTP')
@mock.patch('smtplib.SMTP_SSL')
def test_plugin_email(mock_smtp, mock_smtpssl):
    """
    NotifyEmail() General Checks

    """

    # iterate over our dictionary and test it out
    for (url, meta) in TEST_URLS:

        # Our expected instance
        instance = meta.get('instance', None)

        # Our expected server objects
        self = meta.get('self', None)

        # Our expected Query response (True, False, or exception type)
        response = meta.get('response', True)

        # Our expected privacy url
        # Don't set this if don't need to check it's value
        privacy_url = meta.get('privacy_url')

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
                assert False

            assert isinstance(obj, instance)

            if isinstance(obj, NotifyBase):
                # We loaded okay; now lets make sure we can reverse this url
                assert isinstance(obj.url(), str) is True

                # Verify we can acquire a target count as an integer
                assert isinstance(len(obj), int)

                # Test url() with privacy=True
                assert isinstance(
                    obj.url(privacy=True), str) is True

                # Some Simple Invalid Instance Testing
                assert instance.parse_url(None) is None
                assert instance.parse_url(object) is None
                assert instance.parse_url(42) is None

                if privacy_url:
                    # Assess that our privacy url is as expected
                    assert obj.url(privacy=True).startswith(privacy_url)

                # Instantiate the exact same object again using the URL from
                # the one that was already created properly
                obj_cmp = Apprise.instantiate(obj.url())

                # Our object should be the same instance as what we had
                # originally expected above.
                if not isinstance(obj_cmp, NotifyBase):
                    # Assert messages are hard to trace back with the way
                    # these tests work. Just printing before throwing our
                    # assertion failure makes things easier to debug later on
                    print('TEST FAIL: {} regenerated as {}'.format(
                        url, obj.url()))
                    assert False

                # Verify there is no change from the old and the new
                if len(obj) != len(obj_cmp):
                    print('%d targets found in %s' % (
                        len(obj), obj.url(privacy=True)))
                    print('But %d targets found in %s' % (
                        len(obj_cmp), obj_cmp.url(privacy=True)))
                    raise AssertionError("Target miscount %d != %d")

            if self:
                # Iterate over our expected entries inside of our object
                for key, val in self.items():
                    # Test that our object has the desired key
                    assert hasattr(key, obj)
                    assert getattr(key, obj) == val

            try:
                if test_smtplib_exceptions is False:
                    # Verify we can acquire a target count as an integer
                    targets = len(obj)

                    # check that we're as expected
                    assert obj.notify(
                        title='test', body='body',
                        notify_type=NotifyType.INFO) == response

                    if response:
                        # If we successfully got a response, there must have
                        # been at least 1 target present
                        assert targets > 0

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
            if instance is None:
                raise

            if not isinstance(e, instance):
                raise


@mock.patch('smtplib.SMTP')
@mock.patch('smtplib.SMTP_SSL')
def test_plugin_email_webbase_lookup(mock_smtp, mock_smtpssl):
    """
    NotifyEmail() Web Based Lookup Tests

    """

    # Insert a test email at the head of our table
    NotifyEmailModule.EMAIL_TEMPLATES = (
        (
            # Testing URL
            'Testing Lookup',
            re.compile(r'^(?P<id>[^@]+)@(?P<domain>l2g\.com)$', re.I),
            {
                'port': 123,
                'smtp_host': 'smtp.l2g.com',
                'secure': True,
                'login_type': (NotifyEmailModule.WebBaseLogin.USERID, )
            },
        ),
    ) + NotifyEmailModule.EMAIL_TEMPLATES

    obj = Apprise.instantiate(
        'mailto://user:pass@l2g.com', suppress_exceptions=True)

    assert isinstance(obj, NotifyEmail)
    assert len(obj.targets) == 1
    assert (False, 'user@l2g.com') in obj.targets
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == 'user@l2g.com'
    assert obj.password == 'pass'
    assert obj.user == 'user'
    assert obj.secure is True
    assert obj.port == 123
    assert obj.smtp_host == 'smtp.l2g.com'

    # We get the same results if an email is identified as the username
    # because the USERID variable forces that we can't use an email
    obj = Apprise.instantiate(
        'mailto://_:pass@l2g.com?user=user@test.com', suppress_exceptions=True)
    assert obj.user == 'user'


@mock.patch('smtplib.SMTP')
def test_plugin_email_smtplib_init_fail(mock_smtplib):
    """
    NotifyEmail() Test exception handling when calling smtplib.SMTP()

    """

    obj = Apprise.instantiate(
        'mailto://user:pass@gmail.com', suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail)

    # Support Exception handling of smtplib.SMTP
    mock_smtplib.side_effect = RuntimeError('Test')

    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is False

    # A handled and expected exception
    mock_smtplib.side_effect = smtplib.SMTPException('Test')
    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is False


@mock.patch('smtplib.SMTP')
def test_plugin_email_smtplib_send_okay(mock_smtplib):
    """
    NotifyEmail() Test a successfully sent email

    """

    # Defaults to HTML
    obj = Apprise.instantiate(
        'mailto://user:pass@gmail.com', suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail)

    # Support an email simulation where we can correctly quit
    mock_smtplib.starttls.return_value = True
    mock_smtplib.login.return_value = True
    mock_smtplib.sendmail.return_value = True
    mock_smtplib.quit.return_value = True

    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is True

    # Set Text
    obj = Apprise.instantiate(
        'mailto://user:pass@gmail.com?format=text', suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail)

    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is True

    # Create an apprise object to work with as well
    a = Apprise()
    assert a.add('mailto://user:pass@gmail.com?format=text')

    # Send Attachment with success
    attach = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO,
        attach=attach) is True

    # same results happen from our Apprise object
    assert a.notify(body='body', title='test', attach=attach) is True

    # test using an Apprise Attachment object
    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO,
        attach=AppriseAttachment(attach)) is True

    # same results happen from our Apprise object
    assert a.notify(
        body='body', title='test', attach=AppriseAttachment(attach)) is True

    max_file_size = AttachBase.max_file_size
    # Now do a case where the file can't be sent

    AttachBase.max_file_size = 1
    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO,
        attach=attach) is False

    # same results happen from our Apprise object
    assert a.notify(body='body', title='test', attach=attach) is False

    # Restore value
    AttachBase.max_file_size = max_file_size


@mock.patch('smtplib.SMTP')
def test_plugin_email_smtplib_send_multiple_recipients(mock_smtplib):
    """
    Verify that NotifyEmail() will use a single SMTP session for submitting
    multiple emails.
    """

    # Defaults to HTML
    obj = Apprise.instantiate(
        'mailto://user:pass@mail.example.org?'
        'to=foo@example.net,bar@example.com&'
        'cc=baz@example.org&bcc=qux@example.org', suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail)

    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is True

    assert mock_smtplib.mock_calls == [
        mock.call('mail.example.org', 25, None, timeout=15),
        mock.call().login('user', 'pass'),
        mock.call().sendmail(
            'user@mail.example.org',
            ['foo@example.net', 'baz@example.org', 'qux@example.org'],
            mock.ANY),
        mock.call().sendmail(
            'user@mail.example.org',
            ['bar@example.com', 'baz@example.org', 'qux@example.org'],
            mock.ANY),
        mock.call().quit(),
    ]

    # No from= used in the above
    assert re.match(r'.*from=.*', obj.url()) is None
    # No mode= as this isn't a secure connection
    assert re.match(r'.*mode=.*', obj.url()) is None
    # No smtp= as the SMTP server is the same as the hostname in this case
    assert re.match(r'.*smtp=.*', obj.url()) is None
    # URL is assembled based on provided user
    assert re.match(
        r'^mailto://user:pass\@mail.example.org/.*', obj.url()) is not None

    # Verify our added emails are still part of the URL
    assert re.match(r'.*/foo%40example.net[/?].*', obj.url()) is not None
    assert re.match(r'.*/bar%40example.com[/?].*', obj.url()) is not None

    assert re.match(r'.*bcc=qux%40example.org.*', obj.url()) is not None
    assert re.match(r'.*cc=baz%40example.org.*', obj.url()) is not None


@mock.patch('smtplib.SMTP')
def test_plugin_email_smtplib_internationalization(mock_smtp):
    """
    NotifyEmail() Internationalization Handling

    """

    # Defaults to HTML
    obj = Apprise.instantiate(
        'mailto://user:pass@gmail.com?name=Например%20так',
        suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail)

    class SMTPMock:
        def sendmail(self, *args, **kwargs):
            """
            over-ride sendmail calls so we can check our our
            internationalization formatting went
            """

            match_subject = re.search(
                r'\n?(?P<line>Subject: (?P<subject>(.+?)))\n(?:[a-z0-9-]+:)',
                args[2], re.I | re.M | re.S)
            assert match_subject is not None

            match_from = re.search(
                r'^(?P<line>From: (?P<name>.+) <(?P<email>[^>]+)>)$',
                args[2], re.I | re.M)
            assert match_from is not None

            # Verify our output was correctly stored
            assert match_from.group('email') == 'user@gmail.com'

            assert decode_header(match_from.group('name'))[0][0]\
                .decode('utf-8') == 'Например так'

            assert decode_header(match_subject.group('subject'))[0][0]\
                .decode('utf-8') == 'دعونا نجعل العالم مكانا أفضل.'

        # Dummy Function
        def quit(self, *args, **kwargs):
            return True

        # Dummy Function
        def starttls(self, *args, **kwargs):
            return True

        # Dummy Function
        def login(self, *args, **kwargs):
            return True

    # Prepare our object we will test our generated email against
    mock_smtp.return_value = SMTPMock()

    # Further test encoding through the message content as well
    assert obj.notify(
        # Google Translated to Arabic: "Let's make the world a better place."
        title='دعونا نجعل العالم مكانا أفضل.',
        # Google Translated to Hungarian: "One line of code at a time.'
        body='Egy sor kódot egyszerre.',
        notify_type=NotifyType.INFO) is True


def test_plugin_email_url_escaping():
    """
    NotifyEmail() Test that user/passwords are properly escaped from URL

    """
    # quote(' %20')
    passwd = '%20%2520'

    # Basically we want to check that ' ' equates to %20 and % equates to %25
    # So the above translates to ' %20' (a space in front of %20).  We want
    # to verify the handling of the password escaping and when it happens.
    # a very bad response would be '  ' (double space)
    obj = NotifyEmail.parse_url(
        'mailto://user:{}@gmail.com?format=text'.format(passwd))

    assert isinstance(obj, dict) is True
    assert 'password' in obj

    # Escaping doesn't happen at this stage because we want to leave this to
    # the plugins discretion
    assert obj.get('password') == '%20%2520'

    obj = Apprise.instantiate(
        'mailto://user:{}@gmail.com?format=text'.format(passwd),
        suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    # The password is escaped only 'once'
    assert obj.password == ' %20'


def test_plugin_email_url_variations():
    """
    NotifyEmail() Test URL variations to ensure parsing is correct

    """
    # Test variations of username required to be an email address
    # user@example.com
    obj = Apprise.instantiate(
        'mailto://{user}:{passwd}@example.com?smtp=example.com'.format(
            user='apprise%40example21.ca',
            passwd='abcd123'),
        suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    assert obj.password == 'abcd123'
    assert obj.user == 'apprise@example21.ca'

    # No from= used in the above
    assert re.match(r'.*from=.*', obj.url()) is None
    # No mode= as this isn't a secure connection
    assert re.match(r'.*mode=.*', obj.url()) is None
    # No smtp= as the SMTP server is the same as the hostname in this case
    # even though it was explicitly specified
    assert re.match(r'.*smtp=.*', obj.url()) is None
    # URL is assembled based on provided user
    assert re.match(
        r'^mailto://apprise:abcd123\@example.com/.*', obj.url()) is not None

    # test username specified in the url body (as an argument)
    # this always over-rides the entry at the front of the url
    obj = Apprise.instantiate(
        'mailto://_:{passwd}@example.com?user={user}'.format(
            user='apprise%40example21.ca',
            passwd='abcd123'),
        suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    assert obj.password == 'abcd123'
    assert obj.user == 'apprise@example21.ca'

    # No from= used in the above
    assert re.match(r'.*from=.*', obj.url()) is None
    # No mode= as this isn't a secure connection
    assert re.match(r'.*mode=.*', obj.url()) is None
    # No smtp= as the SMTP server is the same as the hostname in this case
    assert re.match(r'.*smtp=.*', obj.url()) is None
    # URL is assembled based on provided user
    assert re.match(
        r'^mailto://apprise:abcd123\@example.com/.*', obj.url()) is not None

    # test user and password specified in the url body (as an argument)
    # this always over-rides the entries at the front of the url
    obj = Apprise.instantiate(
        'mailtos://_:_@example.com?user={user}&pass={passwd}'.format(
            user='apprise%40example21.ca',
            passwd='abcd123'),
        suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    assert obj.password == 'abcd123'
    assert obj.user == 'apprise@example21.ca'
    assert len(obj.targets) == 1
    assert (False, 'apprise@example.com') in obj.targets
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == 'apprise@example.com'
    assert obj.targets[0][0] is False
    assert obj.targets[0][1] == obj.from_addr[1]

    # No from= used in the above
    assert re.match(r'.*from=.*', obj.url()) is None
    # Default mode is starttls
    assert re.match(r'.*mode=starttls.*', obj.url()) is not None
    # No smtp= as the SMTP server is the same as the hostname in this case
    assert re.match(r'.*smtp=.*', obj.url()) is None
    # URL is assembled based on provided user
    assert re.match(
        r'^mailtos://apprise:abcd123\@example.com/.*', obj.url()) is not None

    # test user and password specified in the url body (as an argument)
    # this always over-rides the entries at the front of the url
    # this is similar to the previous test except we're only specifying
    # this information in the kwargs
    obj = Apprise.instantiate(
        'mailto://example.com?user={user}&pass={passwd}'.format(
            user='apprise%40example21.ca',
            passwd='abcd123'),
        suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    assert obj.password == 'abcd123'
    assert obj.user == 'apprise@example21.ca'
    assert len(obj.targets) == 1
    assert (False, 'apprise@example.com') in obj.targets
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == 'apprise@example.com'
    assert obj.targets[0][0] is False
    assert obj.targets[0][1] == obj.from_addr[1]
    assert obj.smtp_host == 'example.com'

    # No from= used in the above
    assert re.match(r'.*from=.*', obj.url()) is None
    # No mode= as this isn't a secure connection
    assert re.match(r'.*mode=.*', obj.url()) is None
    # No smtp= as the SMTP server is the same as the hostname in this case
    assert re.match(r'.*smtp=.*', obj.url()) is None
    # URL is assembled based on provided user
    assert re.match(
        r'^mailto://apprise:abcd123\@example.com/.*', obj.url()) is not None

    # test a complicated example
    obj = Apprise.instantiate(
        'mailtos://{user}:{passwd}@{host}:{port}'
        '?smtp={smtp_host}&format=text&from=Charles<{this}>&to={that}'.format(
            user='apprise%40example21.ca',
            passwd='abcd123',
            host='example.com',
            port=1234,
            this='from@example.jp',
            that='to@example.jp',
            smtp_host='smtp.example.edu'),
        suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    assert obj.password == 'abcd123'
    assert obj.user == 'apprise@example21.ca'
    assert obj.host == 'example.com'
    assert obj.port == 1234
    assert obj.smtp_host == 'smtp.example.edu'
    assert len(obj.targets) == 1
    assert (False, 'to@example.jp') in obj.targets
    assert obj.from_addr[0] == 'Charles'
    assert obj.from_addr[1] == 'from@example.jp'
    assert re.match(
        r'.*from=Charles\+%3Cfrom%40example.jp%3E.*', obj.url()) is not None

    # Test Tagging under various urll encodings
    for toaddr in ('/john.smith+mytag@domain.com',
                   '?to=john.smith+mytag@domain.com',
                   '/john.smith%2Bmytag@domain.com',
                   '?to=john.smith%2Bmytag@domain.com'):

        obj = Apprise.instantiate(
            'mailto://user:pass@domain.com{}'.format(toaddr))
        assert isinstance(obj, NotifyEmail) is True
        assert obj.password == 'pass'
        assert obj.user == 'user'
        assert obj.host == 'domain.com'
        assert obj.from_addr[0] == obj.app_id
        assert obj.from_addr[1] == 'user@domain.com'
        assert len(obj.targets) == 1
        assert obj.targets[0][0] is False
        assert obj.targets[0][1] == 'john.smith+mytag@domain.com'


def test_plugin_email_dict_variations():
    """
    NotifyEmail() Test email dictionary variations to ensure parsing is correct

    """
    # Test variations of username required to be an email address
    # user@example.com
    obj = Apprise.instantiate({
        'schema': 'mailto',
        'user': 'apprise@example.com',
        'password': 'abd123',
        'host': 'example.com'}, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True


@mock.patch('smtplib.SMTP_SSL')
@mock.patch('smtplib.SMTP')
def test_plugin_email_url_parsing(mock_smtp, mock_smtp_ssl):
    """
    NotifyEmail() Test email url parsing

    """

    response = mock.Mock()
    mock_smtp_ssl.return_value = response
    mock_smtp.return_value = response

    # Test variations of username required to be an email address
    # user@example.com; we also test an over-ride port on a template driven
    # mailto:// entry
    results = NotifyEmail.parse_url(
        'mailtos://user:pass123@hotmail.com:444'
        '?to=user2@yahoo.com&name=test%20name')
    assert isinstance(results, dict)
    assert 'test name' == results['from_addr']
    assert 'user' == results['user']
    assert 444 == results['port']
    assert 'hotmail.com' == results['host']
    assert 'pass123' == results['password']
    assert 'user2@yahoo.com' in results['targets']

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == 'user@hotmail.com'
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == 'user2@yahoo.com'
    assert _msg.split('\n')[-3] == 'test'

    # Our URL port was over-ridden (on template) to use 444
    # We can verify that this was correctly saved
    assert obj.url().startswith(
        'mailtos://user:pass123@hotmail.com:444/user2%40yahoo.com')
    assert 'mode=starttls' in obj.url()
    assert 'smtp=smtp-mail.outlook.com' in obj.url()

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    # The below switches the `name` with the `to` to verify the results
    # are the same; it also verfies that the mode gets changed to SSL
    # instead of STARTTLS
    results = NotifyEmail.parse_url(
        'mailtos://user:pass123@hotmail.com?smtp=override.com'
        '&name=test%20name&to=user2@yahoo.com&mode=ssl')
    assert isinstance(results, dict)
    assert 'test name' == results['from_addr']
    assert 'user' == results['user']
    assert 'hotmail.com' == results['host']
    assert 'pass123' == results['password']
    assert 'user2@yahoo.com' in results['targets']
    assert 'ssl' == results['secure_mode']
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 1
    assert response.starttls.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == 'user@hotmail.com'
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == 'user2@yahoo.com'
    assert _msg.split('\n')[-3] == 'test'

    user, pw = response.login.call_args[0]
    # the SMTP Server was ovr
    assert pw == 'pass123'
    assert user == 'user'

    assert obj.url().startswith(
        'mailtos://user:pass123@hotmail.com/user2%40yahoo.com')
    # Test that our template over-ride worked
    assert 'mode=ssl' in obj.url()
    assert 'smtp=override.com' in obj.url()
    # No reply address specified
    assert 'reply=' not in obj.url()

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    #
    # Test outlook/hotmail lookups
    #
    results = NotifyEmail.parse_url(
        'mailtos://user:pass123@hotmail.com')
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True
    assert obj.smtp_host == 'smtp-mail.outlook.com'
    # No entries in the reply_to
    assert not obj.reply_to

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == 'pass123'
    assert user == 'user@hotmail.com'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = NotifyEmail.parse_url(
        'mailtos://user:pass123@outlook.com')
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True
    assert obj.smtp_host == 'smtp.outlook.com'
    # No entries in the reply_to
    assert not obj.reply_to

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == 'pass123'
    assert user == 'user@outlook.com'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = NotifyEmail.parse_url(
        'mailtos://user:pass123@outlook.com.au')
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True
    assert obj.smtp_host == 'smtp.outlook.com'
    # No entries in the reply_to
    assert not obj.reply_to

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == 'pass123'
    assert user == 'user@outlook.com.au'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    # Consisitency Checks
    results = NotifyEmail.parse_url(
        'mailtos://outlook.com?smtp=smtp.outlook.com'
        '&user=user@outlook.com&pass=app.pw')
    obj1 = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj1, NotifyEmail) is True
    assert obj1.smtp_host == 'smtp.outlook.com'
    assert obj1.user == 'user@outlook.com'
    assert obj1.password == 'app.pw'
    assert obj1.secure_mode == 'starttls'
    assert obj1.port == 587

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj1.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == 'app.pw'
    assert user == 'user@outlook.com'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = NotifyEmail.parse_url(
        'mailtos://user:app.pw@outlook.com')
    obj2 = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj2, NotifyEmail) is True
    assert obj2.smtp_host == obj1.smtp_host
    assert obj2.user == obj1.user
    assert obj2.password == obj1.password
    assert obj2.secure_mode == obj1.secure_mode
    assert obj2.port == obj1.port

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj2.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == 'app.pw'
    assert user == 'user@outlook.com'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = NotifyEmail.parse_url(
        'mailtos://user:pass123@live.com')
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True
    # No entries in the reply_to
    assert not obj.reply_to

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == 'pass123'
    assert user == 'user@live.com'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = NotifyEmail.parse_url(
        'mailtos://user:pass123@hotmail.com')
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True
    # No entries in the reply_to
    assert not obj.reply_to

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == 'pass123'
    assert user == 'user@hotmail.com'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    #
    # Test Port Over-Riding
    #
    results = NotifyEmail.parse_url(
        "mailtos://abc:password@xyz.cn:465?"
        "smtp=smtp.exmail.qq.com&mode=ssl")
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    # Verify our over-rides are in place
    assert obj.smtp_host == 'smtp.exmail.qq.com'
    assert obj.port == 465
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == 'abc@xyz.cn'
    assert obj.secure_mode == 'ssl'
    # No entries in the reply_to
    assert not obj.reply_to

    # No from= used in the above
    assert re.match(r'.*from=.*', obj.url()) is None
    # No Our secure connection is SSL
    assert re.match(r'.*mode=ssl.*', obj.url()) is not None
    # No smtp= as the SMTP server is the same as the hostname in this case
    assert re.match(r'.*smtp=smtp.exmail.qq.com.*', obj.url()) is not None
    # URL is assembled based on provided user (:465 is dropped because it
    # is a default port when using xyz.cn)
    assert re.match(
        r'^mailtos://abc:password@xyz.cn/.*', obj.url()) is not None

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 1
    assert response.starttls.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == 'password'
    assert user == 'abc'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = NotifyEmail.parse_url(
        "mailtos://abc:password@xyz.cn?"
        "smtp=smtp.exmail.qq.com&mode=ssl&port=465")
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    # Verify our over-rides are in place
    assert obj.smtp_host == 'smtp.exmail.qq.com'
    assert obj.port == 465
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == 'abc@xyz.cn'
    assert obj.secure_mode == 'ssl'
    # No entries in the reply_to
    assert not obj.reply_to

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 1
    assert response.starttls.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == 'password'
    assert user == 'abc'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    #
    # Test Reply-To Email
    #
    results = NotifyEmail.parse_url(
        "mailtos://user:pass@example.com?reply=noreply@example.com")
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True
    # Verify our over-rides are in place
    assert obj.smtp_host == 'example.com'
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == 'user@example.com'
    assert obj.secure_mode == 'starttls'
    assert obj.url().startswith(
        'mailtos://user:pass@example.com')
    # Test that our template over-ride worked
    assert 'reply=noreply%40example.com' in obj.url()

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == 'pass'
    assert user == 'user'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    #
    # Test Reply-To Email with Name Inline
    #
    results = NotifyEmail.parse_url(
        "mailtos://user:pass@example.com?reply=Chris<noreply@example.ca>")
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True
    # Verify our over-rides are in place
    assert obj.smtp_host == 'example.com'
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == 'user@example.com'
    assert obj.secure_mode == 'starttls'
    assert obj.url().startswith(
        'mailtos://user:pass@example.com')
    # Test that our template over-ride worked
    assert 'reply=Chris+%3Cnoreply%40example.ca%3E' in obj.url()

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == 'pass'
    assert user == 'user'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    # Fast Mail Handling

    # Test variations of username required to be an email address
    # user@example.com; we also test an over-ride port on a template driven
    # mailto:// entry
    results = NotifyEmail.parse_url(
        'mailto://fastmail.com/?to=hello@concordium-explorer.nl'
        '&user=joe@mydomain.nl&pass=abc123'
        '&from=Concordium Explorer Bot<bot@concordium-explorer.nl>')
    assert isinstance(results, dict)
    assert 'Concordium Explorer Bot<bot@concordium-explorer.nl>' == \
        results['from_addr']
    assert 'joe@mydomain.nl' == results['user']
    assert results['port'] is None
    assert 'fastmail.com' == results['host']
    assert 'abc123' == results['password']
    assert 'hello@concordium-explorer.nl' in results['targets']

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 1
    assert response.starttls.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == 'bot@concordium-explorer.nl'
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == 'hello@concordium-explorer.nl'
    assert _msg.split('\n')[-3] == 'test'

    user, pw = response.login.call_args[0]
    assert pw == 'abc123'
    assert user == 'joe@mydomain.nl'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    # Issue github.com/caronc/apprise/issue/941

    # mail domain = mail-domain.com
    # host domain = domain.subdomain.com
    # PASSWORD needs to be fetched since a user= was provided
    #  - this is an edge case that is tested here
    results = NotifyEmail.parse_url(
        'mailtos://PASSWORD@domain.subdomain.com:587?'
        'user=admin@mail-domain.com&to=mail@mail-domain.com')
    assert isinstance(results, dict)
    # From_Addr could not be detected at this stage, but will be
    # handled during instantiation
    assert '' == results['from_addr']
    assert 'admin@mail-domain.com' == results['user']
    assert results['port'] == 587
    assert 'domain.subdomain.com' == results['host']
    assert 'PASSWORD' == results['password']
    assert 'mail@mail-domain.com' in results['targets']

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    # Not that our from_address takes on 'admin@domain.subdomain.com'
    assert obj.from_addr == ['Apprise', 'admin@domain.subdomain.com']

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert response.starttls.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == 'admin@domain.subdomain.com'
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == 'mail@mail-domain.com'
    assert _msg.split('\n')[-3] == 'test'

    user, pw = response.login.call_args[0]
    assert user == 'admin@mail-domain.com'
    assert pw == 'PASSWORD'


@mock.patch('smtplib.SMTP_SSL')
@mock.patch('smtplib.SMTP')
def test_plugin_email_plus_in_toemail(mock_smtp, mock_smtp_ssl):
    """
    NotifyEmail() support + in To Email address

    """

    response = mock.Mock()
    mock_smtp_ssl.return_value = response
    mock_smtp.return_value = response

    # We want to test the case where a + is found in the To address; we want to
    # ensure that it is supported
    results = NotifyEmail.parse_url(
        'mailtos://user:pass123@gmail.com'
        '?to=Plus Support<test+notification@gmail.com>')
    assert isinstance(results, dict)
    assert 'user' == results['user']
    assert 'gmail.com' == results['host']
    assert 'pass123' == results['password']
    assert results['port'] is None
    assert 'Plus Support<test+notification@gmail.com>' in results['targets']

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    assert len(obj.targets) == 1
    assert ('Plus Support', 'test+notification@gmail.com') in obj.targets

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == 'user@gmail.com'
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == 'test+notification@gmail.com'
    assert _msg.split('\n')[-3] == 'test'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    #
    # Perform the same test where the To field jsut contains the + in the
    # address
    #
    results = NotifyEmail.parse_url(
        'mailtos://user:pass123@gmail.com'
        '?to=test+notification@gmail.com')
    assert isinstance(results, dict)
    assert 'user' == results['user']
    assert 'gmail.com' == results['host']
    assert 'pass123' == results['password']
    assert results['port'] is None
    assert 'test+notification@gmail.com' in results['targets']

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    assert len(obj.targets) == 1
    assert (False, 'test+notification@gmail.com') in obj.targets

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == 'user@gmail.com'
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == 'test+notification@gmail.com'
    assert _msg.split('\n')[-3] == 'test'

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    #
    # Perform the same test where the To field is in the URL itself
    #
    results = NotifyEmail.parse_url(
        'mailtos://user:pass123@gmail.com'
        '/test+notification@gmail.com')
    assert isinstance(results, dict)
    assert 'user' == results['user']
    assert 'gmail.com' == results['host']
    assert 'pass123' == results['password']
    assert results['port'] is None
    assert 'test+notification@gmail.com' in results['targets']

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    assert len(obj.targets) == 1
    assert (False, 'test+notification@gmail.com') in obj.targets

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == 'user@gmail.com'
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == 'test+notification@gmail.com'
    assert _msg.split('\n')[-3] == 'test'


@mock.patch('smtplib.SMTP_SSL')
@mock.patch('smtplib.SMTP')
def test_plugin_email_formatting_990(mock_smtp, mock_smtp_ssl):
    """
    NotifyEmail() GitHub Issue 990
    https://github.com/caronc/apprise/issues/990
    Email formatting not working correctly

    """

    response = mock.Mock()
    mock_smtp_ssl.return_value = response
    mock_smtp.return_value = response

    results = NotifyEmail.parse_url(
        'mailtos://mydomain.com?smtp=mail.local.mydomain.com'
        '&user=noreply@mydomain.com&pass=mypassword'
        '&from=noreply@mydomain.com&to=me@mydomain.com&mode=ssl&port=465')

    assert isinstance(results, dict)
    assert 'noreply@mydomain.com' == results['user']
    assert 'mydomain.com' == results['host']
    assert 'mail.local.mydomain.com' == results['smtp_host']
    assert 'mypassword' == results['password']
    assert 'ssl' == results['secure_mode']
    assert '465' == results['port']
    assert 'me@mydomain.com' in results['targets']

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, NotifyEmail) is True

    assert len(obj.targets) == 1
    assert (False, 'me@mydomain.com') in obj.targets
