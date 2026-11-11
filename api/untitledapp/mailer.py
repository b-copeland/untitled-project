"""
Outgoing email, behind one function so the rest of the app does not care how it is delivered.

    send_email(to, subject, text)

Which backend delivers it is decided by ``EMAIL_BACKEND`` in the config:

* ``smtp``    sends through Flask-Mail (SendGrid by default, see ``MAIL_*`` in config.py).
* ``console`` writes the message to the application log. For local development, so that a "verify your email" link can
              be copied out of the terminal without any account.
* ``memory``  keeps the messages in ``app.extensions["mail_outbox"]``. For tests.

If ``EMAIL_BACKEND`` is not set, ``smtp`` is used when a ``MAIL_PASSWORD`` (the SendGrid key) exists and ``console``
otherwise, so a missing key never makes sign-up or password recovery crash.

Sending never raises into the caller: a mail server that is down must not turn a "forgot password" request into an
error page, and (more importantly) it must not reveal whether an address is registered. Failures are logged.
"""
import itsdangerous
import flask
from flask_mail import Message

from untitledapp import mail


def _backend():
    app = flask.current_app
    configured = app.config.get("EMAIL_BACKEND")
    if configured:
        return configured
    return "smtp" if app.config.get("MAIL_PASSWORD") else "console"


def send_email(to, subject, text):
    """Deliver one plain-text message. Returns True if it was handed to the backend."""
    app = flask.current_app
    backend = _backend()
    try:
        if backend == "memory":
            app.extensions.setdefault("mail_outbox", []).append({"to": to, "subject": subject, "text": text})
        elif backend == "console":
            app.logger.warning("EMAIL to=%s subject=%s\n%s", to, subject, text)
        else:
            mail.send(Message(subject=subject, recipients=[to], body=text))
    except Exception:
        app.logger.exception("Could not send email to %s", to)
        return False
    return True


def frontend_url():
    """Where the React app lives, for the links in emails."""
    configured = flask.current_app.config.get("FRONTEND_URL")
    return (configured or flask.request.host_url).rstrip("/")


# Signed, expiring tokens for the links in emails. They carry no state of their own on the server: the signature proves
# we issued them, and the age check expires them. The purpose is the salt, so a token for one thing is useless for
# another.
VERIFY_EMAIL = "verify-email"
RESET_PASSWORD = "reset-password"
MAX_AGE = {VERIFY_EMAIL: 2 * 24 * 3600, RESET_PASSWORD: 3600}


def _serializer(purpose):
    return itsdangerous.URLSafeTimedSerializer(flask.current_app.config["SECRET_KEY"], salt=purpose)


def make_token(purpose, payload):
    return _serializer(purpose).dumps(payload)


def read_token(purpose, token):
    """The payload, or None if the token is forged, for another purpose, or too old."""
    try:
        return _serializer(purpose).loads(token, max_age=MAX_AGE[purpose])
    except itsdangerous.BadData:
        return None
