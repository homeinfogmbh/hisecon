"""HOMEINFO Secure Contact form

This project provides a secure web mailer wusing reCaptcha by Google Inc.
and a token system to authenticate calling sites.
"""
from json import loads
from urllib.parse import unquote
from smtplib import SMTPAuthenticationError, SMTPRecipientsRefused

from requests import post

from homeinfo.lib.config import Configuration
from homeinfo.lib.log import Logger
from homeinfo.lib.mail import Mailer, EMail
from homeinfo.lib.wsgi import OK, Error, InternalServerError, RequestHandler

__all__ = ['Hisecon']


class ReCaptcha():
    """Re captcha wrapper"""

    VERIFICATION_URL = 'https://www.google.com/recaptcha/api/siteverify'

    def __init__(self, secret, response, remoteip=None, logger=None):
        """Sets basic reCAPTCHA data"""
        self.secret = secret
        self.response = response
        self.remoteip = remoteip

        if logger is None:
            self.logger = Logger(self.__class__.__name__)
        else:
            self.logger = logger.inherit(self.__class__.__name__)

    def __call__(self):
        """Calls the web API"""
        return post(self.VERIFICATION_URL, params=self._params)

    def __bool__(self):
        """Verifies reCAPTCHA data"""
        return True if self.verify() else False

    @property
    def _params(self):
        """Returns the parameters dictionary for requests"""
        params = {
            'secret': self.secret,
            'response': self.response}

        if self.remoteip is not None:
            params['remoteip'] = self.remoteip

        return params

    @property
    def dict(self):
        """Returns the response dictionary"""
        text = self().text

        try:
            return loads(text)
        except ValueError:
            self.logger.error('Invalid reCAPTCHA response: {}'.format(text))
            return {}

    def verify(self):
        """Verifies reCAPTCHA data"""
        try:
            return self.dict['success']
        except KeyError:
            return False


class HiseconConfig(Configuration):
    """Configuration parser for hisecon"""

    @property
    def mail(self):
        """Returns the mail section"""
        return self['mail']


class Hisecon(RequestHandler):
    """Handles requests of the hisecon app"""

    JSON = '/etc/hisecon.json'
    CONFIG = HiseconConfig('/etc/hisecon.conf', alert=True)

    @property
    def _sites_text(self):
        """Loads the text from the configurations file"""
        try:
            with open(self.JSON) as f:
                return f.read()
        except FileNotFoundError:
            self.logger.error('Sites file not found: {}'.format(self.JSON))
        except PermissionError:
            self.logger.error('Cannot read sites file: {}'.format(self.JSON))

    @property
    def sites(self):
        """Loads the configurations dictionary"""
        try:
            return loads(self._sites_text)
        except ValueError:
            self.logger.error('Invalid content:\n{}'.format(self._sites_text))
            return {}

    def post(self):
        """Handles POST requests

        Required params:
            config
            response
            subject

        Optional params:
            recipient
            remoteip
            issuer
            html
        """
        remoteip = self.params.get('remoteip')
        issuer = self.params.get('issuer')
        html = True if self.params.get('html') else False

        try:
            config = self.params.get('config')
        except KeyError:
            msg = 'No configuration provided'
            self.logger.warning(msg)
            raise Error(msg, status=400) from None
        else:
            try:
                site = self.sites[config]
            except KeyError:
                msg = 'No such configuration entry: "{}"'.format(config)
                self.logger.warning(msg)
                raise Error(msg, status=400) from None

        # Get optional SMTP configuration
        smtp = site.get('smtp', {})

        try:
            secret = site['secret']
        except KeyError:
            msg = 'No secret specified for configuration'
            self.logger.critical(msg)
            raise InternalServerError(msg) from None

        try:
            response = self.params['response']
        except KeyError:
            msg = 'No reCAPTCHA response provided'
            self.logger.warning(msg)
            raise Error(msg, status=400) from None

        try:
            recipient = self.params['recipient']
        except KeyError:
            recipient = None

        try:
            subject = self.params['subject']
        except KeyError:
            msg = 'No subject provided'
            self.logger.warning(msg)
            raise Error(msg, status=400) from None
        else:
            subject = unquote(subject)

        if ReCaptcha(secret, response, remoteip=remoteip):
            self.logger.info('Got valid reCAPTCHA')
            sender = smtp.get('from', self.CONFIG.mail['FROM'])
            recipients = site.get('recipients') or []

            mailer = Mailer(
                smtp.get('host', self.CONFIG.mail['HOST']),
                smtp.get('port', int(self.CONFIG.mail['PORT'])),
                smtp.get('user', self.CONFIG.mail['USER']),
                smtp.get('passwd', self.CONFIG.mail['PASSWD']),
                ssl=smtp.get('ssl', True),
                logger=self.logger)

            if recipient:
                recipients.append(recipient)

            if issuer:
                recipients.append(issuer)

            try:
                body_html, body_plain = self._get_text(html=html)
            except ValueError:
                msg = 'Non-text data received'
                self.logger.error(msg)
                raise Error(msg, status=400) from None
            else:
                if not body_plain and not body_html:
                    msg = 'No message provided'
                    self.logger.warning(msg)
                    raise Error(msg, status=400) from None
                else:
                    emails = [email for email in self._emails(
                        sender, recipients, subject,
                        body_html=body_html, body_plain=body_plain)]
                    return self._send_mails(mailer, emails)
        else:
            msg = 'reCAPTCHA check failed'
            self.logger.error(msg)
            raise Error(msg, status=400) from None

    def _emails(self, sender, recipients, subject,
                body_html=None, body_plain=None):
        """Actually sends emails"""
        for recipient in recipients:
            yield EMail(
                subject, sender, recipient,
                plain=body_plain, html=body_html)

    def _get_text(self, html=False):
        """Get message text"""
        text = unquote(self.data.decode())

        if html:
            return (text, None)
        else:
            return (None, text.replace('<br>', '\n'))

    def _send_mails(self, mailer, emails):
        """Actually send emails"""
        try:
            mailer.send(emails, fg=True)
        except SMTPAuthenticationError:
            msg = 'Invalid credentials'
            self.logger.critical(msg)
            raise InternalServerError(msg) from None
        except SMTPRecipientsRefused:
            msg = 'Recipient refused'
            self.logger.critical(msg)
            raise InternalServerError(msg) from None
        else:
            msg = 'Emails sent'
            self.logger.success(msg)
            return OK(msg)
