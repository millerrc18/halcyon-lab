"""SMTP email notifier for the AI Research Desk."""

import smtplib
from email.mime.text import MIMEText

from src.config import load_config


def send_email(subject: str, body: str, to_address: str | None = None) -> bool:
    """Send a plain-text email via SMTP.

    Returns True on success, False on failure.
    """
    config = load_config()
    email_cfg = config.get("email", {})

    smtp_server = email_cfg.get("smtp_server")
    smtp_port = email_cfg.get("smtp_port", 587)
    use_tls = email_cfg.get("use_tls", True)
    username = email_cfg.get("username")
    password = email_cfg.get("password")
    from_address = email_cfg.get("from_address", username)
    recipient = to_address or email_cfg.get("to_address")

    if not all([smtp_server, username, password, recipient]):
        print("ERROR: Email config incomplete. Check config/settings.local.yaml.")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = recipient

    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        if use_tls:
            server.starttls()
        server.login(username, password)
        server.sendmail(from_address, [recipient], msg.as_string())
        server.quit()
        return True
    except smtplib.SMTPAuthenticationError:
        print("ERROR: SMTP authentication failed. Check username/password.")
        return False
    except smtplib.SMTPConnectError:
        print(f"ERROR: Could not connect to {smtp_server}:{smtp_port}.")
        return False
    except Exception as e:
        print(f"ERROR: Email send failed: {e}")
        return False
