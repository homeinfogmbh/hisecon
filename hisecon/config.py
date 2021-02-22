"""Configuration file parsing."""

from configparser import ConfigParser
from logging import getLogger
from pathlib import Path


__all__ = ['CONFIG', 'CONFIG_FILE', 'LOG_FORMAT', 'LOGGER']


CONFIG = ConfigParser()
CONFIG_FILE = Path('/usr/local/etc/hisecon.conf')
LOG_FORMAT = '[%(levelname)s] %(name)s: %(message)s'
LOGGER = getLogger('hisecon')
