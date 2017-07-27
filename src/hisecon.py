"""HOMEINFO Secure Contact form

This project provides a secure web mailer using reCaptcha by Google Inc.
and a token system to authenticate calling sites.
"""
from contextlib import suppress
from json import loads
from os.path import join
from smtplib import SMTPAuthenticationError, SMTPRecipientsRefused
from urllib.parse import unquote

from configparserplus import ConfigParserPlus
from emaillib import Mailer, EMail
from recaptcha import ReCaptcha
from wsgilib import escape_object, OK, Error, InternalServerError, RequestHandler

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

        try:
            with open(self.JSON) as f:
                json = f.read()
        except FileNotFoundError:
            self.logger.error('Sites file not found: {}'.format(self.JSON))
            raise InternalServerError('Sites file not found.') from None
        except PermissionError:
            self.logger.error('Cannot read sites file: {}'.format(self.JSON))
            raise InternalServerError('Sites file not readable.') from None
        else:
            try:
                sites = loads(json)
            except ValueError:
                self.logger.error('Invalid content:\n{}'.format(json))
                raise InternalServerError('Corrupted sites file.') from None
            else:
                try:
                    self.site = sites[self.config]
                except KeyError:
                    msg = 'No such configuration: "{}"'.format(self.config)
                    self.logger.warning(msg)
                    raise Error(msg, status=400) from None
                else:
                    self.smtp = self.site.get('smtp', {})

    @property
    def remote_ip(self):
        """Returns the specified remote IP address"""
        return self.query.get('remoteip')

    @property
    def reply_to(self):
        """Returns the optional reply-to address"""
        return self.query.get('reply_to')

    @property
    def format(self):
        """Returns the desired format"""
        try:
            return self.query['format']
        except KeyError:
            if self.query.get('html') is not None:
                return 'html'
            else:
                return 'text'

    @property
    def config(self):
        """Returns the specified configuration"""
        try:
            return self.query['config']
        except KeyError:
            raise self.logerr('No configuration provided.') from None

    @property
    def secret(self):
        """Returns the respective reCAPTCHA secret"""
        try:
            return self.site['secret']
        except KeyError:
            raise self.logerr(
                'No secret specified for configuration.', status=500) from None

    @property
    def response(self):
        """Returns the respective reCAPTCHA response"""
        try:
            return self.query['response']
        except KeyError:
            raise self.logerr('No reCAPTCHA response provided.') from None

    @property
    def issuer(self):
        """Returns the optional issuer address"""
        return self.query.get('issuer')

    @property
    def default_recipients(self):
        """Yields default recipients"""
        try:
            return self.site['recipients']
        except KeyError:
            return []

    @property
    def additional_recipients(self):
        """Yields the optional additional recipients"""
        try:
            recipients = self.query['recipients'].split(',')
        except KeyError:
            pass
        else:
            for recipient in recipients:
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
        except AttributeError:
            raise Error('No data provided.') from None
        except ValueError:
            raise Error('POSTed data is not a valid unicode string.') from None

    @property
    def json(self):
        """Returns the POSTed JSON data"""
        try:
            return loads(self.data.decode())
        except AttributeError:
            raise Error('No data provided.') from None
        except ValueError:
            raise Error('Invalid JSON data.') from None

    @property
    def template(self):
        """Returns the optional template"""
        file_name = '{}.temp'.format(self.site['template'])
        file_path = join('/usr/share/hisecon', file_name)

        try:
            with open(file_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            raise InternalServerError('Template not found.') from None
        except PermissionError:
            raise InternalServerError('Cannot open template.') from None

    @property
    def body(self):
        """Returns the emails plain text and HTML bodies"""
        format = self.format

        if format == 'html':
            return self.text
        elif format == 'text':
            return self.text.replace('<br>', '\n')
        elif format == 'json':
            json = escape_object(self.json)

            try:
                template = self.template
            except KeyError:
                raise Error('No template configured.') from None
            else:
                try:
                    return template.format(**json)
                except KeyError:
                    raise Error('Invalid rendering settings.') from None

    @property
    def mailer(self):
        """Returns an appropriate mailer"""
        return Mailer(self.host, self.port, self.user, self.passwd,
                      ssl=self.ssl, logger=self.logger)

    @property
    def recaptcha(self):
        """Returns a recaptcha client"""
        return ReCaptcha(self.secret, logger=self.logger)

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
            html (deprecated)
            format (new)
        """
        if self.recaptcha.validate(self.response, remote_ip=self.remote_ip):
            self.logger.info('Got valid reCAPTCHA.')
            emails = list(self._emails(
                self.sender, self.recipients,
                self.subject, self.reply_to))

            try:
                self.mailer.send(emails, fg=True)
            except SMTPAuthenticationError:
                raise self.logerr('Invalid credentials.', status=500) from None
            except SMTPRecipientsRefused:
                raise self.logerr('Recipient refused.', status=500) from None
            else:
                msg = 'Emails sent.'
                self.logger.success(msg)
                return OK(msg)
        else:
            msg = 'reCAPTCHA check failed'
            self.logger.error(msg)
            raise Error(msg, status=400) from None

    def _emails(self, sender, recipients, subject, reply_to):
        """Actually sends emails"""
        if self.format in ('html', 'json'):
            body_plain = None
            body_html = self.body
        else:
            body_plain = self.body
            body_html = None

        if not body_plain and not body_html:
            raise self.logerr('No message body provided.') from None
        else:
            for recipient in recipients:
                email = EMail(
                    subject, sender, recipient,
                    plain=body_plain, html=body_html)

                if reply_to is not None:
                    email.add_header('reply-to', reply_to)

                yield email
