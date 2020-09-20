# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

import mock
import json
import requests
from apprise import Apprise
from apprise import plugins
from apprise import NotifyType

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


@mock.patch('requests.post')
def test_msteams_templating(mock_post, tmpdir):
    """
    API: NotifyMSTeams() Templating

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    uuid4 = '8b799edf-6f98-4d3a-9be7-2862fb4e5752'
    url = 'msteams://{}@{}/{}/{}'.format(uuid4, uuid4, 'a' * 32, uuid4)

    # Test cases where our URL is invalid
    template = tmpdir.join("simple.json")
    template.write("""
    {
      "@type": "MessageCard",
      "@context": "https://schema.org/extensions",
      "summary": "{{app_id}}",
      "themeColor": "{{app_color}}",
      "sections": [
        {
          "activityImage": null,
          "activityTitle": "{{app_title}}",
          "text": "{{app_body}}"
        }
      ]
    }
    """)

    # Instantiate our URL
    obj = Apprise.instantiate('{url}/?template={template}&{kwargs}'.format(
        url=url,
        template=str(template),
        kwargs=':key1=token&:key2=token',
    ))

    assert isinstance(obj, plugins.NotifyMSTeams)
    assert obj.notify(
        body="body", title='title',
        notify_type=NotifyType.INFO) is True

    assert mock_post.called is True
    assert mock_post.call_args_list[0][0][0].startswith(
        'https://outlook.office.com/webhook/')

    # Our Posted JSON Object
    posted_json = json.loads(mock_post.call_args_list[0][1]['data'])
    assert 'summary' in posted_json
    assert posted_json['summary'] == 'Apprise'
    assert posted_json['themeColor'] == '#3AA3E3'
    assert posted_json['sections'][0]['activityTitle'] == 'title'
    assert posted_json['sections'][0]['text'] == 'body'

    # Test invalid JSON

    # Test cases where our URL is invalid
    template = tmpdir.join("invalid.json")
    template.write("}")

    # Instantiate our URL
    obj = Apprise.instantiate('{url}/?template={template}&{kwargs}'.format(
        url=url,
        template=str(template),
        kwargs=':key1=token&:key2=token',
    ))

    assert isinstance(obj, plugins.NotifyMSTeams)
    # We will fail to preform our notifcation because the JSON is bad
    assert obj.notify(
        body="body", title='title',
        notify_type=NotifyType.INFO) is False

    # Test cases where we're missing the @type part of the URL
    template = tmpdir.join("missing_type.json")
    template.write("""
    {
      "@context": "https://schema.org/extensions",
      "summary": "{{app_id}}",
      "themeColor": "{{app_color}}",
      "sections": [
        {
          "activityImage": null,
          "activityTitle": "{{app_title}}",
          "text": "{{app_body}}"
        }
      ]
    }
    """)

    # Instantiate our URL
    obj = Apprise.instantiate('{url}/?template={template}&{kwargs}'.format(
        url=url,
        template=str(template),
        kwargs=':key1=token&:key2=token',
    ))

    assert isinstance(obj, plugins.NotifyMSTeams)

    # We can not load the file because we're missing the @type entry
    assert obj.notify(
        body="body", title='title',
        notify_type=NotifyType.INFO) is False

    # Test cases where we're missing the @context part of the URL
    template = tmpdir.join("missing_context.json")
    template.write("""
    {
      "@type": "MessageCard",
      "summary": "{{app_id}}",
      "themeColor": "{{app_color}}",
      "sections": [
        {
          "activityImage": null,
          "activityTitle": "{{app_title}}",
          "text": "{{app_body}}"
        }
      ]
    }
    """)

    # Instantiate our URL
    obj = Apprise.instantiate('{url}/?template={template}&{kwargs}'.format(
        url=url,
        template=str(template),
        kwargs=':key1=token&:key2=token',
    ))

    assert isinstance(obj, plugins.NotifyMSTeams)
    # We can not load the file because we're missing the @context entry
    assert obj.notify(
        body="body", title='title',
        notify_type=NotifyType.INFO) is False

    # Test a case where we can not access the file:
    with mock.patch('json.loads', side_effect=OSError):
        # we fail, but this time it's because we couldn't
        # access the cached file contents for reading
        assert obj.notify(
            body="body", title='title',
            notify_type=NotifyType.INFO) is False

    # A more complicated example; uses a target
    mock_post.reset_mock()
    template = tmpdir.join("more_complicated_example.json")
    template.write("""
    {
      "@type": "MessageCard",
      "@context": "https://schema.org/extensions",
      "summary": "{{app_desc}}",
      "themeColor": "{{app_color}}",
      "sections": [
        {
          "activityImage": null,
          "activityTitle": "{{app_title}}",
          "text": "{{app_body}}"
        }
      ],
     "potentialAction": [{
        "@type": "ActionCard",
        "name": "Add a comment",
        "inputs": [{
            "@type": "TextInput",
            "id": "comment",
            "isMultiline": false,
            "title": "Add a comment here for this task."
        }],
        "actions": [{
            "@type": "HttpPOST",
            "name": "Add Comment",
            "target": "{{ target }}"
        }]
     }]
    }
    """)

    # Instantiate our URL
    obj = Apprise.instantiate('{url}/?template={template}&{kwargs}'.format(
        url=url,
        template=str(template),
        kwargs=':key1=token&:key2=token&:target=http://localhost',
    ))

    assert isinstance(obj, plugins.NotifyMSTeams)
    assert obj.notify(
        body="body", title='title',
        notify_type=NotifyType.INFO) is True

    assert mock_post.called is True
    assert mock_post.call_args_list[0][0][0].startswith(
        'https://outlook.office.com/webhook/')

    # Our Posted JSON Object
    posted_json = json.loads(mock_post.call_args_list[0][1]['data'])
    assert 'summary' in posted_json
    assert posted_json['summary'] == 'Apprise Notifications'
    assert posted_json['themeColor'] == '#3AA3E3'
    assert posted_json['sections'][0]['activityTitle'] == 'title'
    assert posted_json['sections'][0]['text'] == 'body'

    # We even parsed our entry out of the URL
    assert posted_json['potentialAction'][0]['actions'][0]['target'] \
        == 'http://localhost'
