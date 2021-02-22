"""Miscellaneous functions."""

from typing import Iterator, Optional

from flask import request

from emaillib import EMail
from recaptcha import verify as _verify

from hisecon.config import CONFIG, LOGGER
from hisecon.contextlocals import SITE
from hisecon.errors import error


__all__ = ['get_emails', 'verify']


def get_content_type() -> str:
    """Returns the content type."""

    try:
        return request.json['contentType']
    except KeyError:
        raise error('No content type provided') from None


def get_emails() -> Iterator[EMail]:
    """Actually sends emails"""

    for recipient in get_recipients():
        LOGGER.debug('Recipient: %s', recipient)
        email = EMail(get_subject(), get_sender(), recipient,
                      plain=get_plain_text(), html=get_html_text())
        reply_to = request.json.get('replyTo')

        if reply_to is not None:
            email.add_header('reply-to', reply_to)

        yield email


def get_html_text() -> Optional[str]:
    """Returns the HTML text attachment for the email."""

    if get_content_type() == 'text/plain':
        return get_text()

    return None


def get_plain_text() -> Optional[str]:
    """Returns the plain text attachment for the email."""

    if get_content_type() in {'text/html', 'application/xhtml+xml'}:
        return get_text()

    return None


def get_recipients() -> Iterator[str]:
    """Yields all recipients."""

    yield from SITE.get('recipients', [])
    yield from request.json.get('recipients', [])


def get_response() -> str:
    """Returns the respective reCAPTCHA response."""

    try:
        return request.json['response']
    except KeyError:
        raise error('No reCAPTCHA response provided.') from None


def get_secret() -> str:
    """Returns the respective ReCAPTCHA secret."""

    try:
        return SITE['secret']
    except KeyError:
        raise error('No secret specified.', status=500) from None


def get_sender() -> str:
    """Returns the specified sender's email address."""

    try:
        return SITE['smtp']['from']
    except KeyError:
        return CONFIG['mail']['from']


def get_subject() -> str:
    """Returns the subject."""

    try:
        return request.json['subject']
    except KeyError:
        raise error('No subject provided') from None


def get_text() -> str:
    """Returns the message text."""

    try:
        return request.json['text']
    except KeyError:
        raise error('No text provided') from None


def verify() -> bool:
    """Verifies the ReCAPTCHA."""

    return _verify(get_secret(), get_response(), remote_ip=request.remote_addr)
