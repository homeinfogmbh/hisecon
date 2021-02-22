"""Context locals."""

from flask import request
from werkzeug.local import LocalProxy

from configlib import loadcfg
from emaillib import Mailer

from hisecon.config import CONFIG
from hisecon.errors import error


__all__ = ['MAILER', 'SITE']


def load_mailer() -> Mailer:
    """Returns an appropriate mailer."""

    smtp = SITE.get('smtp', {})
    host = smtp.get('host', CONFIG.get('mail', 'HOST'))
    port = smtp.getint('port', CONFIG.getint('mail', 'PORT'))
    user = smtp.get('user', CONFIG.get('mail', 'USER'))
    passwd = smtp.get('passwd', CONFIG.get('mail', 'PASSWD'))
    ssl = smtp.get('ssl', True)
    return Mailer(host, port, user, passwd, ssl=ssl)


def load_site() -> dict:
    """Loads the site configuration JSON file."""

    try:
        config = request.json['config']
    except KeyError:
        raise error('No configuration provided.') from None

    try:
        return loadcfg('hisecon.json')[config]
    except KeyError:
        raise error(f'No such configuration: {config}', status=400) from None


MAILER = LocalProxy(load_mailer)
SITE = LocalProxy(load_site)
