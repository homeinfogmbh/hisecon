#! /usr/bin/env python3
"""Install script."""

from setuptools import setup


setup(
    name='hisecon',
    use_scm_version={
        "local_scheme": "node-and-timestamp"
    },
    setup_requires=['setuptools_scm'],
    author='HOMEINFO - Digitale Informationssysteme GmbH',
    author_email='<info at homeinfo dot de>',
    maintainer='Richard Neumann',
    maintainer_email='<r dot neumann at homeinfo period de>',
    install_requires=[
        'configlib',
        'emaillib',
        'flask',
        'recaptcha',
        'werkzeug',
        'wsgilib'
    ],
    packages=['hisecon'],
    description='HOMEINFO Secure Contact form'
)
