"""SMTP email notifier for the AI Research Desk."""

import smtplib
import sys
from email.mime.text import MIMEText

from src.config import load_config


def send_email(subject: str, body: str, to_address: str | None = None) -> bool:
    """Send a plain-text email via SMTP.

    Supports CC recipients via config email.cc_addresses (list of strings).

    Returns True on success, False on failure.
    """
    config = load_config()
    email_cfg = config.get("email", {})

    smtp_server = email_cfg.get("smtp_server", "")
    smtp_port = email_cfg.get("smtp_port", 587)
    use_tls = email_cfg.get("use_tls", True)
    username = email_cfg.get("username", "")
    password = email_cfg.get("password", "")
    from_address = email_cfg.get("from_address", username)
    recipient = to_address or email_cfg.get("to_address", "")
    cc_addresses = email_cfg.get("cc_addresses", [])

    if not smtp_server or not username or not password or not recipient:
        print("ERROR: Email configuration is incomplete. Check your settings.", file=sys.stderr)
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = recipient
    if cc_addresses:
        msg["Cc"] = ", ".join(cc_addresses)

    # Send to all recipients (To + CC)
    all_recipients = [recipient] + cc_addresses

    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        if use_tls:
            server.starttls()
        server.login(username, password)
        server.sendmail(from_address, all_recipients, msg.as_string())
        server.quit()
        return True
    except smtplib.SMTPAuthenticationError:
        print("ERROR: SMTP authentication failed. Check username/password.", file=sys.stderr)
        return False
    except smtplib.SMTPConnectError:
        print("ERROR: Could not connect to SMTP server.", file=sys.stderr)
        return False
    except ConnectionRefusedError:
        print("ERROR: Connection refused by SMTP server.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"ERROR: Failed to send email: {e}", file=sys.stderr)
        return False
