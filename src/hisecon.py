"""HOMEINFO Secure Contact form

This project provides a secure web mailer wusing reCaptcha by Google Inc.
and a token system to authenticate calling sites.
"""
from logging import getLogger
from json import loads

from requests import post

from homeinfo.lib.config import Configuration
from homeinfo.lib.mail import Mailer, EMail
from homeinfo.lib.wsgi import OK, Error, InternalServerError, WsgiApp

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


class DomainConfig():
    """Domain configuration wrapper"""

    def __init__(self, domain, secret, recipients=None, sender=None):
        self.domain = domain
        self.secret = secret
        self.recipients = recipients
        self.sender = sender


class Hisecon(WsgiApp):
    """WSGI mailer app"""

    DEBUG = True

    SECRETS_FILE = '/etc/hisecon.domains'

    def __init__(self, date_format=None):
        super().__init__(cors=True, date_format=date_format)
        self.logger = getLogger(name=self.__class__.__name__.upper())
        self.config = HiseconConfig('/etc/hisecon.conf', alert=True)

    @property
    def domains(self):
        """Returns available domain configurations"""
        sites = {}

        try:
            with open(self.SECRETS_FILE) as f:
                s = f.read()
        except FileNotFoundError:
            self.logger.error('Secrets file not found: {}'.format(
                self.SECRETS_FILE))
            return sites
        except PermissionError:
            self.logger.error('Secrets file "{}" could not be opened'.format(
                self.SECRETS_FILE))
            return sites

        try:
            sites_dict = loads(s)
        except ValueError:
            self.logger.error('Secrets file "{}" has invalid content'.format(
                self.SECRETS_FILE))
            return sites
        else:
            try:
                sites_list = sites_dict['sites']
            except KeyError:
                self.logger.error('No sites configured')
                return sites

            for site_element in sites_list:
                try:
                    domain = site_element['domain']
                    secret = site_element['secret']
                except KeyError:
                    self.logger.error('Could not lookup domain and / or '
                        'secret for {}'.format(site_element))
                else:
                    try:
                        recipients = site_element['recipients']
                    except KeyError:
                        recipients = None

                    try:
                        sender = site_element['sender']
                    except KeyError:
                        sender = None

                    sites[domain] = DomainConfig(
                        domain,
                        secret,
                        recipients=recipients,
                        sender=sender)

        return sites

    def post(self, environ):
        """Handles POST requests

        Required params:
            domain
            response
            recipient
            subject

        Optional params:
            sender
            remoteip
            issuer
            copy2issuer
            body_plain
            body_html
        """
        query_string = self.query_string(environ)
        self.logger.debug(query_string)

        qd = self.qd(query_string)
        self.logger.debug(str(qd))

        remoteip = qd.get('remoteip')
        issuer = qd.get('issuer')
        copy2issuer = True if qd.get('copy2issuer') else False
        body_plain = qd.get('body_plain')
        body_html = qd.get('body_html')

        try:
            domain = qd.get('domain')
        except KeyError:
            msg = 'No domain provided'
            self.logger.warning(msg)
            return Error(msg, status=400)
        else:
            try:
                domain_config = self.domains[domain]
            except KeyError:
                msg = 'Invalid domain: {}'.format(domain)
                self.logger.warning(msg)
                return Error(msg, status=400)

        try:
            response = qd['response']
        except KeyError:
            msg = 'No reCAPTCHA response provided'
            self.logger.warning(msg)
            return Error(msg, status=400)

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

        if not body_plain and not body_html:
            msg = 'No message provided'
            self.logger.warning(msg)
            return Error(msg, status=400)

        try:
            if ReCaptcha(domain_config.secret, response, remoteip=remoteip):
                self.logger.info('Got valid reCAPTCHA')

                sender = domain_config.sender or self.config.mail['FROM']
                recipients = domain_config.recipients or []

                if copy2issuer and issuer:
                    recipients.append(issuer)

                return self._send_mail(
                    sender, recipients, subject,
                    body_html=body_html, body_plain=body_plain)
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

    def _send_mail(self, sender, recipients, subject,
                   body_html=body_html, body_plain=body_plain)
        """Actually sends emails"""
        mailer = Mailer(
            self.config.mail['ADDR'],
            int(self.config.mail['PORT']),
            self.config.mail['USER'],
            self.config.mail['PASSWD'])

        emails = []

        for recipient in recipients:
            email = EMail(
                subject, sender, recipient,
                plain=body_plain, html=body_html)
            self.logger.debug(
                'Created email from "{sender}" to "{recipient}" with subject '
                '"{subject}" and plain content "{body_plain}" and HTML content '
                '"{body_html}"'.format(
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    body_plain=body_plain,
                    body_html=body_html))
            emails.append(email)

        try:
            mailer.send(emails)
        except Exception:
            msg = 'Could not send mail'
            self.logger.critical(msg)
            return InternalServerError(msg)
        else:
            msg = 'Mail sent'
            self.logger.info(msg)
            return OK(msg)
