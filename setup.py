#! /usr/bin/env python3

from distutils.core import setup


setup(
    name='hisecon',
    version='latest',
    author='Richard Neumann',
    package_dir={'': 'src'},
    py_modules=['hisecon'],
    scripts=['files/hisecond'],
    data_files=[('/usr/lib/systemd/system', ['files/hisecon.service'])],
    description='HOMEINFO Secure Contact form')
