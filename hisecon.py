"""HOMEINFO Secure Contact Form.

A secure and spam-resistent email backend.
"""

from contextlib import suppress
from smtplib import SMTPAuthenticationError, SMTPRecipientsRefused

from flask import request
from werkzeug.local import LocalProxy

from configlib import INIParser, JSONParser
from emaillib import Mailer, EMail
from recaptcha import VerificationError, ReCaptcha
from wsgilib import Error, Application


__all__ = ['CONFIG', 'JSON', 'APPLICATION']


CONFIG = INIParser('/etc/hisecon.conf', alert=True)
JSON = JSONParser('/etc/hisecon.json', alert=True)
APPLICATION = Application('hisecon', cors=True, debug=True)


def _load_site():
    """Loads the site configuration JSON file."""

    try:
        config = request.args['config']
    except KeyError:
        raise Error('No configuration provided.')

    try:
        return JSON[config]
    except KeyError:
        raise Error('No such configuration: "{}".'.format(config), status=400)


SITE = LocalProxy(_load_site)


def _load_recaptcha():
    """Loads the respective ReCAPTCHA client."""

    try:
        return ReCaptcha(SITE['secret'])
    except KeyError:
        raise Error('No secret specified for configuration.', status=500)


RECAPTCHA = LocalProxy(_load_recaptcha)


def _load_mailer():
    """Returns an appropriate mailer."""

    smtp = SITE.get('smtp', {})
    host = smtp.get('host', CONFIG['mail']['HOST'])
    port = smtp.get('port', int(CONFIG['mail']['PORT']))
    user = smtp.get('user', CONFIG['mail']['USER'])
    passwd = smtp.get('passwd', CONFIG['mail']['PASSWD'])
    ssl = smtp.get('ssl', True)
    return Mailer(host, port, user, passwd, ssl=ssl)


MAILER = LocalProxy(_load_mailer)


def get_response():
    """Returns the respective reCAPTCHA response."""

    try:
        return request.args['response']
    except KeyError:
        raise Error('No reCAPTCHA response provided.')


def get_format():
    """Returns the desired format."""

    try:
        return request.args['format']
    except KeyError:
        if request.args.get('html', False):
            return 'html'

        return 'text'


def get_recipients():
    """Yields all recipients."""

    yield from SITE.get('recipients', ())

    try:
        recipients = request.args['recipients']
    except KeyError:
        pass
    else:
        yield from filter(None, map(str.strip, recipients.rsplit(',')))

    with suppress(KeyError):
        yield request.args['issuer']


def get_subject():
    """Returns the respective subject."""

    try:
        return request.args['subject']
    except KeyError:
        raise Error('No subject provided', status=400)


def get_sender():
    """Returns the specified sender's email address."""

    try:
        return SITE['smtp']['from']
    except KeyError:
        return CONFIG['mail']['from']


def get_body():
    """Returns the emails plain text and HTML bodies."""

    # TODO: This is a hack until all clients send
    # data with correct "ContentType" settings.
    text = request.get_data(as_text=True)

    if get_format() == 'text':
        return text.replace('<br>', '\n')

    return text


def get_emails():
    """Actually sends emails"""

    if get_format() in ('html', 'json'):
        plain = None
        html = get_body()
    else:
        plain = get_body()
        html = None

    if not plain and not html:
        raise Error('No message body provided.')

    for recipient in get_recipients():
        email = EMail(
            get_subject(), get_sender(), recipient, plain=plain, html=html)
        reply_to = request.args.get('reply_to')

        if reply_to is not None:
            email.add_header('reply-to', reply_to)

        yield email


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
        RECAPTCHA.verify(get_response(), remote_ip=remote_ip)
    except VerificationError:
        raise Error('reCAPTCHA check failed.')

    emails = tuple(get_emails())

    try:
        MAILER.send(emails, background=False)
    except SMTPAuthenticationError:
        raise Error('Invalid mailer credentials.', status=500)
    except SMTPRecipientsRefused:
        raise Error('Recipient refused.', status=500)

    return 'Emails sent.'
