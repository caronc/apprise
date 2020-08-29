# Apprise Development

This directory just contains some tools that are useful when developing with Apprise.  The tools are as follows:

- `apprise`: This effectively acts as the `apprise` tool would once Apprise has been installed into your environment.  However `apprise` uses the branch you're working in.  So if you added a new Notification service, you can test with it as you would easily.  `apprise` takes all the same parameters as the `apprise` tool does.

    ```bash
    # simply make your code changes to apprise and test it out:
    ./bin/apprise -t title -m message \
          mailto://user:pass@example.com
    ```

- `test.sh`: This allows you to just run the unit tests associated with this project.  You can optionally specify a _keyword_ as a parameter and the unit tests will specifically focus on a single test.  This is useful when you need to debug something and don't want to run the entire fleet of tests each time.  e.g:

   ```bash
   # Run all tests:
   ./bin/tests.sh

   # Run just the tests associated with the rest framework:
   ./bin/tests.sh rest

   # Run just the Apprise config related unit tests
   ./bin/tests.sh config
   ```

- `checkdone.sh`: This script just runs a lint check against the code to make sure there are no PEP8 issues and additionally runs a full test coverage report.  This is what will happen once you check in your code.  Nothing can be merged unless these tests pass with 100% coverage.  So it's useful to have this handy to run now and then.

   ```bash
   # Perform PEP8 and test coverage check on all code and reports
   # back. It's called 'checkdone' because it checks to see if you're
   # actually done with your code commit or not. :)
   ./bin/checkdone.sh
   ```