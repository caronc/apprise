# -*- coding: utf-8 -*-
# A Conducto Pipeline
# Visit https://www.conducto.com for more information.
import os
import conducto as co
from inspect import cleandoc


def all_checks() -> co.Serial:
    """
    Define our Full Conducto Pipeline
    """
    # Dockerfile Context
    context = '.'

    # Shared Pipeline Directory
    share = '/conducto/data/pipeline/apprise'

    # The directory the project can be found in within the containers
    repo = '/apprise'

    # Unit Testing
    dockerfiles = (
        # Define our Containers
        ("Python 3.9", os.path.join('.conducto', 'Dockerfile.py39')),
        ("Python 3.8", os.path.join('.conducto', 'Dockerfile.py38')),
        ("Python 3.7", os.path.join('.conducto', 'Dockerfile.py37')),
        ("Python 3.6", os.path.join('.conducto', 'Dockerfile.py36')),
        ("Python 3.5", os.path.join('.conducto', 'Dockerfile.py35')),
        ("Python 2.7", os.path.join('.conducto', 'Dockerfile.py27')),
    )

    # Package Testing
    pkg_dockerfiles = (
        # Define our Containers
        ("EL8 RPM", os.path.join('.conducto', 'Dockerfile.el8')),
        ("EL7 RPM", os.path.join('.conducto', 'Dockerfile.el7')),
    )

    # find generated coverage filename and store it in the pipeline
    coverage_template = cleandoc('''
        pip install -r requirements.txt -r dev-requirements.txt || exit 1

        mkdir --verbose -p {share} && \\
           coverage run --parallel -m pytest && \\
             find . -mindepth 1 -maxdepth 1 -type f \\
                 -name '.coverage.*' \\
                 -exec mv --verbose -- {{}} {share} \;''')

    # pull generated file from the pipeline and place it back into
    # our working directory
    coverage_report_template = cleandoc('''
        pip install coverage || exit 1

        find {share} -mindepth 1 -maxdepth 1 -type f \\
            -name '.coverage.*' \\
            -exec mv --verbose -- {{}} . \;

        coverage combine . && \\
            coverage report --ignore-errors --skip-covered --show-missing

        # Push our coverage report to codecov.io
        retry=3
        iter=0
        while [ $iter -lt $retry ]; do
           bash <(curl -s https://codecov.io/bash) -Z
           [ $? -eq 0 ] && break
           sleep 1s
           # loop to try again
           let iter+=1
        done
    ''')

    # RPM Packaging Templates (assumes we're building as the user 'builder')
    rpm_pkg_template = cleandoc('''
        # copy our environment over
        rsync -a ./ /home/builder/

        # Permissions
        chmod ug+rw -R /home/builder
        chown -R builder /home/builder

        # Advance to our build directory
        cd /home/builder

        # Prepare Virtual Environment
        VENV_CMD="python3 -m venv"
        [ "$DIST" == "el7" ] && VENV_CMD=virtualenv

        sudo -u builder \\
            $VENV_CMD . && . bin/activate && \\
                pip install coverage babel wheel markdown && \\
                   python3 setup.py extract_messages && \\
                   python3 setup.py sdist

        # Build Man Page
        sudo -u builder \\
            ronn --roff packaging/man/apprise.md

        # Prepare RPM Package
        sudo -u builder \\
            find dist -type f -name '*.gz' \\
                -exec mv --verbose {{}} packaging/redhat/ \\;
        sudo -u builder \\
            find packaging/man -type f -name '*.1' \\
                -exec mv --verbose {{}} packaging/redhat/ \\;

        # Build Source RPM Package
        sudo -u builder \\
            rpmbuild -bs packaging/redhat/python-apprise.spec || exit 1

        # Install Missing RPM Dependencies
        if [ -x /usr/bin/dnf ]; then
            # EL8 and Newer
            dnf builddep -y rpm/*.rpm || exit 1
        else
            # EL7 Backwards Compatibility
            yum-builddep -y rpm/*.rpm || exit 1
        fi

        # Build our RPM using the environment we prepared
        sudo -u builder \\
            rpmbuild -bb packaging/redhat/python-apprise.spec''') \
        .format(repo=repo)

    # Define our default image keyword argument defaults
    image_kwargs = {
        'copy_repo': True,
        'path_map': {'.': repo},
    }

    # Our base image is always the first entry defined in our dockerfiles
    base_image = co.Image(
        dockerfile=dockerfiles[0][1], context=context, **image_kwargs)
    base_pkg_image = co.Image(
        dockerfile=pkg_dockerfiles[0][1], context=context, **image_kwargs)

    with co.Serial() as pipeline:
        with co.Parallel(name="Presentation"):
            # Code Styles
            co.Exec(
                'pip install flake8 && '
                'flake8 . --count --show-source --statistics',
                name="Style Guidelines", image=base_image)

            # RPM Checking
            co.Exec(
                cleandoc('''rpmlint --verbose -o "NetworkEnabled False" \\
                                packaging/redhat/python-apprise.spec'''),
                name="RPM Guidelines", image=base_pkg_image)

        with co.Parallel(name="Tests"):
            for entry in dockerfiles:
                name, dockerfile = entry

                # Prepare our Image
                image = co.Image(
                    dockerfile=dockerfile, context=context, **image_kwargs)

                # Unit Tests
                # These produce files that look like:
                # .coverage.{userid}.{hostname}.NNNNNN.NNNNNN where:
                #  - {userid} becomes the user that ran the test
                #  - {hostname} identifies the hostname it was built on
                #  - N gets replaced with a number

                # The idea here is that the .coverage.* file is unique
                # from others being built in other containers
                co.Exec(
                    coverage_template.format(share=share),
                    name="{} Coverage".format(name), image=image)

        # Coverage Reporting
        co.Exec(
            coverage_report_template.format(share=share),
            name="Test Code Coverage", image=base_image)

        with co.Parallel(name="Packaging"):
            for entry in pkg_dockerfiles:
                name, dockerfile = entry
                image = co.Image(
                    dockerfile=dockerfile, context=context, **image_kwargs)

                # Build our packages
                co.Exec(rpm_pkg_template, name=name, image=image)

    return pipeline


if __name__ == "__main__":
    """
    Execute our pipeline
    """
    exit(co.main(default=all_checks))
