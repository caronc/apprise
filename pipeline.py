# -*- coding: utf-8 -*-
# A Conducto Pipeline
# Visit https://www.conducto.com for more information.
import os
import conducto as co
from inspect import cleandoc


def pipeline() -> co.Serial:
    """
    Define our Full Conducto Pipeline
    """
    # Dockerfile Context
    context = '.'

    # Shared Pipeline Directory
    share = '/conducto/data/pipeline/apprise'

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
        mkdir --verbose -p {share} && \\
           coverage run --parallel -m pytest && \\
             find . -mindepth 1 -maxdepth 1 -type f \\
                 -name '.coverage.*' \\
                 -exec mv --verbose -- {{}} {share} \;''')

    # pull generated file from the pipeline and place it back into
    # our working directory
    coverage_report_template = cleandoc('''
        find {share} -mindepth 1 -maxdepth 1 -type f \\
            -name '.coverage.*' \\
            -exec mv --verbose -- {{}} . \;

        coverage combine . && \\
            coverage report --ignore-errors --skip-covered --show-missing''')

    # Package Templates
    rpm_pkg_template = cleandoc('''
        sudo -u builder \\
            rpmbuild -bb packaging/redhat/python-apprise.spec''')

    # Our base image is always the first entry defined in our dockerfiles
    base_image = co.Image(dockerfile=dockerfiles[0][1], context=context)
    base_pkg_image = \
        co.Image(dockerfile=pkg_dockerfiles[0][1], context=context)

    with co.Serial() as pipeline:
        with co.Parallel(name="Presentation"):
            # Code Styles
            co.Exec(
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
                image = co.Image(dockerfile=dockerfile, context=context)
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
                image = co.Image(dockerfile=dockerfile, context=context)

                # Build our packages
                co.Exec(rpm_pkg_template, name=name, image=image)

    return pipeline


if __name__ == "__main__":
    """
    Execute our pipeline
    """
    exit(co.main(default=pipeline))
