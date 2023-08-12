# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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

import asyncio
import re
from functools import partial

from ..URLBase import URLBase
from ..common import NotifyType
from ..common import NOTIFY_TYPES
from ..common import NotifyFormat
from ..common import NOTIFY_FORMATS
from ..common import OverflowMode
from ..common import OVERFLOW_MODES
from ..AppriseLocale import gettext_lazy as _
from ..AppriseAttachment import AppriseAttachment


class NotifyBase(URLBase):
    """
    This is the base class for all notification services
    """

    # An internal flag used to test the state of the plugin. If set to
    # False, then the plugin is not used.  Plugins can disable themselves
    # due to enviroment issues (such as missing libraries, or platform
    # dependencies that are not present).  By default all plugins are
    # enabled.
    enabled = True

    # The category allows for parent inheritance of this object to alter
    # this when it's function/use is intended to behave differently. The
    # following category types exist:
    #
    #  native: Is a native plugin written/stored in `apprise/plugins/Notify*`
    #  custom: Is a custom plugin written/stored in a users plugin directory
    #          that they loaded at execution time.
    category = 'native'

    # Some plugins may require additional packages above what is provided
    # already by Apprise.
    #
    # Use this section to relay this information to the users of the script to
    # help guide them with what they need to know if they plan on using your
    # plugin.   The below configuration should otherwise accomodate all normal
    # situations and will not requrie any updating:
    requirements = {
        # Use the description to provide a human interpretable description of
        # what is required to make the plugin work. This is only nessisary
        # if there are package dependencies.  Setting this to default will
        # cause a general response to be returned.  Only set this if you plan
        # on over-riding the default.  Always consider language support here.
        # So before providing a value do the following in your code base:
        #
        #  from apprise.AppriseLocale import gettext_lazy as _
        #
        # 'details': _('My detailed requirements')
        'details': None,

        # Define any required packages needed for the plugin to run.  This is
        # an array of strings that simply look like lines residing in a
        # `requirements.txt` file...
        #
        # As an example, an entry may look like:
        # 'packages_required': [
        #   'cryptography < 3.4`,
        # ]
        'packages_required': [],

        # Recommended packages identify packages that are not required to make
        # your plugin work, but would improve it's use or grant it access to
        # full functionality (that might otherwise be limited).

        # Similar to `packages_required`, you would identify each entry in
        # the array as you would in a `requirements.txt` file.
        #
        #   - Do not re-provide entries already in the `packages_required`
        'packages_recommended': [],
    }

    # The services URL
    service_url = None

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = None

    # Most Servers do not like more then 1 request per 5 seconds, so 5.5 gives
    # us a safe play range. Override the one defined already in the URLBase
    request_rate_per_sec = 5.5

    # Allows the user to specify the NotifyImageSize object
    image_size = None

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 32768

    # Defines the maximum allowable characters in the title; set this to zero
    # if a title can't be used. Titles that are not used but are defined are
    # automatically placed into the body
    title_maxlen = 250

    # Set the maximum line count; if this is set to anything larger then zero
    # the message (prior to it being sent) will be truncated to this number
    # of lines. Setting this to zero disables this feature.
    body_max_line_count = 0

    # Default Notify Format
    notify_format = NotifyFormat.TEXT

    # Default Overflow Mode
    overflow_mode = OverflowMode.UPSTREAM

    # Support Attachments; this defaults to being disabled.
    # Since apprise allows you to send attachments without a body or title
    # defined, by letting Apprise know the plugin won't support attachments
    # up front, it can quickly pass over and ignore calls to these end points.

    # You must set this to true if your application can handle attachments.
    # You must also consider a flow change to your notification if this is set
    # to True as well as now there will be cases where both the body and title
    # may not be set.  There will never be a case where a body, or attachment
    # isn't set in the same call to your notify() function.
    attachment_support = False

    # Default Title HTML Tagging
    # When a title is specified for a notification service that doesn't accept
    # titles, by default apprise tries to give a plesant view and convert the
    # title so that it can be placed into the body. The default is to just
    # use a <b> tag.  The below causes the <b>title</b> to get generated:
    default_html_tag_id = 'b'

    # Here is where we define all of the arguments we accept on the url
    # such as: schema://whatever/?overflow=upstream&format=text
    # These act the same way as tokens except they are optional and/or
    # have default values set if mandatory. This rule must be followed
    template_args = dict(URLBase.template_args, **{
        'overflow': {
            'name': _('Overflow Mode'),
            'type': 'choice:string',
            'values': OVERFLOW_MODES,
            # Provide a default
            'default': overflow_mode,
            # look up default using the following parent class value at
            # runtime. The variable name identified here (in this case
            # overflow_mode) is checked and it's result is placed over-top of
            # the 'default'. This is done because once a parent class inherits
            # this one, the overflow_mode already set as a default 'could' be
            # potentially over-ridden and changed to a different value.
            '_lookup_default': 'overflow_mode',
        },
        'format': {
            'name': _('Notify Format'),
            'type': 'choice:string',
            'values': NOTIFY_FORMATS,
            # Provide a default
            'default': notify_format,
            # look up default using the following parent class value at
            # runtime.
            '_lookup_default': 'notify_format',
        },
    })

    def __init__(self, **kwargs):
        """
        Initialize some general configuration that will keep things consistent
        when working with the notifiers that will inherit this class.

        """

        super().__init__(**kwargs)

        if 'format' in kwargs:
            # Store the specified format if specified
            notify_format = kwargs.get('format', '')
            if notify_format.lower() not in NOTIFY_FORMATS:
                msg = 'Invalid notification format {}'.format(notify_format)
                self.logger.error(msg)
                raise TypeError(msg)

            # Provide override
            self.notify_format = notify_format

        if 'overflow' in kwargs:
            # Store the specified format if specified
            overflow = kwargs.get('overflow', '')
            if overflow.lower() not in OVERFLOW_MODES:
                msg = 'Invalid overflow method {}'.format(overflow)
                self.logger.error(msg)
                raise TypeError(msg)

            # Provide override
            self.overflow_mode = overflow

    def image_url(self, notify_type, logo=False, extension=None,
                  image_size=None):
        """
        Returns Image URL if possible
        """

        if not self.image_size:
            return None

        if notify_type not in NOTIFY_TYPES:
            return None

        return self.asset.image_url(
            notify_type=notify_type,
            image_size=self.image_size if image_size is None else image_size,
            logo=logo,
            extension=extension,
        )

    def image_path(self, notify_type, extension=None):
        """
        Returns the path of the image if it can
        """
        if not self.image_size:
            return None

        if notify_type not in NOTIFY_TYPES:
            return None

        return self.asset.image_path(
            notify_type=notify_type,
            image_size=self.image_size,
            extension=extension,
        )

    def image_raw(self, notify_type, extension=None):
        """
        Returns the raw image if it can
        """
        if not self.image_size:
            return None

        if notify_type not in NOTIFY_TYPES:
            return None

        return self.asset.image_raw(
            notify_type=notify_type,
            image_size=self.image_size,
            extension=extension,
        )

    def color(self, notify_type, color_type=None):
        """
        Returns the html color (hex code) associated with the notify_type
        """
        if notify_type not in NOTIFY_TYPES:
            return None

        return self.asset.color(
            notify_type=notify_type,
            color_type=color_type,
        )

    def notify(self, *args, **kwargs):
        """
        Performs notification
        """
        try:
            # Build a list of dictionaries that can be used to call send().
            send_calls = list(self._build_send_calls(*args, **kwargs))

        except TypeError:
            # Internal error
            return False

        else:
            # Loop through each call, one at a time. (Use a list rather than a
            # generator to call all the partials, even in case of a failure.)
            the_calls = [self.send(**kwargs2) for kwargs2 in send_calls]
            return all(the_calls)

    async def async_notify(self, *args, **kwargs):
        """
        Performs notification for asynchronous callers
        """
        try:
            # Build a list of dictionaries that can be used to call send().
            send_calls = list(self._build_send_calls(*args, **kwargs))

        except TypeError:
            # Internal error
            return False

        else:
            loop = asyncio.get_event_loop()

            # Wrap each call in a coroutine that uses the default executor.
            # TODO: In the future, allow plugins to supply a native
            # async_send() method.
            async def do_send(**kwargs2):
                send = partial(self.send, **kwargs2)
                result = await loop.run_in_executor(None, send)
                return result

            # gather() all calls in parallel.
            the_cors = (do_send(**kwargs2) for kwargs2 in send_calls)
            return all(await asyncio.gather(*the_cors))

    def _build_send_calls(self, body=None, title=None,
                          notify_type=NotifyType.INFO, overflow=None,
                          attach=None, body_format=None, **kwargs):
        """
        Get a list of dictionaries that can be used to call send() or
        (in the future) async_send().
        """

        if not self.enabled:
            # Deny notifications issued to services that are disabled
            msg = f"{self.service_name} is currently disabled on this system."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Prepare attachments if required
        if attach is not None and not isinstance(attach, AppriseAttachment):
            try:
                attach = AppriseAttachment(attach, asset=self.asset)

            except TypeError:
                # bad attachments
                raise

            # Handle situations where the body is None
            body = '' if not body else body

        elif not (body or attach):
            # If there is not an attachment at the very least, a body must be
            # present
            msg = "No message body or attachment was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        if not body and not self.attachment_support:
            # If no body was specified, then we know that an attachment
            # was.  This is logic checked earlier in the code.
            #
            # Knowing this, if the plugin itself doesn't support sending
            # attachments, there is nothing further to do here, just move
            # along.
            msg = f"{self.service_name} does not support attachments; " \
                " service skipped"
            self.logger.warning(msg)
            raise TypeError(msg)

        # Handle situations where the title is None
        title = '' if not title else title

        # Apply our overflow (if defined)
        for chunk in self._apply_overflow(
                body=body, title=title, overflow=overflow,
                body_format=body_format):

            # Send notification
            yield dict(
                body=chunk['body'], title=chunk['title'],
                notify_type=notify_type, attach=attach,
                body_format=body_format
            )

    def _apply_overflow(self, body, title=None, overflow=None,
                        body_format=None):
        """
        Takes the message body and title as input.  This function then
        applies any defined overflow restrictions associated with the
        notification service and may alter the message if/as required.

        The function will always return a list object in the following
        structure:
            [
                {
                    title: 'the title goes here',
                    body: 'the message body goes here',
                },
                {
                    title: 'the title goes here',
                    body: 'the message body goes here',
                },

            ]
        """

        response = list()

        # tidy
        title = '' if not title else title.strip()
        body = '' if not body else body.rstrip()

        if overflow is None:
            # default
            overflow = self.overflow_mode

        if self.title_maxlen <= 0 and len(title) > 0:

            if self.notify_format == NotifyFormat.HTML:
                # Content is appended to body as html
                body = '<{open_tag}>{title}</{close_tag}>' \
                    '<br />\r\n{body}'.format(
                        open_tag=self.default_html_tag_id,
                        title=title,
                        close_tag=self.default_html_tag_id,
                        body=body)

            elif self.notify_format == NotifyFormat.MARKDOWN and \
                    body_format == NotifyFormat.TEXT:
                # Content is appended to body as markdown
                title = title.lstrip('\r\n \t\v\f#-')
                if title:
                    # Content is appended to body as text
                    body = '# {}\r\n{}'.format(title, body)

            else:
                # Content is appended to body as text
                body = '{}\r\n{}'.format(title, body)

            title = ''

        # Enforce the line count first always
        if self.body_max_line_count > 0:
            # Limit results to just the first 2 line otherwise
            # there is just to much content to display
            body = re.split(r'\r*\n', body)
            body = '\r\n'.join(body[0:self.body_max_line_count])

        if overflow == OverflowMode.UPSTREAM:
            # Nothing more to do
            response.append({'body': body, 'title': title})
            return response

        elif len(title) > self.title_maxlen:
            # Truncate our Title
            title = title[:self.title_maxlen]

        if self.body_maxlen > 0 and len(body) <= self.body_maxlen:
            response.append({'body': body, 'title': title})
            return response

        if overflow == OverflowMode.TRUNCATE:
            # Truncate our body and return
            response.append({
                'body': body[:self.body_maxlen],
                'title': title,
            })
            # For truncate mode, we're done now
            return response

        # If we reach here, then we are in SPLIT mode.
        # For here, we want to split the message as many times as we have to
        # in order to fit it within the designated limits.
        response = [{
            'body': body[i: i + self.body_maxlen],
            'title': title} for i in range(0, len(body), self.body_maxlen)]

        return response

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Should preform the actual notification itself.

        """
        raise NotImplementedError(
            "send() is not implimented by the child class.")

    def url_parameters(self, *args, **kwargs):
        """
        Provides a default set of parameters to work with. This can greatly
        simplify URL construction in the acommpanied url() function in all
        defined plugin services.
        """

        params = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
        }

        params.update(super().url_parameters(*args, **kwargs))

        # return default parameters
        return params

    @staticmethod
    def parse_url(url, verify_host=True, plus_to_space=False):
        """Parses the URL and returns it broken apart into a dictionary.

        This is very specific and customized for Apprise.


        Args:
            url (str): The URL you want to fully parse.
            verify_host (:obj:`bool`, optional): a flag kept with the parsed
                 URL which some child classes will later use to verify SSL
                 keys (if SSL transactions take place).  Unless under very
                 specific circumstances, it is strongly recomended that
                 you leave this default value set to True.

        Returns:
            A dictionary is returned containing the URL fully parsed if
            successful, otherwise None is returned.
        """
        results = URLBase.parse_url(
            url, verify_host=verify_host, plus_to_space=plus_to_space)

        if not results:
            # We're done; we failed to parse our url
            return results

        # Allow overriding the default format
        if 'format' in results['qsd']:
            results['format'] = results['qsd'].get('format')
            if results['format'] not in NOTIFY_FORMATS:
                URLBase.logger.warning(
                    'Unsupported format specified {}'.format(
                        results['format']))
                del results['format']

        # Allow overriding the default overflow
        if 'overflow' in results['qsd']:
            results['overflow'] = results['qsd'].get('overflow')
            if results['overflow'] not in OVERFLOW_MODES:
                URLBase.logger.warning(
                    'Unsupported overflow specified {}'.format(
                        results['overflow']))
                del results['overflow']

        return results

    @staticmethod
    def parse_native_url(url):
        """
        This is a base class that can be optionally over-ridden by child
        classes who can build their Apprise URL based on the one provided
        by the notification service they choose to use.

        The intent of this is to make Apprise a little more userfriendly
        to people who aren't familiar with constructing URLs and wish to
        use the ones that were just provied by their notification serivice
        that they're using.

        This function will return None if the passed in URL can't be matched
        as belonging to the notification service. Otherwise this function
        should return the same set of results that parse_url() does.
        """
        return None
