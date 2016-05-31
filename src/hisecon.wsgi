#! /usr/bin/env python3
"""WSGI main program for HOMEINFO Secure Contact form"""

from homeinfo.hisecon import Hisecon

application = Hisecon()
