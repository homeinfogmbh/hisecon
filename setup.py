#! /usr/bin/env python3

from distutils.core import setup


setup(
    name='hisecon',
    version='latest',
    author='Richard Neumann',
    package_dir={'': 'src'},
    py_modules=['hisecon'],
    data_files=[
        ('/etc/uwsgi/apps-available', [
            'src/hisecon.ini']),
        ('/usr/share', [
            'src/hisecon.wsgi'])],
    description='HOMEINFO Secure Contact form')
