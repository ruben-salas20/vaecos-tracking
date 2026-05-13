"""Notificaciones por email (opcional).

Se configura por variables de entorno. Si no están todas las requeridas, el
notifier loguea a consola pero no falla — el runner sigue sin interrupciones.

Env vars:
    NOTIFY_EMAIL       — destinatario (puede ser uno o varios separados por coma)
    SMTP_HOST          — ej. smtp.gmail.com
    SMTP_PORT          — ej. 587 (STARTTLS) o 465 (SSL)
    SMTP_USER          — usuario SMTP
    SMTP_PASSWORD      — password de aplicación
    SMTP_FROM          — From: del email (default: SMTP_USER)
    SMTP_USE_SSL       — "true" para SSL/465; default STARTTLS/587
"""
from __future__ import annotations

import os
import re
import smtplib
import ssl
import sys
from dataclasses import dataclass
from email.message import EmailMessage


def _safe_int_env(name: str, default: int) -> int:
    """Lee un env var como int tolerando basura tipo '587 # comentario'.

    Algunos .env mal parseados pueden dejar comentarios inline en os.environ.
    En lugar de explotar con ValueError, sacamos los dígitos del inicio.
    """
    raw = os.environ.get(name, "")
    if not raw:
        return default
    m = re.match(r"\s*(-?\d+)", raw)
    return int(m.group(1)) if m else default


@dataclass(frozen=True)
class NotifierConfig:
    enabled: bool
    to_addresses: tuple[str, ...]
    host: str
    port: int
    user: str
    password: str
    from_addr: str
    use_ssl: bool


def _clean_str_env(name: str, default: str = "") -> str:
    """Lee env var como string, tolerando comentarios inline tipo 'value # comment'."""
    raw = os.environ.get(name, default)
    if not raw:
        return default
    # Si tiene un '#' precedido por whitespace, cortar ahí (defensivo contra dotenv mal parseado)
    if not raw.startswith(('"', "'")):
        m = re.search(r"\s+#", raw)
        if m:
            raw = raw[: m.start()]
    return raw.strip()


def _load_config() -> NotifierConfig:
    to_raw = _clean_str_env("NOTIFY_EMAIL")
    host = _clean_str_env("SMTP_HOST")
    port = _safe_int_env("SMTP_PORT", 587)
    user = _clean_str_env("SMTP_USER")
    password = _clean_str_env("SMTP_PASSWORD")
    from_addr = _clean_str_env("SMTP_FROM", user) or user
    use_ssl_raw = _clean_str_env("SMTP_USE_SSL", "false").lower()
    use_ssl = use_ssl_raw in ("1", "true", "yes", "on")

    to_addresses = tuple(a.strip() for a in to_raw.split(",") if a.strip())
    enabled = bool(to_addresses and host and user and password)
    return NotifierConfig(
        enabled=enabled,
        to_addresses=to_addresses,
        host=host,
        port=port,
        user=user,
        password=password,
        from_addr=from_addr or user,
        use_ssl=use_ssl,
    )


def notify(
    subject: str,
    body: str,
    *,
    html: str | None = None,
    prefix: str = "[VAECOS Effi]",
) -> bool:
    """Manda email si está configurado. Si `html` se da, lo envía como
    multipart/alternative (texto plano + HTML). Si no, solo texto. Nunca raise."""
    full_subject = f"{prefix} {subject}".strip()
    config = _load_config()

    if not config.enabled:
        print(f"[notifier:disabled] {full_subject}\n{body}", file=sys.stderr)
        return False

    msg = EmailMessage()
    msg["From"] = config.from_addr
    msg["To"] = ", ".join(config.to_addresses)
    msg["Subject"] = full_subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        if config.use_ssl:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(config.host, config.port, context=ctx, timeout=15) as s:
                s.login(config.user, config.password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(config.host, config.port, timeout=15) as s:
                s.ehlo()
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
                s.login(config.user, config.password)
                s.send_message(msg)
        return True
    except Exception as e:
        print(f"[notifier:error] {e}\nSubject: {full_subject}\n{body}", file=sys.stderr)
        return False
