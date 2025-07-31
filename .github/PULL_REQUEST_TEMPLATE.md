## Description:
**Related issue (if applicable):** #<!--apprise issue number goes here-->

<!-- Have anything else to describe? Define it here; this helps build the wiki item later
  -- Delete this section if you are not creating a new plugin --

## *ServiceName* Notifications
* **Source**: https://official.website.example.ca
* **Icon Support**: Yes / No
* **Message Format**: Plain Text / HTML / Markdown
* **Message Limit**: nn Characters

Describe your service here..

### 🛠️ Setup Instructions

1. Visit [service.site](https://example.ca/) and sign in using your account credentials.
2. Once logged in, generate and copy your **token** ...

---

### ✅ Apprise Support

### Syntax

Valid syntax is as follows:
- `service://{variable}`

---

### 🔐 Parameter Breakdown

| Variable  | Required |  Description   |
|-----------|----------|----------------|
| variable1 | Yes      | Your variable1 |
| variable2 | No       | Your variable2 |

---

### 📦 Examples

Sends a simple example
```bash
apprise -vv -t "Title" -b "Message content" \
    service://token
```

## New Service Completion Status
<!-- This section is only applicable if you're adding a new service -->
* [ ] apprise/plugins/<!--new plugin name -->.py
* [ ] pypackage.toml update `keywords` section to identify our new service
    - add new service into this file (alphabetically).
* [ ] README.md
    - add entry for new service to table (as a quick reference)
* [ ] packaging/redhat/python-apprise.spec
    - add new service into the `%global common_description`

 -- END OF NEW PLUGIN SECTION - REMOVE ABOVE SECION IF NOT A NEW PLUGIN -->

## Checklist
<!-- The following must be completed or your PR can't be merged -->
* [ ] The code change is tested and works locally.
* [ ] There is no commented out code in this PR.
* [ ] No lint errors (use `tox -e lint` and even `tox -e format` to autofix what it can)
* [ ] Test coverage added (use `tox -e minimal`)

## Testing
<!-- If this your code is testable by other users of the program
     it would be really helpful to define this here -->
Anyone can help test this source code as follows:
```bash
# Create a virtual environment to work in as follows:
python3 -m venv apprise

# Change into our new directory
cd apprise

# Activate our virtual environment
source bin/activate

# Install the branch
pip install git+https://github.com/caronc/apprise.git@<this.branch-name>

# Test out the changes with the following command:
apprise -t "Test Title" -b "Test Message" \
  <apprise url related to ticket>

# If you have cloned the branch and have tox available to you
# the following can also allow you to test:
tox -e apprise -- -t "Test Title" -b "Test Message" \
          <apprise url related to ticket>
```
