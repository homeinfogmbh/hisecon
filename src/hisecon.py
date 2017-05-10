"""HOMEINFO Secure Contact form

This project provides a secure web mailer using reCaptcha by Google Inc.
and a token system to authenticate calling sites.
"""
from contextlib import suppress
from json import loads
from os.path import join
from urllib.parse import unquote
from smtplib import SMTPAuthenticationError, SMTPRecipientsRefused

from configparserplus import ConfigParserPlus
from emaillib import Mailer, EMail
from recaptcha import ReCaptcha
from wsgilib import OK, Error, InternalServerError, RequestHandler

__all__ = ['Hisecon']


class HiseconConfig(ConfigParserPlus):
    """Configuration parser for hisecon"""

    @property
    def mail(self):
        """Returns the mail section"""
        return self['mail']


class Hisecon(RequestHandler):
    """Handles requests of the hisecon app"""

    JSON = '/etc/hisecon.json'
    CONFIG = HiseconConfig('/etc/hisecon.conf', alert=True)

    def __init__(self, *args, **kwargs):
        """Load site once"""
        super().__init__(*args, **kwargs)
        print('## LOG LEVEL: {} ###'.format(self.logger.level))
        self.site = self._site

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

    @property
    def remote_ip(self):
        """Returns the specified remote IP address"""
        return self.query.get('remoteip')

    @property
    def issuer(self):
        """Returns the optional issuer address"""
        return self.query.get('issuer')

    @property
    def reply_to(self):
        """Returns the optional reply-to address"""
        return self.query.get('reply_to')

    @property
    def html(self):
        """Returns the HTML format flag"""
        return True if self.query.get('html') else False

    @property
    def config(self):
        """Returns the specified configuration"""
        try:
            return self.query['config']
        except KeyError:
            msg = 'No configuration provided'
            self.logger.warning(msg)
            raise Error(msg, status=400) from None

    @property
    def _site(self):
        """Returns the respective configuration settings"""
        try:
            return self.sites[self.config]
        except KeyError:
            msg = 'No such configuration entry: "{}"'.format(self.config)
            self.logger.warning(msg)
            raise Error(msg, status=400) from None

    @property
    def smtp(self):
        """Get optional SMTP configuration"""
        return self.site.get('smtp', {})

    @property
    def secret(self):
        """Returns the respective reCAPTCHA secret"""
        try:
            return self.site['secret']
        except KeyError:
            msg = 'No secret specified for configuration'
            self.logger.critical(msg)
            raise InternalServerError(msg) from None

    @property
    def response(self):
        """Returns the respective reCAPTCHA response"""
        try:
            return self.query['response']
        except KeyError:
            msg = 'No reCAPTCHA response provided'
            self.logger.warning(msg)
            raise Error(msg, status=400) from None

    @property
    def default_recipients(self):
        """Yields default recipients"""
        with suppress(KeyError):
            return self.site['recipients']

    @property
    def additional_recipients(self):
        """Yields the optional additional recipients"""
        with suppress(KeyError):
            for recipient in self.query['recipients'].split(','):
                recipient = recipient.strip()

                if recipient:
                    yield recipient

        # Yield legacy single recipient argument
        with suppress(KeyError):
            yield self.query['recipient']

    @property
    def recipients(self):
        """Yields all recipients"""
        yield from self.default_recipients
        yield from self.additional_recipients

        if self.issuer is not None:
            yield self.issuer

    @property
    def subject(self):
        """Returns the respective subject"""
        try:
            subject = self.query['subject']
        except KeyError:
            msg = 'No subject provided'
            self.logger.warning(msg)
            raise Error(msg, status=400) from None
        else:
            return unquote(subject)

    @property
    def host(self):
        """Returns the SMTP server's host name"""
        return self.smtp.get('host', self.CONFIG.mail['HOST'])

    @property
    def port(self):
        """Returns the SMTP server's port"""
        return self.smtp.get('port', int(self.CONFIG.mail['PORT']))

    @property
    def user(self):
        """Returns the SMTP user"""
        return self.smtp.get('user', self.CONFIG.mail['USER'])

    @property
    def passwd(self):
        """Returns the SMTP user's password"""
        return self.smtp.get('passwd', self.CONFIG.mail['PASSWD'])

    @property
    def ssl(self):
        """Returns the SMTP server's SSL/TLS settings"""
        return self.smtp.get('ssl', True)

    @property
    def sender(self):
        """Returns the specified sender's email address"""
        return self.smtp.get('from', self.CONFIG.mail['FROM'])

    @property
    def text(self):
        """Return the POSTed text"""
        try:
            return unquote(self.data.decode())
        except ValueError:
            raise Error('POSTed data is not a valid unicode string.') from None

    @property
    def bodies(self):
        """Get message text"""
        if self.html:
            return (None, self.text)
        else:
            return (self.text.replace('<br>', '\n'), None)

    @property
    def template(self):
        """Returns the optional template"""
        try:
            template_name = self.query['template']
        except KeyError:
            return None
        else:
            file_name = '{}.temp'.format(template_name)
            file_path = join('/usr/share/hisecon', file_name)

            try:
                with open(file_path, 'r') as f:
                    return f.read()
            except FileNotFoundError:
                raise Error('No such template: {}.'.format(
                    template_name)) from None
            except PermissionError:
                raise InternalServerError('Cannot open template.')

    @property
    def dictionary(self):
        """Returns the dictionary for data rendering"""
        try:
            return loads(self.text)
        except ValueError:
            raise Error('Not a valid JSON object: {}.'.format(
                self.text)) from None

    @property
    def mailer(self):
        """Returns an appropriate mailer"""
        return Mailer(self.host, self.port, self.user, self.passwd,
                      ssl=self.ssl, logger=self.logger)

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
        if ReCaptcha(self.secret, self.response, remote_ip=self.remote_ip):
            self.logger.info('Got valid reCAPTCHA')
            emails = list(self._emails(
                self.sender, self.recipients,
                self.subject, self.reply_to))

            try:
                self.mailer.send(emails, fg=True)
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
        else:
            msg = 'reCAPTCHA check failed'
            self.logger.error(msg)
            raise Error(msg, status=400) from None

    def _emails(self, sender, recipients, subject, reply_to):
        """Actually sends emails"""
        body_plain, body_html = self.bodies

        if not body_plain and not body_html:
            msg = 'No message body provided'
            self.logger.warning(msg)
            raise Error(msg, status=400) from None
        else:
            for recipient in recipients:
                email = EMail(
                    subject, sender, recipient,
                    plain=body_plain, html=body_html)

                if reply_to is not None:
                    email.add_header('reply-to', reply_to)

                yield email
