"""HISECON API globals."""

from contextlib import suppress
from functools import lru_cache
from json import load

from flask import request
from werkzeug.local import LocalProxy

from configlib import INIParser
from emaillib import Mailer, EMail
from recaptcha import ReCaptcha
from wsgilib import Error, PostData

__all__ = [
    'CONFIG',
    'ARGS',
    'RECAPTCHA',
    'RESPONSE',
    'MAILER',
    'EMAILS']


JSON = '/etc/hisecon.json'
CONFIG = INIParser('/etc/hisecon.conf', alert=True)


def _strip(string):
    """Strips the respective string."""

    return string.strip()


@lru_cache(maxsize=1)
def _load_sites():
    """Reads the sites configuration from the JSON file."""

    try:
        with open(JSON) as json:
            return load(json)
    except FileNotFoundError:
        raise Error('Sites file not found.', status=500)
    except PermissionError:
        raise Error('Sites file not readable.', status=500)
    except ValueError:
        raise Error('Corrupted sites file.', status=500)


def _load_site():
    """Loads the site configuration JSON file."""

    try:
        config = ARGS['config']
    except KeyError:
        raise Error('No configuration provided.')

    try:
        return _load_sites()[config]
    except KeyError:
        raise Error('No such configuration: "{}".'.format(config), status=400)


def _load_recaptcha():
    """Loads the respective ReCAPTCHA client."""

    try:
        return ReCaptcha(SITE['secret'])
    except KeyError:
        raise Error('No secret specified for configuration.', status=500)


def _load_response():
    """Returns the respective reCAPTCHA response."""

    try:
        return ARGS['response']
    except KeyError:
        raise Error('No reCAPTCHA response provided.')


def _load_format():
    """Returns the desired format."""

    try:
        return ARGS['format']
    except KeyError:
        if ARGS.get('html', False):
            return 'html'

        return 'text'


def _load_recipients():
    """Yields all recipients."""

    yield from SITE.get('recipients', ())

    with suppress(KeyError):
        yield from filter(None, map(_strip, ARGS['recipients'].split(',')))

    with suppress(KeyError):
        yield ARGS['issuer']


def _load_subject():
    """Returns the respective subject."""

    try:
        return ARGS['subject']
    except KeyError:
        raise Error('No subject provided', status=400)


def _load_sender():
    """Returns the specified sender's email address."""

    try:
        return SITE['smtp']['from']
    except KeyError:
        return CONFIG['mail']['from']

def _load_body():
    """Returns the emails plain text and HTML bodies."""

    if FORMAT == 'html':
        return PostData().text
    elif FORMAT == 'text':
        return PostData().text.replace('<br>', '\n')


def _load_mailer():
    """Returns an appropriate mailer."""

    smtp = SITE.get('smtp', {})
    host = smtp.get('host', CONFIG['mail']['HOST'])
    port = smtp.get('port', int(CONFIG['mail']['PORT']))
    user = smtp.get('user', CONFIG['mail']['USER'])
    passwd = smtp.get('passwd', CONFIG['mail']['PASSWD'])
    ssl = smtp.get('ssl', True)
    return Mailer(host, port, user, passwd, ssl=ssl)


def _load_emails():
    """Actually sends emails"""

    if FORMAT in ('html', 'json'):
        plain = None
        html = BODY
    else:
        plain = BODY
        html = None

    if not plain and not html:
        raise Error('No message body provided.')

    for recipient in RECIPIENTS:
        email = EMail(SUBJECT, SENDER, recipient, plain=plain, html=html)
        reply_to = ARGS.get('reply_to')

        if reply_to is not None:
            email.add_header('reply-to', reply_to)

        yield email


ARGS = LocalProxy(lambda: request.args)
SITE = LocalProxy(_load_site)
RECAPTCHA = LocalProxy(_load_recaptcha)
RESPONSE = LocalProxy(_load_response)
FORMAT = LocalProxy(_load_format)
RECIPIENTS = LocalProxy(_load_recipients)
SUBJECT = LocalProxy(_load_subject)
SENDER = LocalProxy(_load_sender)
BODY = LocalProxy(_load_body)
MAILER = LocalProxy(_load_mailer)
EMAILS = LocalProxy(_load_emails)
