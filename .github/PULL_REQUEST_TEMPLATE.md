## Description
**Related issue (if applicable):** #<!-- apprise issue number goes here -->

<!--
  -- Have anything else to describe?
  -- Define it here; this helps build the documentation site later
-->

<!-- START OF NEW PLUGIN SECTION
  -- Delete this section if you are not creating a new plugin --

## *ServiceName* Notifications
* **Source**: https://official.website.example.ca
* **Image Support**: Yes / No
* **Message Format**: Plain Text / HTML / Markdown
* **Message Limit**: nn characters

Describe your service here.

## Account Setup
1. Visit the service portal and sign in using your account credentials.
2. Generate and copy your token, key, or credentials.

## Syntax

Valid syntax is as follows:
- `service://{variable}`

## Parameter Breakdown

| Variable  | Required |  Description   |
|-----------|----------|----------------|
| variable1 | Yes      | Your variable1 |
| variable2 | No       | Your variable2 |

## Examples

Sends a simple example:
```bash
apprise -vv -t "Title" -b "Message content" \
    service://token
```

## New Service Completion Status
* [ ] apprise/plugins/--new_plugin_name.py
* [ ] pyproject.toml
    - Update keywords section to identify the new service (alphabetically).
* [ ] README.md
    - Add entry for the new service (quick reference only).
* [ ] packaging/redhat/python-apprise.spec
    - add new service into the `%global common_description`

END OF NEW PLUGIN SECTION -->

<!-- The following must be completed or your PR cannot be merged -->
## Checklist
* [ ] Documentation ticket created (if applicable):** [apprise-docs/##](https://github.com/caronc/apprise-docs/issue/<!--apprise-docs issue number goes here-->)
* [ ] The change is tested and works locally.
* [ ] No commented-out code in this PR.
* [ ] No lint errors (use `tox -e lint` and optionally `tox -e format`).
* [ ] Test coverage added or updated (use `tox -e minimal`).

## Testing
<!-- If your change is testable by others, define how to validate it here -->
Anyone can help test as follows:
```bash
# Create a virtual environment
python3 -m venv apprise

# Change into our new directory
cd apprise

# Activate our virtual environment
source bin/activate

# Install the branch
pip install git+https://github.com/caronc/apprise.git@<this.branch-name>

# If you have cloned the branch and have tox available to you:
tox -e apprise -- -t "Test Title" -b "Test Message" \
    <apprise url related to this change>
```
