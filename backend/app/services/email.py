from __future__ import annotations

import email.mime.multipart
import email.mime.text

import aiosmtplib
import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

log = structlog.get_logger()

_jinja = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html"]),
)


async def _send(to: str, subject: str, html_body: str) -> None:
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.attach(email.mime.text.MIMEText(html_body, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=False,
        )
        log.info("email.sent", to=to, subject=subject)
    except Exception as exc:
        log.error("email.send_failed", to=to, exc=str(exc))


async def send_verification_email(to: str, verify_url: str) -> None:
    html = _jinja.get_template("email_verify.html").render(verify_url=verify_url)
    await _send(to, "Verifica il tuo account", html)


async def send_password_reset_email(to: str, reset_url: str) -> None:
    html = _jinja.get_template("email_reset.html").render(reset_url=reset_url)
    await _send(to, "Reset della password", html)
