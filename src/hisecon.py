"""HOMEINFO Secure Contact form.

This project provides a secure web mailer using reCaptcha by Google Inc.
and a token system to authenticate calling sites.
"""
from contextlib import suppress
from json import loads
from os.path import join
from smtplib import SMTPAuthenticationError, SMTPRecipientsRefused
from urllib.parse import unquote

from configlib import INIParser
from emaillib import Mailer, EMail
from recaptcha import ReCaptcha
from wsgilib import OK, Error, InternalServerError, \
    RequestHandler

__all__ = ['Hisecon']


JSON = '/etc/hisecon.json'
CONFIG = INIParser('/etc/hisecon.conf', alert=True)


class Hisecon(RequestHandler):
    """ReCaptcha secured, configurable mail backend."""

    def __init__(self, *args, **kwargs):
        """Loads the site configuration."""
        super().__init__(*args, **kwargs)
        self.config = self._load_config()

    def _load_config(self):
        """Loads the site configuration JSON file."""
        try:
            config = self.query['config']
        except KeyError:
            raise self.logerr('No configuration provided.') from None

        try:
            with open(JSON) as json:
                text = json.read()
        except FileNotFoundError:
            self.logger.error('Sites file not found: {}.'.format(JSON))
            raise InternalServerError('Sites file not found.') from None
        except PermissionError:
            self.logger.error('Cannot read sites file: {}.'.format(JSON))
            raise InternalServerError('Sites file not readable.') from None

        try:
            sites = loads(text)
        except ValueError:
            self.logger.error('Invalid content:\n{}'.format(json))
            raise InternalServerError('Corrupted sites file.') from None

        try:
            return sites[config]
        except KeyError:
            msg = 'No such configuration: "{}".'.format(config)
            self.logger.warning(msg)
            raise Error(msg, status=400) from None

    @property
    def format(self):
        """Returns the desired format."""
        try:
            return self.query['format']
        except KeyError:
            if self.query.get('html', False):
                return 'html'

            return 'text'

    @property
    def response(self):
        """Returns the respective reCAPTCHA response."""
        try:
            return self.query['response']
        except KeyError:
            raise self.logerr('No reCAPTCHA response provided.') from None

    @property
    def recipients(self):
        """Yields all recipients."""
        for site_recipient in self.config.get('recipients', []):
            yield site_recipient

        try:
            recipients = self.query['recipients']
        except KeyError:
            pass
        else:
            for query_recipient in recipients.split(','):
                query_recipient = query_recipient.strip()

                if query_recipient:
                    yield query_recipient

        with suppress(KeyError):
            yield self.query['issuer']

    @property
    def subject(self):
        """Returns the respective subject."""
        try:
            subject = self.query['subject']
        except KeyError:
            msg = 'No subject provided'
            self.logger.warning(msg)
            raise Error(msg, status=400) from None
        else:
            return unquote(subject)

    @property
    def sender(self):
        """Returns the specified sender's email address."""
        try:
            return self.config['smtp']['from']
        except KeyError:
            return CONFIG['mail']['FROM']

    @property
    def template(self):
        """Returns the optional template."""
        file_name = '{}.temp'.format(self.config['template'])
        file_path = join('/usr/share/hisecon', file_name)

        try:
            with open(file_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            raise InternalServerError('Template not found.') from None
        except PermissionError:
            raise InternalServerError('Cannot open template.') from None

    @property
    def body(self):
        """Returns the emails plain text and HTML bodies."""
        frmt = self.format

        if frmt == 'html':
            return self.data.text
        elif frmt == 'text':
            return self.data.text.replace('<br>', '\n')
        elif frmt == 'json':
            try:
                template = self.template
            except KeyError:
                raise Error('No template configured.') from None

            try:
                return template.format(**self.data.json)
            except KeyError:
                raise Error('Invalid rendering settings.') from None

    @property
    def mailer(self):
        """Returns an appropriate mailer."""
        smtp = self.config.get('smtp', {})
        host = smtp.get('host', CONFIG['mail']['HOST'])
        port = smtp.get('port', int(CONFIG['mail']['PORT']))
        user = smtp.get('user', CONFIG['mail']['USER'])
        passwd = smtp.get('passwd', CONFIG['mail']['PASSWD'])
        ssl = smtp.get('ssl', True)
        return Mailer(host, port, user, passwd, ssl=ssl, logger=self.logger)

    @property
    def recaptcha(self):
        """Returns the ReCAPTCHA client."""
        try:
            secret = self.config['secret']
        except KeyError:
            raise self.logerr(
                'No secret specified for configuration.', status=500) from None
        else:
            return ReCaptcha(secret)

    def post(self):
        """Handles POST requests.

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
        if self.recaptcha.validate(
                self.response, remote_ip=self.query.get('remoteip')):
            self.logger.info('Got valid reCAPTCHA.')
            emails = list(self._emails(
                self.sender, self.recipients,
                self.subject, self.query.get('reply_to')))

            try:
                self.mailer.send(emails, background=False)
            except SMTPAuthenticationError:
                raise self.logerr('Invalid credentials.', status=500) from None
            except SMTPRecipientsRefused:
                raise self.logerr('Recipient refused.', status=500) from None
            else:
                msg = 'Emails sent.'
                self.logger.success(msg)
                return OK(msg)
        else:
            raise self.logerr('reCAPTCHA check failed.') from None

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
