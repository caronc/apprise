# Apprise Development Tools

# Common Testing
This directory just contains some tools that are useful when developing with Apprise.  It is presumed that you've set yourself up with a working development environment before using the tools identified here:

```bash
# Using pip, setup a working development environment:
pip install -r dev-requirements.txt
```

The tools are as follows:

- :gear: `apprise`: This effectively acts as the `apprise` tool would once Apprise has been installed into your environment.  However `apprise` uses the branch you're working in.  So if you added a new Notification service, you can test with it as you would easily.  `apprise` takes all the same parameters as the `apprise` tool does.

    ```bash
    # simply make your code changes to apprise and test it out:
    ./bin/apprise -t title -b body \
          mailto://user:pass@example.com
    ```

- :gear: `test.sh`: This allows you to just run the unit tests associated with this project.  You can optionally specify a _keyword_ as a parameter and the unit tests will specifically focus on a single test.  This is useful when you need to debug something and don't want to run the entire fleet of tests each time.  e.g:

   ```bash
   # Run all tests:
   ./bin/test.sh

   # Run just the tests associated with the rest framework:
   ./bin/test.sh rest

   # Run just the Apprise config related unit tests
   ./bin/test.sh config
   ```

- :gear: `checkdone.sh`: This script just runs a lint check against the code to make sure there are no PEP8 issues and additionally runs a full test coverage report.  This is what will happen once you check in your code.  Nothing can be merged unless these tests pass with 100% coverage.  So it's useful to have this handy to run now and then.

   ```bash
   # Perform PEP8 and test coverage check on all code and reports
   # back. It's called 'checkdone' because it checks to see if you're
   # actually done with your code commit or not. :)
   ./bin/checkdone.sh
   ```

You can optionally just update your path to include this `./bin` directory and call the scripts that way as well. Hence:
```bash
# Update the path to include the bin directory:
export PATH="$(pwd)/bin:$PATH"

# Now you can call the scripts identified above from anywhere...
```

## RPM Testing

Apprise is also packaged for Redhat/Fedora as an RPM. To verify this process works correctly an additional tool called `build-rpm.sh` is provided.  It's best tested using the Docker environments:
   ```bash
   # To test with el9; do the following:
   docker-compose run --rm rpmbuild.el9 build-rpm.sh

   # To test with f39; do the following:
   docker-compose run --rm rpmbuild.f39 build-rpm.sh
   ```
