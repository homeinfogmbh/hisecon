"""HOMEINFO Secure Contact form

This project provides a secure web mailer wusing reCaptcha by Google Inc.
and a token system to authenticate calling sites.
"""
from logging import getLogger
from json import loads
from urllib.parse import unquote
from smtplib import SMTPAuthenticationError, SMTPRecipientsRefused

from requests import post

from homeinfo.lib.config import Configuration
from homeinfo.lib.mail import Mailer, EMail
from homeinfo.lib.wsgi import OK, Error, InternalServerError, handler, \
    RequestHandler, WsgiApp

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
        params = {'secret': self.secret, 'response': self.response}

        if self.remoteip is not None:
            params['remoteip'] = self.remoteip

        response = post(self.VERIFICATION_URL, params=params)
        response_dict = loads(response.text)

        return response_dict.get('success', False) is True


class HiseconConfig(Configuration):
    """Configuration parser for hisecon"""

    @property
    def mail(self):
        """Returns the mail section"""
        return self['mail']


class HiseconRequestHandler(RequestHandler):
    """Handles requests of the hisecon app"""

    def __init__(self, environ, cors, date_format, debug):
        super().__init__(environ, cors, date_format, debug)
        self.SECRETS_FILE = '/etc/hisecon.domains'
        self.config = HiseconConfig('/etc/hisecon.conf', alert=True)
        self.logger = getLogger(name='HISECON')

    @property
    def configs_text(self):
        """Loads the text from the configurations file"""
        try:
            with open(self.SECRETS_FILE) as f:
                s = f.read()
        except FileNotFoundError:
            self.logger.error('Secrets file not found: {}'.format(
                self.SECRETS_FILE))
        except PermissionError:
            self.logger.error('Secrets file "{}" could not be opened'.format(
                self.SECRETS_FILE))
        else:
            return s

    @property
    def configs(self):
        """Loads the configurations dictionary"""
        try:
            configs_dict = loads(self.configs_text)
        except ValueError:
            self.logger.error('Secrets file "{}" has invalid content'.format(
                self.SECRETS_FILE))
            return {}
        else:
            return configs_dict

        return sites

    def post(self):
        """Handles POST requests

        Required params:
            config
            response
            recipient
            subject

        Optional params:
            sender
            remoteip
            issuer
            body_plain
            body_html
        """
        # Get query dictionary from API
        qd = self.query_dict
        self.logger.debug(str(qd))

        remoteip = qd.get('remoteip')
        self.logger.debug('Got remote IP: {}'.format(remoteip))
        issuer = qd.get('issuer')
        self.logger.debug('Got issuer: {}'.format(issuer))
        html = True if qd.get('html') else False
        self.logger.debug('HTML content is: {}'.format(remoteip))

        try:
            config = qd.get('config')
        except KeyError:
            msg = 'No configuration provided'
            self.logger.warning(msg)
            return Error(msg, status=400)
        else:
            try:
                cfgd = self.configs[config]
            except KeyError:
                msg = 'No such configuration entry: "{}"'.format(config)
                self.logger.warning(msg)
                return Error(msg, status=400)

        smtp_host = cfgd.get('smtp_host') or self.config.mail['ADDR']
        self.logger.debug('Got SMTP host: {}'.format(smtp_host))

        try:
            smtp_port = int(cfgd.get('smtp_port'))
        except (TypeError, ValueError):
            smtp_port = int(self.config.mail['PORT'])

        self.logger.debug('Got SMTP port: {}'.format(smtp_port))

        smtp_ssl = cfgd.get('smtp_ssl', None)
        self.logger.debug('Got SMTP SSL: {}'.format(smtp_ssl))

        smtp_user = cfgd.get('smtp_user') or self.config.mail['USER']
        self.logger.debug('Got SMTP user: {}'.format(smtp_user))

        smtp_passwd = cfgd.get('smtp_passwd') or self.config.mail['PASSWD']
        self.logger.debug('Got SMTP passwd: {}'.format(smtp_passwd))

        try:
            secret = cfgd['secret']
        except KeyError:
            msg = 'No secret specified for configuration'
            self.logger.critical(msg)
            return InternalServerError(msg)

        try:
            response = qd['response']
        except KeyError:
            msg = 'No reCAPTCHA response provided'
            self.logger.warning(msg)
            return Error(msg, status=400)
        else:
            self.logger.debug('Got reCAPTCHA response: {}'.format(response))

        try:
            recipient = qd['recipient']
        except KeyError:
            recipient = None

        self.logger.debug('Got additional recipient: {}'.format(recipient))

        try:
            subject = qd['subject']
        except KeyError:
            msg = 'No subject provided'
            self.logger.warning(msg)
            return Error(msg, status=400)
        else:
            self.logger.debug('Got subject: {}'.format(subject))
            subject = unquote(subject)
            self.logger.debug('Got unquoted subject: {}'.format(subject))

        try:
            if ReCaptcha(secret, response, remoteip=remoteip):
                self.logger.info('Got valid reCAPTCHA')
                sender = cfgd.get('smtp_from') or self.config.mail['FROM']
                self.logger.debug('Got sender: {}'.format(sender))
                recipients = cfgd.get('recipients') or []
                self.logger.debug('Got recipients: {}'.format(recipients))

                mailer = Mailer(smtp_host, smtp_port, smtp_user, smtp_passwd,
                                ssl=smtp_ssl, logger=self.logger)

                if recipient:
                    recipients.append(recipient)
                    self.logger.debug('Added recipient: {}'.format(recipient))

                if issuer:
                    recipients.append(issuer)
                    self.logger.debug('Added issuer: {}'.format(issuer))

                if recipient or issuer:
                    self.logger.debug('Updated recipients: {}'.format(
                        recipients))

                try:
                    body_html, body_plain = self._get_text(html=html)
                except ValueError:
                    msg = 'Non-text data received'
                    self.logger.error(msg)
                    return Error(msg, status=400)
                else:
                    if not body_plain and not body_html:
                        msg = 'No message provided'
                        self.logger.warning(msg)
                        return Error(msg, status=400)
                    else:
                        emails = [email for email in self._emails(
                            sender, recipients, subject,
                            body_html=body_html, body_plain=body_plain)]
                        return self._send_mails(mailer, emails)
            else:
                msg = 'reCAPTCHA check failed'
                self.logger.error(msg)
                return Error(msg, status=400)
        except ValueError:
            msg = 'Could not parse JSON response of reCAPTCHA'
            self.logger.error(msg)
            return InternalServerError(msg)

    def _emails(self, sender, recipients, subject,
                body_html=None, body_plain=None):
        """Actually sends emails"""
        for recipient in recipients:
            email = EMail(
                subject, sender, recipient,
                plain=body_plain, html=body_html)
            self.logger.debug(
                'Created email from "{sender}" to "{recipient}" '
                'with subject "{subject}" and plain content '
                '"{body_plain}" and HTML content "{body_html}"'.format(
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    body_plain=body_plain,
                    body_html=body_html))
            yield email

    def _get_text(self, html=False):
        """Get message text"""
        body_html = None
        body_plain = None

        data = self.file.read()
        text = data.decode()

        if html:
            body_html = text
            self.logger.debug('Got HTML text: {0}'.format(body_html))
            body_html = unquote(text)
            self.logger.debug('Unquoted HTML text: {0}'.format(body_html))
        else:
            body_plain = text
            self.logger.debug('Got plain text: {0}'.format(body_plain))
            body_plain = unquote(body_plain)
            self.logger.debug('Unquoted plain text: {0}'.format(body_plain))
            body_plain = body_plain.replace('<br>', '\n')
            self.logger.debug('Translated plain text: {0}'.format(body_plain))

        return (body_html, body_plain)

    def _send_mails(self, mailer, emails):
        """Actually send emails"""
        self.logger.debug('Sending emails')

        try:
            mailer.send(emails, fg=True)
        except SMTPAuthenticationError:
            msg = 'Invalid credentials'
            self.logger.critical(msg)
            return InternalServerError(msg)
        except SMTPRecipientsRefused:
            msg = 'Recipient refused'
            self.logger.critical(msg)
            return InternalServerError(msg)
        except Exception:
            if self.debug:
                raise
            else:
                msg = 'Unknown error'
                self.logger.critical(msg)
                return InternalServerError(msg)
        else:
            msg = 'Emails sent'
            self.logger.info(msg)
            return OK(msg)


@handler(HiseconRequestHandler)
class Hisecon(WsgiApp):
    """WSGI mailer app"""

    DEBUG = True
