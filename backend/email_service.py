"""Kreeda Nation email delivery — thin wrapper around SendGrid.

All transactional emails (signup OTPs, password reset, booking notifications) flow through
this module so we have a single switch / single log surface.

Requires the env vars: SENDGRID_API_KEY, SENDER_EMAIL, optional SENDER_NAME.

If the API key is missing OR the call to SendGrid raises, the function returns False and
logs the failure but does NOT raise — callers (e.g., signup OTP) decide whether to abort
or fall back to logging the credential.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger("kreeda.email")


def is_email_configured() -> bool:
    return bool(os.environ.get("SENDGRID_API_KEY") and os.environ.get("SENDER_EMAIL"))


def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    plain: Optional[str] = None,
) -> bool:
    """Send a single email. Returns True on SendGrid 2xx, False otherwise.

    Never raises — caller decides how to react to a failure.
    """
    api_key = os.environ.get("SENDGRID_API_KEY")
    sender = os.environ.get("SENDER_EMAIL")
    sender_name = os.environ.get("SENDER_NAME", "Kreeda Nation")
    if not (api_key and sender):
        logger.error("Email not sent — SENDGRID_API_KEY / SENDER_EMAIL not configured. to=%s subject=%s", to, subject)
        return False
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, From
    except Exception:
        logger.exception("sendgrid SDK not installed")
        return False
    msg = Mail(
        from_email=From(sender, sender_name),
        to_emails=to,
        subject=subject,
        plain_text_content=plain or _html_to_text(html),
        html_content=html,
    )
    try:
        resp = SendGridAPIClient(api_key).send(msg)
    except Exception as e:
        logger.error("SendGrid send failed: to=%s subject=%s err=%s", to, subject, e)
        return False
    ok = 200 <= resp.status_code < 300
    if not ok:
        logger.error("SendGrid non-2xx: to=%s subject=%s status=%s body=%s",
                     to, subject, resp.status_code, getattr(resp, "body", b"")[:300])
    else:
        logger.info("Email sent: to=%s subject=%s status=%s", to, subject, resp.status_code)
    return ok


def _html_to_text(html: str) -> str:
    import re
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


# ---------- Branded templates ----------
def send_otp_email(to: str, otp: str, company_name: str = "") -> bool:
    subject = f"Your Kreeda Nation verification code: {otp}"
    greeting = f"Hi{(' ' + company_name) if company_name else ''},"
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e5e5e5;padding:32px 20px;">
      <div style="max-width:560px;margin:auto;background:#141414;border:1px solid #ffffff14;border-radius:6px;padding:32px;">
        <div style="font-size:11px;letter-spacing:.3em;color:#84CC16;text-transform:uppercase;font-family:ui-monospace,monospace;">/ Verify your email</div>
        <h1 style="font-size:30px;letter-spacing:.05em;margin:12px 0 24px;color:#fff;">KREEDA NATION</h1>
        <p>{greeting}</p>
        <p>To finish creating your company workspace on Kreeda Nation, enter this 6-digit code on the signup page:</p>
        <div style="font-size:42px;letter-spacing:.4em;font-weight:700;color:#84CC16;background:#0a0a0a;border:1px solid #84CC1640;border-radius:4px;padding:18px;text-align:center;margin:24px 0;font-family:ui-monospace,monospace;">{otp}</div>
        <p style="font-size:13px;color:#a3a3a3;">The code expires in <b>10 minutes</b>. If you didn't request this, you can safely ignore the email — no account will be created.</p>
        <hr style="border:none;border-top:1px solid #ffffff14;margin:28px 0;"/>
        <p style="font-size:11px;color:#737373;font-family:ui-monospace,monospace;text-transform:uppercase;letter-spacing:.2em;">Kreeda Nation · Where teams compete, connect &amp; grow</p>
      </div>
    </div>
    """
    return send_email(to=to, subject=subject, html=html)
