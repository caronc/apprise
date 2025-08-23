# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

import json

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseConfig, NotifyType
from apprise.plugins.msteams import NotifyMSTeams

logging.disable(logging.CRITICAL)

# a test UUID we can use
UUID4 = "8b799edf-6f98-4d3a-9be7-2862fb4e5752"

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyMSTeams
    ##################################
    (
        "msteams://",
        {
            # First API Token not specified
            "instance": TypeError,
        },
    ),
    (
        "msteams://:@/",
        {
            # We don't have strict host checking on for msteams, so this URL
            # actually becomes parseable and :@ becomes a hostname.
            # The below errors because a second token wasn't found
            "instance": TypeError,
        },
    ),
    (
        f"msteams://{UUID4}",
        {
            # Just half of one token 1 provided
            "instance": TypeError,
        },
    ),
    (
        f"msteams://{UUID4}@{UUID4}/",
        {
            # Just 1 tokens provided
            "instance": TypeError,
        },
    ),
    (
        "msteams://{}@{}/{}".format(UUID4, UUID4, "a" * 32),
        {
            # Just 2 tokens provided
            "instance": TypeError,
        },
    ),
    (
        "msteams://{}@{}/{}/{}?t1".format(UUID4, UUID4, "b" * 32, UUID4),
        {
            # All tokens provided - we're good
            "instance": NotifyMSTeams,
        },
    ),
    # Support native URLs
    (
        "https://outlook.office.com/webhook/{}@{}/IncomingWebhook/{}/{}"
        .format(UUID4, UUID4, "k" * 32, UUID4),
        {
            # All tokens provided - we're good
            "instance": NotifyMSTeams,
            # Our expected url(privacy=True) startswith() response (v1 format)
            "privacy_url": "msteams://8...2/k...k/8...2/",
        },
    ),
    # Support New Native URLs
    (
        "https://myteam.webhook.office.com/webhookb2/{}@{}/IncomingWebhook/{}/{}"
        .format(UUID4, UUID4, "m" * 32, UUID4),
        {
            # All tokens provided - we're good
            "instance": NotifyMSTeams,
            # Our expected url(privacy=True) startswith() response (v2 format):
            "privacy_url": "msteams://myteam/8...2/m...m/8...2/",
        },
    ),
    # Support Newer Native URLs with 4 tokens, introduced in 2025
    (
        "https://myteam.webhook.office.com/webhookb2/{}@{}/IncomingWebhook/{}/{}"
        "/{}".format(UUID4, UUID4, "m" * 32, UUID4, "V2-_" + "n" * 43),
        {
            # All tokens provided - we're good
            "instance": NotifyMSTeams,
            # Our expected url(privacy=True) startswith() response (v2 format):
            "privacy_url": "msteams://myteam/8...2/m...m/8...2/V...n",
        },
    ),
    # Legacy URL Formatting
    (
        "msteams://{}@{}/{}/{}?t2".format(UUID4, UUID4, "c" * 32, UUID4),
        {
            # All tokens provided - we're good
            "instance": NotifyMSTeams,
            # don't include an image by default
            "include_image": False,
        },
    ),
    # Legacy URL Formatting
    (
        "msteams://{}@{}/{}/{}?image=No".format(UUID4, UUID4, "d" * 32, UUID4),
        {
            # All tokens provided - we're good  no image
            "instance": NotifyMSTeams,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "msteams://8...2/d...d/8...2/",
        },
    ),
    # New 2021 URL formatting
    (
        "msteams://apprise/{}@{}/{}/{}".format(UUID4, UUID4, "e" * 32, UUID4),
        {
            # All tokens provided - we're good  no image
            "instance": NotifyMSTeams,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "msteams://apprise/8...2/e...e/8...2/",
        },
    ),
    # New 2021 URL formatting; support team= argument
    (
        "msteams://{}@{}/{}/{}?team=teamname".format(
            UUID4, UUID4, "f" * 32, UUID4
        ),
        {
            # All tokens provided - we're good  no image
            "instance": NotifyMSTeams,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "msteams://teamname/8...2/f...f/8...2/",
        },
    ),
    # New 2021 URL formatting (forcing v1)
    (
        "msteams://apprise/{}@{}/{}/{}?version=1".format(
            UUID4, UUID4, "e" * 32, UUID4
        ),
        {
            # All tokens provided - we're good
            "instance": NotifyMSTeams,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "msteams://8...2/e...e/8...2/",
        },
    ),
    # Invalid versioning
    (
        "msteams://apprise/{}@{}/{}/{}?version=999".format(
            UUID4, UUID4, "e" * 32, UUID4
        ),
        {
            # invalid version
            "instance": TypeError,
        },
    ),
    (
        "msteams://apprise/{}@{}/{}/{}?version=invalid".format(
            UUID4, UUID4, "e" * 32, UUID4
        ),
        {
            # invalid version
            "instance": TypeError,
        },
    ),
    (
        "msteams://{}@{}/{}/{}?tx".format(UUID4, UUID4, "x" * 32, UUID4),
        {
            "instance": NotifyMSTeams,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "msteams://{}@{}/{}/{}?ty".format(UUID4, UUID4, "y" * 32, UUID4),
        {
            "instance": NotifyMSTeams,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "msteams://{}@{}/{}/{}?ta".format(UUID4, UUID4, "z" * 32, UUID4),
        {
            "instance": NotifyMSTeams,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_msteams_urls():
    """NotifyMSTeams() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@pytest.fixture
def msteams_url():
    return "msteams://{}@{}/{}/{}".format(UUID4, UUID4, "a" * 32, UUID4)


@pytest.fixture
def request_mock(mocker):
    """Prepare requests mock."""
    mock_post = mocker.patch("requests.post")
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    return mock_post


@pytest.fixture
def simple_template(tmpdir):
    template = tmpdir.join("simple.json")
    template.write("""
    {
      "@type": "MessageCard",
      "@context": "https://schema.org/extensions",
      "summary": "{{name}}",
      "themeColor": "{{app_color}}",
      "sections": [
        {
          "activityImage": null,
          "activityTitle": "{{title}}",
          "text": "{{body}}"
        }
      ]
    }
    """)
    return template


def test_plugin_msteams_templating_basic_success(
    request_mock, msteams_url, tmpdir
):
    """
    NotifyMSTeams() Templating - success.
    Test cases where URL and JSON is valid.
    """

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
    obj = Apprise.instantiate(
        "{url}/?template={template}&{kwargs}".format(
            url=msteams_url,
            template=str(template),
            kwargs=":key1=token&:key2=token",
        )
    )

    assert isinstance(obj, NotifyMSTeams)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        "https://outlook.office.com/webhook/"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "summary" in posted_json
    assert posted_json["summary"] == "Apprise"
    assert posted_json["themeColor"] == "#3AA3E3"
    assert posted_json["sections"][0]["activityTitle"] == "title"
    assert posted_json["sections"][0]["text"] == "body"


def test_plugin_msteams_templating_invalid_json(
    request_mock, msteams_url, tmpdir
):
    """
    NotifyMSTeams() Templating - invalid JSON.
    """

    template = tmpdir.join("invalid.json")
    template.write("}")

    # Instantiate our URL
    obj = Apprise.instantiate(
        "{url}/?template={template}&{kwargs}".format(
            url=msteams_url,
            template=str(template),
            kwargs=":key1=token&:key2=token",
        )
    )

    assert isinstance(obj, NotifyMSTeams)
    # We will fail to preform our notifcation because the JSON is bad
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )


def test_plugin_msteams_templating_json_missing_type(
    request_mock, msteams_url, tmpdir
):
    """
    NotifyMSTeams() Templating - invalid JSON.
    Test case where we're missing the @type part of the URL.
    """

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
    obj = Apprise.instantiate(
        "{url}/?template={template}&{kwargs}".format(
            url=msteams_url,
            template=str(template),
            kwargs=":key1=token&:key2=token",
        )
    )

    assert isinstance(obj, NotifyMSTeams)

    # We can not load the file because we're missing the @type entry
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )


def test_plugin_msteams_templating_json_missing_context(
    request_mock, msteams_url, tmpdir
):
    """
    NotifyMSTeams() Templating - invalid JSON.
    Test cases where we're missing the @context part of the URL.
    """

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
    obj = Apprise.instantiate(
        "{url}/?template={template}&{kwargs}".format(
            url=msteams_url,
            template=str(template),
            kwargs=":key1=token&:key2=token",
        )
    )
    assert isinstance(obj, NotifyMSTeams)

    # We can not load the file because we're missing the @context entry
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )


def test_plugin_msteams_templating_load_json_failure(
    request_mock, msteams_url, tmpdir
):
    """
    NotifyMSTeams() Templating - template loading failure.
    Test a case where we can not access the file.
    """

    template = tmpdir.join("empty.json")
    template.write("")

    obj = Apprise.instantiate(f"{msteams_url}/?template={template!s}")

    with mock.patch("json.loads", side_effect=OSError):
        # we fail, but this time it's because we couldn't
        # access the cached file contents for reading
        assert (
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
            is False
        )


def test_plugin_msteams_templating_target_success(
    request_mock, msteams_url, tmpdir
):
    """
    NotifyMSTeams() Templating - success with target.
    A more complicated example; uses a target.
    """

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
    obj = Apprise.instantiate(
        "{url}/?template={template}&{kwargs}".format(
            url=msteams_url,
            template=str(template),
            kwargs=":key1=token&:key2=token&:target=http://localhost",
        )
    )

    assert isinstance(obj, NotifyMSTeams)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        "https://outlook.office.com/webhook/"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "summary" in posted_json
    assert posted_json["summary"] == "Apprise Notifications"
    assert posted_json["themeColor"] == "#3AA3E3"
    assert posted_json["sections"][0]["activityTitle"] == "title"
    assert posted_json["sections"][0]["text"] == "body"

    # We even parsed our entry out of the URL
    assert (
        posted_json["potentialAction"][0]["actions"][0]["target"]
        == "http://localhost"
    )


def test_msteams_yaml_config_invalid_template_filename(
    request_mock, msteams_url, simple_template, tmpdir
):
    """
    NotifyMSTeams() YAML Configuration Entries - invalid template filename.
    """

    config = tmpdir.join("msteams01.yml")
    config.write(f"""
    urls:
      - {msteams_url}:
        - tag: 'msteams'
          template:  {simple_template!s}.missing
          :name: 'Template.Missing'
          :body: 'test body'
          :title: 'test title'
    """)

    cfg = AppriseConfig()
    cfg.add(str(config))
    assert len(cfg) == 1
    assert len(cfg[0]) == 1

    obj = cfg[0][0]
    assert isinstance(obj, NotifyMSTeams)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )
    assert request_mock.called is False


def test_msteams_yaml_config_token_identifiers(
    request_mock, msteams_url, simple_template, tmpdir
):
    """
    NotifyMSTeams() YAML Configuration Entries - test token identifiers.
    """

    config = tmpdir.join("msteams01.yml")
    config.write(f"""
    urls:
      - {msteams_url}:
        - tag: 'msteams'
          template:  {simple_template!s}
          :name: 'Testing'
          :body: 'test body'
          :title: 'test title'
    """)

    cfg = AppriseConfig()
    cfg.add(str(config))
    assert len(cfg) == 1
    assert len(cfg[0]) == 1

    obj = cfg[0][0]
    assert isinstance(obj, NotifyMSTeams)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        "https://outlook.office.com/webhook/"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "summary" in posted_json
    assert posted_json["summary"] == "Testing"
    assert posted_json["themeColor"] == "#3AA3E3"
    assert posted_json["sections"][0]["activityTitle"] == "test title"
    assert posted_json["sections"][0]["text"] == "test body"


def test_msteams_yaml_config_no_bullet_under_url_1(
    request_mock, msteams_url, simple_template, tmpdir
):
    """
    NotifyMSTeams() YAML Configuration Entries - no bullet 1.
    Now again but without a bullet under the url definition.
    """

    config = tmpdir.join("msteams02.yml")
    config.write(f"""
    urls:
      - {msteams_url}:
          tag: 'msteams'
          template:  {simple_template!s}
          :name: 'Testing2'
          :body: 'test body2'
          :title: 'test title2'
    """)

    cfg = AppriseConfig()
    cfg.add(str(config))
    assert len(cfg) == 1
    assert len(cfg[0]) == 1

    obj = cfg[0][0]
    assert isinstance(obj, NotifyMSTeams)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        "https://outlook.office.com/webhook/"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "summary" in posted_json
    assert posted_json["summary"] == "Testing2"
    assert posted_json["themeColor"] == "#3AA3E3"
    assert posted_json["sections"][0]["activityTitle"] == "test title2"
    assert posted_json["sections"][0]["text"] == "test body2"


def test_msteams_yaml_config_dictionary_file(
    request_mock, msteams_url, simple_template, tmpdir
):
    """NotifyMSTeams() YAML Configuration Entries.

    Try again but store the content as a dictionary in the configuration file.
    """

    config = tmpdir.join("msteams03.yml")
    config.write(f"""
    urls:
      - {msteams_url}:
        - tag: 'msteams'
          template:  {simple_template!s}
          tokens:
            name: 'Testing3'
            body: 'test body3'
            title: 'test title3'
    """)

    cfg = AppriseConfig()
    cfg.add(str(config))
    assert len(cfg) == 1
    assert len(cfg[0]) == 1

    obj = cfg[0][0]
    assert isinstance(obj, NotifyMSTeams)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        "https://outlook.office.com/webhook/"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "summary" in posted_json
    assert posted_json["summary"] == "Testing3"
    assert posted_json["themeColor"] == "#3AA3E3"
    assert posted_json["sections"][0]["activityTitle"] == "test title3"
    assert posted_json["sections"][0]["text"] == "test body3"


def test_msteams_yaml_config_no_bullet_under_url_2(
    request_mock, msteams_url, simple_template, tmpdir
):
    """
    NotifyMSTeams() YAML Configuration Entries - no bullet 2.
    Now again but without a bullet under the url definition.
    """

    config = tmpdir.join("msteams04.yml")
    config.write(f"""
    urls:
      - {msteams_url}:
          tag: 'msteams'
          template:  {simple_template!s}
          tokens:
            name: 'Testing4'
            body: 'test body4'
            title: 'test title4'
    """)

    cfg = AppriseConfig()
    cfg.add(str(config))
    assert len(cfg) == 1
    assert len(cfg[0]) == 1

    obj = cfg[0][0]
    assert isinstance(obj, NotifyMSTeams)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        "https://outlook.office.com/webhook/"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "summary" in posted_json
    assert posted_json["summary"] == "Testing4"
    assert posted_json["themeColor"] == "#3AA3E3"
    assert posted_json["sections"][0]["activityTitle"] == "test title4"
    assert posted_json["sections"][0]["text"] == "test body4"


def test_msteams_yaml_config_combined(
    request_mock, msteams_url, simple_template, tmpdir
):
    """NotifyMSTeams() YAML Configuration Entries.

    Now let's do a combination of the two.
    """

    config = tmpdir.join("msteams05.yml")
    config.write(f"""
    urls:
      - {msteams_url}:
        - tag: 'msteams'
          template:  {simple_template!s}
          tokens:
              body: 'test body5'
              title: 'test title5'
          :name: 'Testing5'
    """)

    cfg = AppriseConfig()
    cfg.add(str(config))
    assert len(cfg) == 1
    assert len(cfg[0]) == 1

    obj = cfg[0][0]
    assert isinstance(obj, NotifyMSTeams)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        "https://outlook.office.com/webhook/"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "summary" in posted_json
    assert posted_json["summary"] == "Testing5"
    assert posted_json["themeColor"] == "#3AA3E3"
    assert posted_json["sections"][0]["activityTitle"] == "test title5"
    assert posted_json["sections"][0]["text"] == "test body5"


def test_msteams_yaml_config_token_mismatch(
    request_mock, msteams_url, simple_template, tmpdir
):
    """NotifyMSTeams() YAML Configuration Entries.

    Now let's do a test where our tokens is not the expected dictionary we want
    to see.
    """

    config = tmpdir.join("msteams06.yml")
    config.write(f"""
    urls:
      - {msteams_url}:
        - tag: 'msteams'
          template:  {simple_template!s}
          # Not a dictionary
          tokens:
            body
    """)

    cfg = AppriseConfig()
    cfg.add(str(config))
    assert len(cfg) == 1

    # It could not load because of invalid tokens
    assert len(cfg[0]) == 0


def test_plugin_msteams_edge_cases():
    """NotifyMSTeams() Edge Cases."""
    # Initializes the plugin with an invalid token
    with pytest.raises(TypeError):
        NotifyMSTeams(token_a=None, token_b="abcd", token_c="abcd")
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyMSTeams(token_a="  ", token_b="abcd", token_c="abcd")

    with pytest.raises(TypeError):
        NotifyMSTeams(token_a="abcd", token_b=None, token_c="abcd")
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyMSTeams(token_a="abcd", token_b="  ", token_c="abcd")

    with pytest.raises(TypeError):
        NotifyMSTeams(token_a="abcd", token_b="abcd", token_c=None)
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyMSTeams(token_a="abcd", token_b="abcd", token_c="  ")

    uuid4 = "8b799edf-6f98-4d3a-9be7-2862fb4e5752"
    token_a = f"{uuid4}@{uuid4}"
    token_b = "A" * 32
    # test case where no tokens are specified
    obj = NotifyMSTeams(token_a=token_a, token_b=token_b, token_c=uuid4)
    assert isinstance(obj, NotifyMSTeams)
