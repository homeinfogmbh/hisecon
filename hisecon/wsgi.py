"""Web server implementation."""

from logging import DEBUG, INFO, basicConfig

from recaptcha import VerificationError
from wsgilib import Application

from hisecon.config import CONFIG, CONFIG_FILE, LOG_FORMAT, LOGGER
from hisecon.contextlocals import MAILER
from hisecon.errors import error
from hisecon.functions import get_emails, verify


__all__ = ["APPLICATION"]


APPLICATION = Application("hisecon", cors=True)


@APPLICATION.before_first_request
def init_logger():
    """Initializes the logger."""

    CONFIG.read(CONFIG_FILE)
    debug_mode = CONFIG.getboolean("app", "debug", fallback=False)
    basicConfig(level=DEBUG if debug_mode else INFO, format=LOG_FORMAT)


@APPLICATION.route("/", methods=["POST"])
def send_emails():
    """Sends emails."""

    try:
        verify()
    except VerificationError:
        return error("reCAPTCHA check failed.")

    emails = tuple(get_emails())
    LOGGER.debug("Got emails: %s", emails)

    if not emails:
        return error("No recipients specified.", status=400)

    MAILER.send(emails)
    return "Emails sent."
