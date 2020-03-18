## Description:
**Related issue (if applicable):** #<!--apprise issue number goes here-->

<!-- Have anything else to describe? Define it here -->

## New Service Completion Status
<!-- This section is only applicable if you're adding a new service -->
* [ ] apprise/plugins/Notify<!--ServiceName goes here-->.py
* [ ] setup.py
    - add new service into the `keywords` section of the `setup()` declaration
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
