"""HOMEINFO Secure Contact Form.

A secure and spam-resistant email backend.
"""

from contextlib import suppress
from functools import wraps
from logging import DEBUG, INFO, basicConfig, getLogger
from typing import Callable, Generator, Tuple, Union

from flask import request
from werkzeug.local import LocalProxy

from configlib import load_ini, load_json
from emaillib import Mailer, EMail
from recaptcha import VerificationError, verify
from wsgilib import Error, Application


__all__ = ['CONFIG', 'JSON', 'APPLICATION']


APPLICATION = Application('hisecon', debug=True, cors=True)
CONFIG = load_ini('hisecon.conf')
JSON = load_json('hisecon.json')
LOG_FORMAT = '[%(levelname)s] %(name)s: %(message)s'
LOGGER = getLogger('hisecon')


def debug(template: str, getter: Callable = lambda value: [value]) -> Callable:
    """Debug logs return value."""

    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            result = function(*args, **kwargs)
            LOGGER.debug(template, *getter(result))
            return result

        return wrapper

    return decorator


def _error(message: str, *, status: int = 400) -> Error:
    """Logs an error message and returns an Error."""

    LOGGER.error(message)
    return Error(message, status=status)


def _load_site() -> dict:
    """Loads the site configuration JSON file."""

    try:
        config = request.args['config']
    except KeyError:
        raise _error('No configuration provided.') from None

    try:
        return JSON[config]
    except KeyError:
        raise _error(f'No such configuration: {config}', status=400) from None


SITE = LocalProxy(_load_site)


def _load_secret() -> str:
    """Loads the respective ReCAPTCHA secret."""

    try:
        return SITE['secret']
    except KeyError:
        raise _error('No secret specified.', status=500) from None


def _load_mailer() -> Mailer:
    """Returns an appropriate mailer."""

    smtp = SITE.get('smtp', {})
    host = smtp.get('host', CONFIG['mail']['HOST'])
    port = smtp.get('port', int(CONFIG['mail']['PORT']))
    user = smtp.get('user', CONFIG['mail']['USER'])
    passwd = smtp.get('passwd', CONFIG['mail']['PASSWD'])
    ssl = smtp.get('ssl', True)
    return Mailer(host, port, user, passwd, ssl=ssl)


MAILER = LocalProxy(_load_mailer)


@debug('reCAPTCHA response: %s')
def get_response() -> str:
    """Returns the respective reCAPTCHA response."""

    try:
        return request.args['response']
    except KeyError:
        raise _error('No reCAPTCHA response provided.') from None


@debug('Format: %s')
def get_format() -> str:
    """Returns the desired format."""

    try:
        return request.args['format']
    except KeyError:
        html = request.args.get('html')

        if html or html == '':
            return 'html'

        return 'text'


def get_recipients() -> Generator[str, None, None]:
    """Yields all recipients."""

    yield from SITE.get('recipients', ())

    with suppress(KeyError):
        yield request.args['recipient']

    recipients = request.args.get('recipients')

    if recipients:
        yield from filter(None, map(str.strip, recipients.split(',')))

    with suppress(KeyError):
        yield request.args['issuer']


@debug('Subject: %s')
def get_subject() -> str:
    """Returns the respective subject."""

    try:
        return request.args['subject']
    except KeyError:
        raise _error('No subject provided', status=400) from None


@debug('Sender: %s')
def get_sender() -> str:
    """Returns the specified sender's email address."""

    try:
        return SITE['smtp']['from']
    except KeyError:
        return CONFIG['mail']['from']


@debug('Body:\n\tHTML: %s\n\tText: %s', getter=lambda tpl: tpl)
def get_body() -> Tuple[Union[str, None], Union[str, None]]:
    """Returns the emails plain text and HTML bodies."""

    format = get_format()   # pylint: disable=W0622
    # XXX: This is a hack until all clients send
    # data with correct "Content-Type" settings.
    text = request.get_data(as_text=True)

    if format == 'html':
        LOGGER.info('Email format is: HTML.')
        return (None, text)

    if format == 'json':
        LOGGER.info('Email format is: JSON.')
        return (None, text)

    if format != 'text':
        LOGGER.warning('Unknown format. Defaulting to plain text.')

    LOGGER.info('Email format is: plain text.')
    return (text.replace('<br>', '\n'), None)


def get_emails() -> Generator[EMail, None, None]:
    """Actually sends emails"""

    subject, sender = get_subject(), get_sender()
    plain, html = get_body()

    if not plain and not html:
        raise Error('No message body provided.')

    for recipient in get_recipients():
        LOGGER.debug('Recipient: %s', recipient)
        email = EMail(subject, sender, recipient, plain=plain, html=html)
        reply_to = request.args.get('reply_to')

        if reply_to:
            email.add_header('reply-to', reply_to)

        yield email


@APPLICATION.before_first_request
def init_logger():
    """Initializes the logger."""

    debug_mode = CONFIG.getboolean('app', 'debug', fallback=False)
    basicConfig(level=DEBUG if debug_mode else INFO, format=LOG_FORMAT)


@APPLICATION.route('/', methods=['POST'])
def send_emails():
    """Sends emails.

    Required params:
        config=<configuration>
        response=<recaptcha_response>
        subject=<email_subject>

    Optional params:
        recipient=<recipient> (deprecated)
        recipients=<recipeint>[,<recipient>...]
        remoteip=<remote_ip>
        issuer=<issuer>
        html (deprecated)
        format=(html,text,json) (new)
    """
    remote_ip = request.args.get('remoteip')

    try:
        verify(_load_secret(), get_response(), remote_ip=remote_ip)
    except VerificationError:
        return _error('reCAPTCHA check failed.')

    emails = tuple(get_emails())
    LOGGER.debug('Got emails: %s', emails)

    if not emails:
        return _error('No recipients specified.', status=400)

    if MAILER.send(emails):
        LOGGER.debug('Emails sent.')
        return 'Emails sent.'

    return ('Could not send (all) emails.', 500)
