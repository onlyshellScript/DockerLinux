import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(recipient, subject, message):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_host:
        return False, "SMTP_HOST not configured"

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [recipient], msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)


def send_whatsapp(recipient, message):
    api_url = os.getenv("WHATSAPP_API_URL")
    api_token = os.getenv("WHATSAPP_API_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    if not api_url:
        return False, "WHATSAPP_API_URL not configured"

    try:
        import requests
        resp = requests.post(
            f"{api_url}/messages",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "text",
                "text": {"body": message},
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return True, None
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except ImportError:
        return False, "requests library not installed"
    except Exception as e:
        return False, str(e)


def send_notification(channel, recipient, subject, message):
    if channel == "email":
        return send_email(recipient, subject or "SIGOS", message)
    elif channel == "whatsapp":
        return send_whatsapp(recipient, message)
    return False, f"unknown channel: {channel}"
