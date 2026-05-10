# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
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

from inspect import cleandoc
import json

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseConfig, NotifyType
from apprise.plugins.workflows import NotifyWorkflows

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyWorkflows
    ##################################
    (
        "workflow://",
        {
            # invalid host details (parsing fails very early)
            "instance": None,
        },
    ),
    (
        "workflow://:@/",
        {
            # invalid host details (parsing fails very early)
            "instance": None,
        },
    ),
    (
        "workflow://host/workflow",
        {
            # workflow provided only, no signature
            "instance": TypeError,
        },
    ),
    (
        "workflow://host:443/^(/signature",
        {
            # invalid workflow provided
            "instance": TypeError,
        },
    ),
    (
        "workflow://host:443/workflow1a/signature/?image=no",
        {
            # All tokens provided - we're good
            # Tests case without image defined
            "instance": NotifyWorkflows,
        },
    ),
    (
        "workflows://host:443/workflow1b/signature/",
        {
            # support workflows (s added to end)
            "instance": NotifyWorkflows,
        },
    ),
    (
        "workflows://host:443/signature/?id=workflow1c",
        {
            # id= to store workflow id
            "instance": NotifyWorkflows,
        },
    ),
    (
        "workflows://host:443/signature/?workflow=workflow1d&wrap=yes",
        {
            # workflow= to store workflow id
            "instance": NotifyWorkflows,
        },
    ),
    (
        "workflows://host:443/signature/?workflow=workflow1d&wrap=no",
        {
            # workflow= to store workflow id
            "instance": NotifyWorkflows,
        },
    ),
    (
        "workflows://host:443/workflow1e/signature/?api-version=2024-01-01",
        {
            # support api-version which is extracted from webhook
            "instance": NotifyWorkflows,
            # Our expected url(privacy=True) startswith() response
            "privacy_url": "workflow://host:443/w...e/s...e/",
        },
    ),
    (
        "workflows://host:443/workflow1b/signature/?ver=2016-06-01",
        {
            # Support ver= (api-version alias)
            "instance": NotifyWorkflows,
        },
    ),
    (
        "workflows://host:443/?id=workflow1b&signature=signature",
        {
            # Support signature= (sig= alias)
            "instance": NotifyWorkflows,
            # Our expected url(privacy=True) startswith() response
            "privacy_url": "workflow://host:443/w...b/s...e/",
        },
    ),
    (
        "workflows://host:443/workflow1e/signature/?powerautomate=yes",
        {
            # support power_automate flag
            "instance": NotifyWorkflows,
        },
    ),
    (
        "workflows://host:443/workflow1e/signature/?pa=yes&ver=1995-01-01",
        {
            # support power_automate flag with ver flag
            "instance": NotifyWorkflows,
        },
    ),
    (
        "workflows://host:443/workflow1e/signature/?pa=yes",
        {
            # support power_automate flag
            "instance": NotifyWorkflows,
        },
    ),
    # Support native URLs
    (
        (
            "https://server.azure.com:443/workflows/643e69f83c8944/"
            "triggers/manual/paths/invoke?"
            "api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&"
            "sv=1.0&sig=KODuebWbDGYFr0z0eu"
        ),
        {
            # All tokens provided - we're good
            "instance": NotifyWorkflows,
            # Our expected url(privacy=True) startswith() response
            "privacy_url": "workflow://server.azure.com:443/6...4/K...u/",
        },
    ),
    (
        (
            "https://server.azure.com:443/"
            "powerautomate/automations/direct/"
            "workflows/643e69f83c8944/"
            "triggers/manual/paths/invoke?"
            "api-version=2022-03-01-preview&sp=%2Ftriggers%2Fmanual%2Frun&"
            "sv=1.0&sig=KODuebWbDGYFr0z0eu"
        ),
        {
            # Power-Automate alternative URL - All tokens provided - we're good
            "instance": NotifyWorkflows,
        },
    ),
    (
        "workflow://host:443/workflow2/signature/",
        {
            "instance": NotifyWorkflows,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "workflow://host:443/workflow3/signature/",
        {
            "instance": NotifyWorkflows,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "workflow://host:443/workflow4/signature/",
        {
            "instance": NotifyWorkflows,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_workflows_urls():
    """NotifyWorkflows() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@pytest.fixture
def workflows_url():
    return "workflow://host:443/workflow/signature"


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
    template.write(
        cleandoc("""
    {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": null,
            "content": {
                "$schema":
                    "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "msteams": { "width": "full" },
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "**Test**",
                        "style": "heading"
                    }
                ]
            }
        }]
    }
    """)
    )
    return template


def test_plugin_workflows_simple_test(
    request_mock,
    workflows_url,
):
    """
    NotifyWorkflows() simple testing
    """
    # Instantiate our URL
    obj = Apprise.instantiate(workflows_url)
    assert isinstance(obj, NotifyWorkflows)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        "https://host:443/workflows/workflow/triggers/manual/paths/invoke"
    )
    payload = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "NotifyType." not in request_mock.call_args_list[0][1]["data"]
    assert payload == {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Image",
                            "url": "https://github.com/caronc/apprise/raw/"
                            "master/apprise/assets/themes/default/"
                            "apprise-info-32x32.png",
                            "height": "32px",
                            "altText": NotifyType.INFO.value,
                        },
                        {
                            "type": "TextBlock",
                            # Verify our Title is set
                            "text": "title",
                            "style": "heading",
                            "weight": "Bolder",
                            "size": "Large",
                            "id": "title",
                        },
                        {
                            "type": "TextBlock",
                            # Verify our Body is set
                            "text": "body",
                            "style": "default",
                            "wrap": True,
                            "id": "body",
                        },
                    ],
                    "msteams": {"width": "full"},
                },
            },
        ],
    }

    request_mock.reset_mock()

    # Instantiate our URL
    obj = Apprise.instantiate(f"{workflows_url}?pa=yes")
    assert isinstance(obj, NotifyWorkflows)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        "https://host:443/powerautomate/automations/direct/"
        "workflows/workflow/triggers/manual/paths/invoke"
    )
    payload = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "NotifyType." not in request_mock.call_args_list[0][1]["data"]

    assert payload == {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/"
                    "adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Image",
                            "url": "https://github.com/caronc/apprise/raw/"
                            "master/apprise/assets/themes/default/"
                            "apprise-info-32x32.png",
                            "height": "32px",
                            "altText": "info",
                        },
                        {
                            "type": "TextBlock",
                            # Verify our Title is set
                            "text": "title",
                            "style": "heading",
                            "weight": "Bolder",
                            "size": "Large",
                            "id": "title",
                        },
                        {
                            "type": "TextBlock",
                            # Verify our Body is set
                            "text": "body",
                            "style": "default",
                            "wrap": True,
                            "id": "body",
                        },
                    ],
                    "msteams": {
                        "width": "full",
                    },
                },
            },
        ],
    }


def test_plugin_workflows_templating_basic_success(
    request_mock, workflows_url, tmpdir
):
    """
    NotifyWorkflows() Templating - success.
    Test cases where URL and JSON is valid.
    """

    template = tmpdir.join("simple.json")
    template.write(
        cleandoc("""
    {
      "type": "message",
      "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive",
        "contentUrl": null,
        "content": {
          "$schema":
            "http://adaptivecards.io/schemas/adaptive-card.json",
          "type": "AdaptiveCard",
          "version": "1.4",
          "body": [
            {"type": "TextBlock", "id": "app_id", "text": "{{app_id}}"},
            {"type": "TextBlock", "id": "color", "text": "{{app_color}}"},
            {"type": "TextBlock", "id": "title", "text": "{{app_title}}"},
            {"type": "TextBlock", "id": "body", "text": "{{app_body}}"}
          ]
        }
      }]
    }
    """)
    )

    # Instantiate our URL
    obj = Apprise.instantiate(
        "{url}/?template={template}&{kwargs}".format(
            url=workflows_url,
            template=str(template),
            kwargs=":key1=token&:key2=token",
        )
    )

    assert isinstance(obj, NotifyWorkflows)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        "https://host:443/workflows/workflow/triggers/manual/paths/invoke"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "NotifyType." not in request_mock.call_args_list[0][1]["data"]
    # Verify the Adaptive Card envelope
    assert posted_json["type"] == "message"
    content = posted_json["attachments"][0]["content"]
    # Index body blocks by their id for easy lookup
    blocks = {b["id"]: b["text"] for b in content["body"] if "id" in b}
    assert blocks["app_id"] == "Apprise"
    assert blocks["color"] == "#3AA3E3"
    assert blocks["title"] == "title"
    assert blocks["body"] == "body"


def test_plugin_workflows_templating_invalid_json(
    request_mock, workflows_url, tmpdir
):
    """
    NotifyWorkflows() Templating - invalid JSON.
    """

    template = tmpdir.join("invalid.json")
    template.write("}")

    # Instantiate our URL
    obj = Apprise.instantiate(
        "{url}/?template={template}&{kwargs}".format(
            url=workflows_url,
            template=str(template),
            kwargs=":key1=token&:key2=token",
        )
    )

    assert isinstance(obj, NotifyWorkflows)
    # We will fail to preform our notifcation because the JSON is bad
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )


def test_plugin_workflows_templating_load_json_failure(
    request_mock, workflows_url, tmpdir
):
    """
    NotifyWorkflows() Templating - template loading failure.
    Test a case where we can not access the file.
    """

    template = tmpdir.join("empty.json")
    template.write("")

    obj = Apprise.instantiate(f"{workflows_url}/?template={template!s}")

    with mock.patch("json.loads", side_effect=OSError):
        # we fail, but this time it's because we couldn't
        # access the cached file contents for reading
        assert (
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
            is False
        )


def test_plugin_workflows_templating_target_success(
    request_mock, workflows_url, tmpdir
):
    """
    NotifyWorkflows() Templating - success with target.
    A more complicated example; uses a custom token.
    """

    template = tmpdir.join("more_complicated_example.json")
    template.write(
        cleandoc("""
    {
      "type": "message",
      "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive",
        "contentUrl": null,
        "content": {
          "$schema":
            "http://adaptivecards.io/schemas/adaptive-card.json",
          "type": "AdaptiveCard",
          "version": "1.4",
          "body": [
            {"type": "TextBlock", "id": "desc", "text": "{{app_desc}}"},
            {"type": "TextBlock", "id": "color", "text": "{{app_color}}"},
            {"type": "TextBlock", "id": "title", "text": "{{app_title}}"},
            {"type": "TextBlock", "id": "body", "text": "{{app_body}}"}
          ],
          "actions": [
            {
              "type": "Action.OpenUrl",
              "title": "Open",
              "url": "{{ target }}"
            }
          ]
        }
      }]
    }
    """)
    )

    # Instantiate our URL
    obj = Apprise.instantiate(
        "{url}/?template={template}&{kwargs}".format(
            url=workflows_url,
            template=str(template),
            kwargs=":key1=token&:key2=token&:target=http://localhost",
        )
    )

    assert isinstance(obj, NotifyWorkflows)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        "https://host:443/workflows/workflow/triggers/manual/paths/invoke"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "NotifyType." not in request_mock.call_args_list[0][1]["data"]
    # Verify the Adaptive Card envelope
    assert posted_json["type"] == "message"
    content = posted_json["attachments"][0]["content"]
    # Index body blocks by their id for easy lookup
    blocks = {b["id"]: b["text"] for b in content["body"] if "id" in b}
    assert blocks["desc"] == "Apprise Notifications"
    assert blocks["color"] == "#3AA3E3"
    assert blocks["title"] == "title"
    assert blocks["body"] == "body"
    # The custom :target token must be substituted into the action URL
    assert content["actions"][0]["url"] == "http://localhost"


def test_plugin_workflows_templating_invalid_type(
    request_mock, workflows_url, tmpdir
):
    """NotifyWorkflows() Templating - root 'type' != 'message' is rejected."""

    template = tmpdir.join("bad_type.json")
    template.write(
        cleandoc("""
    {
      "type": "wrongtype",
      "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive",
        "contentUrl": null,
        "content": {}
      }]
    }
    """)
    )

    obj = Apprise.instantiate(f"{workflows_url}/?template={template!s}")
    assert isinstance(obj, NotifyWorkflows)
    # Validation rejects incorrect 'type' value
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )
    assert request_mock.called is False


def test_plugin_workflows_templating_missing_attachments(
    request_mock, workflows_url, tmpdir
):
    """NotifyWorkflows() Templating - absent or empty attachments fails."""

    template = tmpdir.join("no_attachments.json")

    # Missing 'attachments' key entirely
    template.write('{"type": "message"}')
    obj = Apprise.instantiate(f"{workflows_url}/?template={template!s}")
    assert isinstance(obj, NotifyWorkflows)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )
    assert request_mock.called is False

    # Empty list is also rejected
    template.write('{"type": "message", "attachments": []}')
    obj2 = Apprise.instantiate(f"{workflows_url}/?template={template!s}")
    assert isinstance(obj2, NotifyWorkflows)
    assert (
        obj2.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )
    assert request_mock.called is False


def test_plugin_workflows_templating_invalid_contenttype(
    request_mock, workflows_url, tmpdir
):
    """NotifyWorkflows() Templating - attachment missing contentType fails."""

    template = tmpdir.join("no_contenttype.json")
    template.write('{"type": "message", "attachments": [{"content": {}}]}')

    obj = Apprise.instantiate(f"{workflows_url}/?template={template!s}")
    assert isinstance(obj, NotifyWorkflows)
    # An attachment without a 'contentType' string is rejected
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )
    assert request_mock.called is False


def test_plugin_workflows_template_add_failure():
    """NotifyWorkflows() - TypeError when add() drops the entry."""
    # Simulate add() silently failing (len stays 0); no HTTP call needed
    with mock.patch("apprise.plugins.workflows.AppriseAttachment") as mock_cls:
        inst = mock.MagicMock()
        inst.__len__ = mock.Mock(return_value=0)
        mock_cls.return_value = inst

        with pytest.raises(TypeError):
            NotifyWorkflows(
                workflow="T00000000001",
                signature="AbCdEfGhIjKlMnOpQrStUvWx",
                template="file:///some/template.json",
            )


def test_plugin_workflows_templating_content_not_dict(workflows_url, tmpdir):
    """NotifyWorkflows() Templating - template that parses to a JSON
    array is rejected cleanly."""
    # Valid JSON but a list rather than an object; no HTTP call is made
    template = tmpdir.join("array.json")
    template.write('[{"type": "message"}]')

    obj = Apprise.instantiate(f"{workflows_url}/?template={template!s}")
    assert isinstance(obj, NotifyWorkflows)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )


def test_plugin_workflows_templating_attachment_not_dict(
    workflows_url, tmpdir
):
    """NotifyWorkflows() Templating - non-dict in attachments rejected."""
    # attachments list contains a string rather than a dict; no HTTP call made
    template = tmpdir.join("bad_attach.json")
    template.write('{"type": "message", "attachments": ["not-a-dict"]}')

    obj = Apprise.instantiate(f"{workflows_url}/?template={template!s}")
    assert isinstance(obj, NotifyWorkflows)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )


def test_plugin_workflows_templating_none_token_value(
    request_mock, workflows_url, tmpdir
):
    """NotifyWorkflows() Templating - None token value (e.g. app_image_url)
    is coerced to empty string before JSON-escaping."""
    # Template references app_image_url which will be None when
    # include_image=False; old code produced corrupted JSON ("ul" from None)
    template = tmpdir.join("img_ref.json")
    template.write(
        '{"type": "message", "attachments": [{'
        '"contentType": "application/vnd.microsoft.card.adaptive",'
        '"content": {"body": [{"type": "TextBlock",'
        '"text": "{{app_body}} img={{app_image_url}}"}]}}]}'
    )

    # image=no forces app_image_url to None, exercising the None->""
    # coercion in safe_tokens
    obj = Apprise.instantiate(
        f"{workflows_url}/?image=no&template={template!s}"
    )
    assert isinstance(obj, NotifyWorkflows)
    # Must succeed -- None coerced to "" keeps the JSON valid
    assert (
        obj.notify(body="hello", title="t", notify_type=NotifyType.INFO)
        is True
    )
    assert request_mock.called is True
    posted_data = json.loads(request_mock.call_args_list[0][1]["data"])
    body_text = posted_data["attachments"][0]["content"]["body"][0]["text"]
    # app_image_url should expand to "" not "ul"
    assert "img=" in body_text
    assert "ul" not in body_text


def test_workflows_yaml_config_missing_template_filename(
    request_mock, workflows_url, simple_template, tmpdir
):
    """
    NotifyWorkflows() YAML Configuration Entries - Missing template reference.
    """

    config = tmpdir.join("workflow01.yml")
    config.write(
        cleandoc(f"""
    urls:
      - {workflows_url}:
        - tag: 'workflow'
          template: {simple_template!s}.missing
          :name: 'Template.Missing'
          :body: 'test body'
          :title: 'test title'
    """)
    )

    # Config still loads okay
    cfg = AppriseConfig()
    cfg.add(str(config))
    assert len(cfg) == 1
    assert len(cfg[0]) == 1

    obj = cfg[0][0]
    assert isinstance(obj, NotifyWorkflows)

    # However we can't send notification since the template couldn't be loaded
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )
    assert request_mock.called is False


def test_plugin_workflows_edge_cases():
    """NotifyWorkflows() Edge Cases."""
    # Initializes the plugin with an invalid token
    with pytest.raises(TypeError):
        NotifyWorkflows(workflow="@", signature="@")
    with pytest.raises(TypeError):
        NotifyWorkflows(workflow="", signature="abcd")

    with pytest.raises(TypeError):
        NotifyWorkflows(workflow=None, signature="abcd")
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyWorkflows(workflow="  ", signature="abcd")

    with pytest.raises(TypeError):
        NotifyWorkflows(workflow="abcd", signature=None)
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyWorkflows(workflow="abcd", signature="  ")

    # test case where invalid tokens are specified
    with pytest.raises(TypeError):
        NotifyWorkflows(
            workflow="workflow", signature="signature", tokens="not-a-dict"
        )

    # test case where no tokens are specified
    obj = NotifyWorkflows(workflow="workflow", signature="signature")
    assert isinstance(obj, NotifyWorkflows)


def test_plugin_workflows_azure_webhooks(request_mock):
    """NotifyWorkflows() Azure Webhooks."""
    url = (
        "https://prod-15.uksouth.logic.azure.com:443"
        "/workflows/3XXX5/triggers/manual/paths/invoke"
        "?api-version=2016-06-01&"
        "sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=iXXXU"
    )

    #
    # Initialize
    #
    obj = Apprise.instantiate(url)
    assert isinstance(obj, NotifyWorkflows)
    assert obj.workflow == "3XXX5"
    assert obj.signature == "iXXXU"
    assert obj.api_version == "2016-06-01"
