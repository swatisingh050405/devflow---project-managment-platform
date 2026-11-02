import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_password_reset_email(email: str, reset_link: str):
    message = EmailMessage()

    message["Subject"] = "DevFlow Password Reset"
    message["From"] = settings.MAIL_FROM
    message["To"] = email

    message.set_content(
        f"""
Hello,

We received a request to reset your DevFlow password.

Use the following link to reset your password:

{reset_link}

This link expires in 15 minutes.

If you did not request this, ignore this email.
"""
    )

    with smtplib.SMTP_SSL(
        settings.SMTP_HOST,
        settings.SMTP_PORT
    ) as smtp:
        smtp.login(
            settings.SMTP_USERNAME,
            settings.SMTP_PASSWORD
        )
        smtp.send_message(message)