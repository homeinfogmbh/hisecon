#! /usr/bin/env python3
"""WSGI main program for HOMEINFO Secure Contact form"""

from wsgilib import WsgiApp
from fancylog import LogLevel
from hisecon import Hisecon

application = WsgiApp(Hisecon, cors=True, log_level=LogLevel.SUCCESS)
