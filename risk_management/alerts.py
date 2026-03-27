# Alerts
import os
import requests
import smtplib
from email.mime.text import MIMEText
import logging

logger = logging.getLogger(__name__)

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
EMAIL_SMTP = os.environ.get("EMAIL_SMTP", "smtp.gmail.com")
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
EMAIL_TO = os.environ.get("EMAIL_TO", EMAIL_USER)

def send_discord(message):
    if not DISCORD_WEBHOOK:
        return False
    data = {"content": f"🚨 Alphamark Alert: {message}"}
    resp = requests.post(DISCORD_WEBHOOK, json=data)
    return resp.status_code == 204

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": f"🚨 Alphamark: {message}"}
    resp = requests.post(url, data=data)
    return resp.status_code == 200

def send_email(subject, body):
    if not EMAIL_USER or not EMAIL_PASS:
        return False
    msg = MIMEText(body)
    msg['Subject'] = f"Alphamark Alert: {subject}"
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    
    try:
        server = smtplib.SMTP(EMAIL_SMTP, 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return False

def send_alert(message, channels=None):
    """
    Send production-grade multi-channel alert.
    channels: list ['discord', 'telegram', 'email'] or None for all available
    """
    if channels is None:
        channels = []
        if DISCORD_WEBHOOK: channels.append('discord')
        if TELEGRAM_TOKEN: channels.append('telegram')
        if EMAIL_USER: channels.append('email')
    
    success = False
    if 'discord' in channels:
        success |= send_discord(message)
    if 'telegram' in channels:
        success |= send_telegram(message)
    if 'email' in channels:
        success |= send_email("Arbitrage Alert", message)
    
    logger.info(f"Alert sent: {success}")
    return success
