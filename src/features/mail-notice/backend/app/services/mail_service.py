from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import Config
from app.logger import write

KIND_LABEL = {"event": "予定", "todo": "TODO"}


def kind_label(kind: str) -> str:
    return KIND_LABEL.get(kind, kind)


def build_subject(kind: str, title: str) -> str:
    return f"【{kind_label(kind)}】{title}"


def build_body(title: str, start_text: str) -> str:
    return f"タイトル: {title}\n開始: {start_text}\n"


def send_mail(cfg: Config, to_addr: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = cfg.smtp_from
    message["To"] = to_addr
    message.set_content(body)
    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as client:
        client.ehlo()
        if client.has_extn("starttls"):
            client.starttls()
            client.ehlo()
        if cfg.smtp_username:
            client.login(cfg.smtp_username, cfg.smtp_password)
        client.send_message(message)
    write("DBG", f"SMTP送信 to_set={bool(to_addr)} subject_len={len(subject)}")
