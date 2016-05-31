"""HOMEINFO Secure Contact form

This project provides a secure web mailer wusing reCaptcha by Google Inc.
and a token system to authenticate calling sites.
"""
from requests import get
from json import loads

from homeinfo.lib.config import Configuration
from homeinfo.lib.mail import Mailer, EMail
from homeinfo.lib.wsgi import Error, InternalServerError, WsgiApp

__all__ = ['Hisecon']


class HiseconConfig(Configuration):
    """Configuration parser for hisecon"""

    @property
    def mail(self):
        """Returns the mail section"""
        return self['mail']


CONFIG = HiseconConfig('/etc/hisecon.conf', alert=True)


class Hisecon(WsgiApp):
    """WSGI mailer app"""

    DEBUG = True

    RE_CAPTCHA_URL = 'https://www.google.com/recaptcha/api/siteverify'

    def post(self, environ):
        """Handles POST requests"""
        query_string = self.query_string(environ)
        qd = self.qd(query_string)
        cqd = self.cqd(qd)

        sender = cqd.get('sender') or CONFIG.mail['FROM']
        copy2issuer = cqd.get('copy2issuer') or False
        reply_email = cqd.get('reply_email')

        try:
            secret = cqd['secret']
        except KeyError:
            return Error('No reCAPTCHA secret provided', status=400)

        try:
            response = cqd['response']
        except KeyError:
            return Error('No reCAPTCHA response provided', status=400)

        remoteip = cqd.get('remoteip')

        try:
            recipient = cqd['recipient']
        except KeyError:
            return Error('No recipient email address provided', status=400)

        try:
            subject = cqd['subject']
        except KeyError:
            return Error('No subject provided', status=400)

        try:
            message = cqd['message']
        except KeyError:
            return Error('No message provided', status=400)

        if self._check_recpatcha(secret, response, remoteip=remoteip):
            mailer = Mailer(
                CONFIG.mail['ADDR'],
                int(CONFIG.mail['PORT']),
                CONFIG.mail['USER'],
                CONFIG.mail['PASSWD'])

            email = EMail(subject, sender, recipient, plain=message)

            mailer.send([email])
        else:
            return Error('reCAPTCHA check failed', status=400)

    # XXX: Debug!
    get = post

    def _check_recpatcha(self, secret, response, remoteip=None):
        """Verifies Google reCAPTCHA credentials"""
        params = {'secret': secret, 'response': response}

        if remoteip is not None:
            params['remoteip'] = remoteip

        response = post(self.RE_CAPTCHA_URL, params=params)

        try:
            response_dict = loads(response.text)
        except ValueError:
            return InternalServerError(
                'Could not parse JSON response of reCAPTCHA')

        return response_dict.get('success', False) is True
