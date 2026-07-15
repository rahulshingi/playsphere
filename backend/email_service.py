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

    Test-mode: when `EMAIL_MODE=mock` (set by the test runner via
    conftest.py), returns True without hitting SendGrid — prevents test
    suites from burning through the daily quota.
    """
    if os.environ.get("EMAIL_MODE") == "mock":
        logger.info("[EMAIL MOCK] to=%s subject=%s", to, subject)
        return True
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
    return bool(ok)


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
        <p>To finish creating your Kreeda Nation account, enter this 6-digit code on the signup page:</p>
        <div style="font-size:42px;letter-spacing:.4em;font-weight:700;color:#84CC16;background:#0a0a0a;border:1px solid #84CC1640;border-radius:4px;padding:18px;text-align:center;margin:24px 0;font-family:ui-monospace,monospace;">{otp}</div>
        <p style="font-size:13px;color:#a3a3a3;">The code expires in <b>10 minutes</b>. If you didn't request this, you can safely ignore the email — no account will be created.</p>
        <hr style="border:none;border-top:1px solid #ffffff14;margin:28px 0;"/>
        <p style="font-size:11px;color:#737373;font-family:ui-monospace,monospace;text-transform:uppercase;letter-spacing:.2em;">Kreeda Nation · Where teams compete, connect &amp; grow</p>
      </div>
    </div>
    """
    return send_email(to=to, subject=subject, html=html)


def send_password_reset_email(to: str, reset_url: str, name: str = "") -> bool:
    """One-time password-reset link mail for any account type (HR, vendor, player, admin)."""
    subject = "Reset your Kreeda Nation password"
    greeting = f"Hi{(' ' + name) if name else ''},"
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e5e5e5;padding:32px 20px;">
      <div style="max-width:560px;margin:auto;background:#141414;border:1px solid #ffffff14;border-radius:6px;padding:32px;">
        <div style="font-size:11px;letter-spacing:.3em;color:#84CC16;text-transform:uppercase;font-family:ui-monospace,monospace;">/ Password reset</div>
        <h1 style="font-size:30px;letter-spacing:.05em;margin:12px 0 24px;color:#fff;">KREEDA NATION</h1>
        <p>{greeting}</p>
        <p>We received a request to reset the password for this email. Click the button below to choose a new one:</p>
        <p style="text-align:center;margin:28px 0;">
          <a href="{reset_url}" style="display:inline-block;background:#84CC16;color:#000;font-weight:700;padding:14px 32px;border-radius:4px;text-decoration:none;letter-spacing:.05em;">RESET MY PASSWORD</a>
        </p>
        <p style="font-size:12px;color:#a3a3a3;">Or paste this link into your browser:</p>
        <p style="font-size:12px;color:#84CC16;word-break:break-all;font-family:ui-monospace,monospace;">{reset_url}</p>
        <p style="font-size:13px;color:#a3a3a3;margin-top:24px;">The link expires in <b>1 hour</b>. If you didn't request this, you can safely ignore the email — your password won't change.</p>
        <hr style="border:none;border-top:1px solid #ffffff14;margin:28px 0;"/>
        <p style="font-size:11px;color:#737373;font-family:ui-monospace,monospace;text-transform:uppercase;letter-spacing:.2em;">Kreeda Nation · Where teams compete, connect &amp; grow</p>
      </div>
    </div>
    """
    return send_email(to=to, subject=subject, html=html)



def send_welcome_email(to: str, name: str, temp_password: Optional[str], login_url: str = "") -> bool:
    """Sent to a player when an organiser/HR/admin auto-creates their account
    while adding them to a team. Includes the login URL, their email, and a
    temporary password. Player must reset on first login (must_reset flag on
    the user doc)."""
    subject = "Welcome to Kreeda Nation — your account is ready"
    login_link = login_url or "https://kreedanation.com/login"
    greeting = f"Hi{(' ' + name) if name else ''},"
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e5e5e5;padding:32px 20px;">
      <div style="max-width:560px;margin:auto;background:#141414;border:1px solid #ffffff14;border-radius:6px;padding:32px;">
        <div style="font-size:11px;letter-spacing:.3em;color:#84CC16;text-transform:uppercase;font-family:ui-monospace,monospace;">/ Welcome to Kreeda Nation</div>
        <h1 style="font-size:30px;letter-spacing:.05em;margin:12px 0 24px;color:#fff;">YOUR PLAYER ACCOUNT IS READY</h1>
        <p>{greeting}</p>
        <p>Someone added you to a match team on Kreeda Nation, so we've created a player profile for you. Log in with the details below to see your matches, record your stats, and connect with teammates.</p>
        <div style="background:#0a0a0a;border:1px solid #ffffff14;border-radius:4px;padding:16px;margin:20px 0;font-family:ui-monospace,monospace;">
          <div style="font-size:10px;color:#737373;text-transform:uppercase;letter-spacing:.2em;margin-bottom:8px;">Login</div>
          <div style="font-size:14px;color:#84CC16;">Email: {to}</div>
          <div style="font-size:14px;color:#84CC16;margin-top:6px;">Temporary password: <b>{temp_password or '(please use forgot-password)'}</b></div>
        </div>
        <p style="text-align:center;margin:28px 0;">
          <a href="{login_link}" style="display:inline-block;background:#84CC16;color:#000;font-weight:700;padding:14px 32px;border-radius:4px;text-decoration:none;letter-spacing:.05em;">SIGN IN &amp; SET YOUR PASSWORD</a>
        </p>
        <p style="font-size:13px;color:#a3a3a3;">You'll be asked to change this temporary password on first login for security. If you'd rather not use this account, ignore this email — the profile won't affect your privacy.</p>
        <hr style="border:none;border-top:1px solid #ffffff14;margin:28px 0;"/>
        <p style="font-size:11px;color:#737373;font-family:ui-monospace,monospace;text-transform:uppercase;letter-spacing:.2em;">Kreeda Nation · Where teams compete, connect &amp; grow</p>
      </div>
    </div>
    """
    return send_email(to=to, subject=subject, html=html)


