"""HOMEINFO Secure Contact Form.

A secure and spam-resistant email backend.
"""

from contextlib import suppress
from functools import wraps
from logging import DEBUG, INFO, basicConfig, getLogger
from typing import Callable, Generator, NamedTuple, Union

from flask import request
from werkzeug.local import LocalProxy

from configlib import loadcfg
from emaillib import Mailer, EMail
from recaptcha import VerificationError, verify
from wsgilib import Error, Application, get_bool


__all__ = ['APPLICATION', 'CONFIG']


APPLICATION = Application('hisecon', debug=True, cors=True)
CONFIG = loadcfg('hisecon.conf')
LOG_FORMAT = '[%(levelname)s] %(name)s: %(message)s'
LOGGER = getLogger('hisecon')


class Attachment(NamedTuple):
    """Attachment format settings and values."""

    plain: Union[bool, str]
    html: Union[bool, str]


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
        return loadcfg('hisecon.json')[config]
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
    host = smtp.get('host', CONFIG.get('mail', 'HOST'))
    port = smtp.get('port', CONFIG.getint('mail', 'PORT'))
    user = smtp.get('user', CONFIG.get('mail', 'USER'))
    passwd = smtp.get('passwd', CONFIG.get('mail', 'PASSWD'))
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
def get_format() -> Attachment:
    """Returns the desired format."""

    try:
        frmt = request.args['format']
    except KeyError:
        plain = get_bool('text') or get_bool('plain')
        return Attachment(plain=plain, html=get_bool('html'))

    if frmt == 'html':
        return Attachment(plain=False, html=True)

    return Attachment(plain=True, html=False)


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


@debug('Body:\n\tText: %s\n\tHTML: %s', getter=lambda tpl: tpl)
def get_body() -> Attachment:
    """Returns the emails plain text and HTML bodies."""

    plain, html = get_format()
    # XXX: This is a hack until all clients send
    # data with correct "Content-Type" settings.
    text = request.get_data(as_text=True)
    html = text if html else None
    plain = text.replace('<br>', '\n') if plain else None
    return Attachment(plain=plain, html=html)


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
