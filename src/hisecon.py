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


class ReCaptcha():
    """Re captcha wrapper"""

    VERIFICATION_URL = 'https://www.google.com/recaptcha/api/siteverify'

    def __init__(self, secret, response, remoteip=None):
        """Sets basic reCAPTCHA data"""
        self.secret = secret
        self.response = response
        self.remoteip = remoteip

    def __bool__(self):
        """Verifies reCAPTCHA data"""
        return self.verify()

    def verify(self):
        """Verifies reCAPTCHA data"""
        params = {'secret': secret, 'response': response}

        if remoteip is not None:
            params['remoteip'] = remoteip

        response = post(self.VERIFICATION_URL, params=params)
        response_dict = loads(response.text)

        return response_dict.get('success', False) is True


class HiseconConfig(Configuration):
    """Configuration parser for hisecon"""

    @property
    def mail(self):
        """Returns the mail section"""
        return self['mail']

    @property
    def recaptcha(self):
        """Returns the reCAPTCHA section"""
        return self['recaptcha']


class Hisecon(WsgiApp):
    """WSGI mailer app"""

    DEBUG = True

    def __init__(self, cors=None, date_format=None):
        super().__init__(cors=cors, date_format=date_format)
        self.logger = getLogger(name=self.__class__.__name__.upper())
        self.config = HiseconConfig('/etc/hisecon.conf', alert=True)

    def post(self, environ):
        """Handles POST requests"""
        query_string = self.query_string(environ)
        qd = self.qd(query_string)

        sender = qd.get('sender') or self.config.mail['FROM']
        copy2issuer = True if qd.get('copy2issuer') else False
        reply_email = qd.get('reply_email')

        secret = self.config.recaptcha['SECRET']

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

        try:
            if ReCaptcha(secret, response, remoteip=remoteip):
                self.logger.info('Got valid reCAPTCHA')
                self._send_mail(sender, recipient, subject, message)
            else:
                msg = 'reCAPTCHA check failed'
                self.logger.error(msg)
                return Error(msg, status=400)
        except ValueError:
            msg = 'Could not parse JSON response of reCAPTCHA'
            self.logger.error(msg)
            return InternalServerError(msg)

    # Allow GET and POST requests
    get = post

    def _send_mail(self, sender, recipient, subject, message):
        """Actually sends emails"""
        mailer = Mailer(
            self.config.mail['ADDR'],
            int(self.config.mail['PORT']),
            self.config.mail['USER'],
            self.config.mail['PASSWD'])

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