def send_admin_password_reset_email(to: str, temp_password: str, reset_url: str, name: str = "") -> bool:
    """Sent when a platform-admin resets a user's password from the Users tab.

    Shows the temp password + a one-hour reset link so the user can jump straight
    to picking a permanent password. Reuses the existing dark-branded template.
    """
    subject = "Your Kreeda Nation password was reset by an admin"
    greeting = f"Hi{(' ' + name) if name else ''},"
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e5e5e5;padding:32px 20px;">
      <div style="max-width:560px;margin:auto;background:#141414;border:1px solid #ffffff14;border-radius:6px;padding:32px;">
        <div style="font-size:11px;letter-spacing:.3em;color:#F59E0B;text-transform:uppercase;font-family:ui-monospace,monospace;">/ Admin-triggered password reset</div>
        <h1 style="font-size:26px;letter-spacing:.05em;margin:12px 0 24px;color:#fff;">YOUR PASSWORD WAS RESET</h1>
        <p>{greeting}</p>
        <p>A Kreeda Nation platform admin has reset the password for your account. Your <b>temporary password</b> is below — use it to sign in, or click the button to pick a new one right away.</p>
        <div style="background:#0a0a0a;border:1px solid #ffffff14;border-radius:4px;padding:16px;margin:20px 0;font-family:ui-monospace,monospace;">
          <div style="font-size:10px;color:#737373;text-transform:uppercase;letter-spacing:.2em;margin-bottom:8px;">Temporary sign-in</div>
          <div style="font-size:14px;color:#e5e5e5;">Email: {to}</div>
          <div style="font-size:14px;color:#F59E0B;margin-top:6px;">Password: <b>{temp_password}</b></div>
        </div>
        <p style="text-align:center;margin:28px 0;">
          <a href="{reset_url}" style="display:inline-block;background:#84CC16;color:#000;font-weight:700;padding:14px 32px;border-radius:4px;text-decoration:none;letter-spacing:.05em;">SET A NEW PASSWORD</a>
        </p>
        <p style="font-size:12px;color:#a3a3a3;">Or paste this link in your browser (valid for 1 hour):</p>
        <p style="font-size:12px;color:#84CC16;word-break:break-all;font-family:ui-monospace,monospace;">{reset_url}</p>
        <p style="font-size:13px;color:#a3a3a3;margin-top:24px;">If you didn't expect this reset, please contact <a style="color:#84CC16;" href="mailto:contact@kreedanation.com">contact@kreedanation.com</a> right away.</p>
        <hr style="border:none;border-top:1px solid #ffffff14;margin:28px 0;"/>
        <p style="font-size:11px;color:#737373;font-family:ui-monospace,monospace;text-transform:uppercase;letter-spacing:.2em;">Kreeda Nation · Where teams compete, connect &amp; grow</p>
      </div>
    </div>
    """
    return send_email(to=to, subject=subject, html=html)

