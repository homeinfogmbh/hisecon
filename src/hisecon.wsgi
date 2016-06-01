#! /usr/bin/env python3
"""WSGI main program for HOMEINFO Secure Contact form"""
from logging import DEBUG, INFO, basicConfig

from homeinfo.hisecon import Hisecon

basicConfig(level=DEBUG)

application = Hisecon()
