import logging
import json
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage

from app.core.config import get_settings


logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


def _recipient_payload(recipients: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "email": recipient["email"],
            "name": recipient.get("name") or recipient["email"],
        }
        for recipient in recipients
        if recipient.get("email")
    ]


def _brevo_api_configured() -> bool:
    settings = get_settings()
    return bool(settings.brevo_api_key)


def _smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.mail_server and settings.mail_username and settings.mail_password)


def send_html_email(
    *,
    subject: str,
    html_body: str,
    text_body: str,
    to: list[dict[str, str]],
    cc: list[dict[str, str]] | None = None,
    bcc: list[dict[str, str]] | None = None,
) -> None:
    settings = get_settings()
    cc = cc or []
    bcc = bcc or []

    if not to:
        raise EmailDeliveryError("At least one primary recipient is required")

    if settings.mail_provider == "brevo-api":
        if not _brevo_api_configured():
            raise EmailDeliveryError("Brevo API is not configured")

        payload: dict[str, object] = {
            "sender": {
                "name": settings.mail_from_name,
                "email": settings.mail_from_email,
            },
            "to": _recipient_payload(to),
            "subject": subject,
            "textContent": text_body,
            "htmlContent": html_body,
        }
        if cc:
            payload["cc"] = _recipient_payload(cc)
        if bcc:
            payload["bcc"] = _recipient_payload(bcc)

        request = urllib.request.Request(
            url=f"{settings.brevo_api_base_url.rstrip('/')}/smtp/email",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": settings.brevo_api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                status_code = getattr(response, "status", 200)
                if status_code >= 400:
                    body = response.read().decode("utf-8", errors="replace")
                    raise EmailDeliveryError(f"Brevo API responded with {status_code}: {body}")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.exception("Could not deliver HTML email via Brevo API")
            raise EmailDeliveryError(f"Brevo API {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            logger.exception("Could not reach Brevo API")
            raise EmailDeliveryError(str(exc.reason)) from exc
        return

    if not _smtp_configured():
        raise EmailDeliveryError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.mail_from_name} <{settings.mail_from_email}>"
    message["To"] = ", ".join(recipient["email"] for recipient in to)
    if cc:
        message["Cc"] = ", ".join(recipient["email"] for recipient in cc)
    if bcc:
        message["Bcc"] = ", ".join(recipient["email"] for recipient in bcc)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.mail_server, settings.mail_port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(settings.mail_username, settings.mail_password)
            smtp.send_message(message)
    except Exception as exc:  # pragma: no cover - transport failures depend on environment
        logger.exception("Could not deliver HTML email")
        raise EmailDeliveryError(str(exc)) from exc


def _send_via_brevo_api(*, recipient_email: str, recipient_name: str, reset_link: str) -> None:
    settings = get_settings()
    if not _brevo_api_configured():
        raise EmailDeliveryError("Brevo API is not configured")

    greeting_name = recipient_name.strip() or "there"
    payload = {
        "sender": {
            "name": settings.mail_from_name,
            "email": settings.mail_from_email,
        },
        "to": [
            {
                "email": recipient_email,
                "name": greeting_name,
            }
        ],
        "subject": "Reset your Market Watch password",
        "textContent": (
            f"Hello {greeting_name},\n\n"
            "We received a request to reset your Market Watch password.\n\n"
            "Use the link below to set a new password:\n"
            f"{reset_link}\n\n"
            f"This link expires in {settings.password_reset_token_ttl_minutes} minutes and can be used only once.\n\n"
            "If you did not request this, you can ignore this message.\n"
        ),
        "htmlContent": f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #16324f; line-height: 1.5;">
            <p>Hello {greeting_name},</p>
            <p>We received a request to reset your <strong>Market Watch</strong> password.</p>
            <p>
              <a href="{reset_link}" style="display: inline-block; padding: 10px 16px; border-radius: 8px; background: #2563eb; color: #ffffff; text-decoration: none;">
                Reset password
              </a>
            </p>
            <p>If the button does not work, use this link:</p>
            <p><a href="{reset_link}">{reset_link}</a></p>
            <p>This link expires in {settings.password_reset_token_ttl_minutes} minutes and can be used only once.</p>
            <p>If you did not request this, you can ignore this message.</p>
          </body>
        </html>
        """,
    }
    request = urllib.request.Request(
        url=f"{settings.brevo_api_base_url.rstrip('/')}/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": settings.brevo_api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status_code = getattr(response, "status", 200)
            if status_code >= 400:
                body = response.read().decode("utf-8", errors="replace")
                raise EmailDeliveryError(f"Brevo API responded with {status_code}: {body}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.exception("Could not deliver password reset email via Brevo API to %s", recipient_email)
        raise EmailDeliveryError(f"Brevo API {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        logger.exception("Could not reach Brevo API for %s", recipient_email)
        raise EmailDeliveryError(str(exc.reason)) from exc


def send_password_reset_email(*, recipient_email: str, recipient_name: str, reset_link: str) -> None:
    settings = get_settings()

    if settings.mail_provider == "brevo-api":
        _send_via_brevo_api(
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            reset_link=reset_link,
        )
        return

    if not _smtp_configured():
        raise EmailDeliveryError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = "Reset your Market Watch password"
    message["From"] = f"{settings.mail_from_name} <{settings.mail_from_email}>"
    message["To"] = recipient_email

    greeting_name = recipient_name.strip() or "there"
    text_body = (
        f"Hello {greeting_name},\n\n"
        "We received a request to reset your Market Watch password.\n\n"
        "Use the link below to set a new password:\n"
        f"{reset_link}\n\n"
        f"This link expires in {settings.password_reset_token_ttl_minutes} minutes and can be used only once.\n\n"
        "If you did not request this, you can ignore this message.\n"
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #16324f; line-height: 1.5;">
        <p>Hello {greeting_name},</p>
        <p>We received a request to reset your <strong>Market Watch</strong> password.</p>
        <p>
          <a href="{reset_link}" style="display: inline-block; padding: 10px 16px; border-radius: 8px; background: #2563eb; color: #ffffff; text-decoration: none;">
            Reset password
          </a>
        </p>
        <p>If the button does not work, use this link:</p>
        <p><a href="{reset_link}">{reset_link}</a></p>
        <p>This link expires in {settings.password_reset_token_ttl_minutes} minutes and can be used only once.</p>
        <p>If you did not request this, you can ignore this message.</p>
      </body>
    </html>
    """
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.mail_server, settings.mail_port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(settings.mail_username, settings.mail_password)
            smtp.send_message(message)
    except Exception as exc:  # pragma: no cover - transport failures depend on environment
        logger.exception("Could not deliver password reset email to %s", recipient_email)
        raise EmailDeliveryError(str(exc)) from exc
