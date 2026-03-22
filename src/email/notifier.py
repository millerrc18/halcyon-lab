"""SMTP notifier placeholder for MVP.

Implement real sending only after local config and credential handling are finalized.
"""


def send_email(subject: str, body: str, to_address: str) -> None:
    print("EMAIL PLACEHOLDER")
    print(f"To: {to_address}")
    print(f"Subject: {subject}")
    print(body)
