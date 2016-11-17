#! /usr/bin/env python3
"""WSGI main program for HOMEINFO Secure Contact form"""

from homeinfo.lib.wsgi import WsgiApp
from homeinfo.hisecon import Hisecon

application = WsgiApp(Hisecon, cors=True)
