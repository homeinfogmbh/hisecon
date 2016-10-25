#! /usr/bin/env python3

from distutils.core import setup
from homeinfo.lib.misc import GitInfo


version, author, author_email, *_ = GitInfo()


setup(
    name='hisecon',
    version=version,
    author=author,
    author_email=author_email,
    requires=['homeinfo.lib'],
    package_dir={'homeinfo': 'src'},
    py_modules=['homeinfo.hisecon'],
    data_files=[
        ('/etc/uwsgi/apps-available', [
            'src/hisecon.ini']),
        ('/usr/share', [
            'src/hisecon.wsgi'])],
    description='HOMEINFO Secure Contact form')
