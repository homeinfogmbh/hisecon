"""HOMEINFO Secure Contact form

This project provides a secure web mailer wusing reCaptcha by Google Inc.
and a token system to authenticate calling sites.
"""
from logging import getLogger
from json import loads

from requests import post

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

    def __init__(self, cors=None, date_format=None):
        super().__init__(cors=cors, date_format=date_format)
        self.logger = getLogger(name=self.__class__.__name__)

    def post(self, environ):
        """Handles POST requests"""
        query_string = self.query_string(environ)
        qd = self.qd(query_string)

        sender = qd.get('sender') or CONFIG.mail['FROM']
        copy2issuer = True if qd.get('copy2issuer') else False
        reply_email = qd.get('reply_email')

        try:
            secret = qd['secret']
        except KeyError:
            msg = 'No reCAPTCHA secret provided'
            self.logger.warning(msg)
            return Error(msg, status=400)

        try:
            response = qd['response']
        except KeyError:
            msg = 'No reCAPTCHA response provided'
            self.logger.warning(msg)
            return Error(msg, status=400)

        remoteip = qd.get('remoteip')

        try:
            recipient = qd['recipient']
        except KeyError:
            msg = 'No recipient email address provided'
            self.logger.warning(msg)
            return Error(msg, status=400)

        try:
            subject = qd['subject']
        except KeyError:
            msg = 'No subject provided'
            self.logger.warning(msg)
            return Error(msg, status=400)

        try:
            message = qd['message']
        except KeyError:
            msg = 'No message provided'
            self.logger.warning(msg)
            return Error(msg, status=400)

        if self._check_recpatcha(secret, response, remoteip=remoteip):
            self.logger.info('Got valid reCAPTCHA')
            mailer = Mailer(
                CONFIG.mail['ADDR'],
                int(CONFIG.mail['PORT']),
                CONFIG.mail['USER'],
                CONFIG.mail['PASSWD'])

            email = EMail(subject, sender, recipient, plain=message)
            self.logger.info(
                'Created email from "{sender}" to "{recipient}" with subject '
                '"{subject}" and content "{content}"'.format(
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    content=message))

            try:
                mailer.send([email])
            except Exception:
                self.logger.critical('Could not send mail')
            else:
                self.logger.info('Mail sent')
        else:
            msg = 'reCAPTCHA check failed'
            self.logger.error(msg)
            return Error(msg, status=400)

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
            msg = 'Could not parse JSON response of reCAPTCHA'
            self.logger.error(msg)
            return InternalServerError(msg)

        return response_dict.get('success', False) is True
