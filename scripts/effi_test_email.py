"""Prueba la configuración SMTP enviando un email de test.

Usage:
    python scripts/effi_test_email.py                     # usa NOTIFY_EMAIL como destinatario
    python scripts/effi_test_email.py otra@dominio.com    # override del destinatario
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v0.4"))

from app.effi_guides.effi_config import load_settings  # noqa: E402 (carga .env)
from app.effi_guides.notifier import _load_config, notify  # noqa: E402


def main() -> int:
    load_settings()  # asegurar que .env esté cargado en os.environ
    cfg = _load_config()

    print("─── Configuración SMTP detectada ───")
    print(f"  enabled       : {cfg.enabled}")
    print(f"  destinatarios : {', '.join(cfg.to_addresses) or '(vacío)'}")
    print(f"  SMTP host     : {cfg.host or '(vacío)'}")
    print(f"  SMTP port     : {cfg.port}")
    print(f"  SMTP user     : {cfg.user or '(vacío)'}")
    print(f"  SMTP password : {'(set, {} chars)'.format(len(cfg.password)) if cfg.password else '(vacío)'}")
    print(f"  SMTP from     : {cfg.from_addr or '(vacío)'}")
    print(f"  SSL puro      : {cfg.use_ssl} (false = STARTTLS)")
    print()

    if not cfg.enabled:
        print("✗ El notifier está DESACTIVADO. Faltan variables en .env:")
        missing = []
        if not cfg.to_addresses: missing.append("NOTIFY_EMAIL")
        if not cfg.host:         missing.append("SMTP_HOST")
        if not cfg.user:         missing.append("SMTP_USER")
        if not cfg.password:     missing.append("SMTP_PASSWORD")
        for m in missing:
            print(f"    - {m}")
        return 2

    # Si pasaron destinatario por arg, override temporal vía env (notifier lee de ahí).
    if len(sys.argv) > 1:
        os.environ["NOTIFY_EMAIL"] = sys.argv[1]
        print(f"→ Destinatario override: {sys.argv[1]}")
        cfg = _load_config()

    print("→ Enviando email de prueba...")
    body = (
        "Si recibís este mensaje, la configuración SMTP de VAECOS está OK.\n\n"
        "Detalles:\n"
        f"  Host: {cfg.host}:{cfg.port}\n"
        f"  Usuario: {cfg.user}\n"
        f"  From: {cfg.from_addr}\n"
        f"  Para: {', '.join(cfg.to_addresses)}\n\n"
        "De aquí en adelante el bot Effi mandará mails automáticamente cuando:\n"
        "  - La sesión Effi expire (no puede entrar al ERP)\n"
        "  - Una orden requiera revisión humana (escalation)\n"
        "  - Una corrida real con --apply mueva órdenes (resumen)\n"
        "  - Un error fatal interrumpa el flujo\n"
    )
    ok = notify(
        subject="Test de configuración SMTP",
        body=body,
        prefix="[VAECOS Effi]",
    )

    if ok:
        print(f"✓ Email enviado correctamente a {', '.join(cfg.to_addresses)}.")
        print("  Revisá tu bandeja de entrada (y spam por si acaso).")
        return 0
    print("✗ El envío falló. Mirá las líneas '[notifier:error]' arriba para el detalle.")
    print()
    print("Causas comunes:")
    print("  - Gmail: necesitás 'App password' (16 chars), NO tu contraseña real.")
    print("           Generala en https://myaccount.google.com/apppasswords")
    print("  - Puerto incorrecto: 587 → STARTTLS (SMTP_USE_SSL=false)")
    print("                       465 → SSL puro  (SMTP_USE_SSL=true)")
    print("  - SMTP_HOST mal escrito (ej. smtp.gmail.com, no smtp.google.com)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
