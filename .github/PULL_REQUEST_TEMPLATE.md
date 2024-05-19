## Description:
**Related issue (if applicable):** #<!--apprise issue number goes here-->

<!-- Have anything else to describe? Define it here -->

## New Service Completion Status
<!-- This section is only applicable if you're adding a new service -->
* [ ] apprise/plugins/<!--new plugin name -->.py
* [ ] KEYWORDS
    - add new service into this file (alphabetically).
* [ ] README.md
    - add entry for new service to table (as a quick reference)
* [ ] packaging/redhat/python-apprise.spec
    - add new service into the `%global common_description`

## Checklist
<!-- The following must be completed or your PR can't be merged -->
* [ ] The code change is tested and works locally.
* [ ] There is no commented out code in this PR.
* [ ] No lint errors (use `flake8`)
* [ ] 100% test coverage

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

```

