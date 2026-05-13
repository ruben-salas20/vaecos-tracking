"""Login interactivo a Effi ERP. Guarda la sesión (cookies + localStorage) en EFFI_SESSION_PATH.

Modos:
  python scripts/effi_login.py             → headed Chromium, auto-fill, vos confirmás y enviás.
  python scripts/effi_login.py --auto      → headed, intenta login completo y submit automático.
  python scripts/effi_login.py --headless  → invisible (solo si NO hay reCAPTCHA visible).

Una vez logueado, se guarda effi-session.json en EFFI_SESSION_PATH para que el bot la reuse.
La sesión típicamente dura semanas — repetir solo cuando el bot reporte sesión expirada.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Permitir ejecutar el script desde la raíz del repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v0.4"))

from app.effi_guides.effi_config import load_settings  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Login a Effi ERP y guarda storageState.")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Intenta llenar credenciales y submitear automáticamente.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Modo headless (solo si reCAPTCHA está deshabilitado).",
    )
    args = parser.parse_args()

    settings = load_settings()
    if not settings.username or not settings.password:
        print("ERROR: EFFI_USERNAME y EFFI_PASSWORD deben estar definidos en .env", file=sys.stderr)
        return 2

    print(f"→ Abriendo Chromium ({'headless' if args.headless else 'headed'})...")
    print(f"→ URL login: {settings.login_url}")
    print(f"→ Session destino: {settings.session_path}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        context = browser.new_context()
        context.set_default_timeout(settings.navigation_timeout_ms)
        page = context.new_page()

        page.goto(settings.login_url, wait_until="domcontentloaded")

        # Auto-fill de credenciales (campos típicos por nombre/id).
        try:
            for sel in ("input[name='email']", "input[type='email']", "input[name='usuario']", "#email"):
                if page.locator(sel).count() > 0:
                    page.locator(sel).first.fill(settings.username)
                    break
            for sel in ("input[name='password']", "input[type='password']", "#password"):
                if page.locator(sel).count() > 0:
                    page.locator(sel).first.fill(settings.password)
                    break
        except Exception as e:
            print(f"⚠ No pude auto-fillar campos: {e}")

        if args.auto:
            # Intento de submit. Si reCAPTCHA está activo y bloquea, el redirect no ocurrirá.
            try:
                for sel in (
                    "button[type='submit']",
                    "button:has-text('Ingresar')",
                    "button:has-text('Iniciar')",
                    "input[type='submit']",
                ):
                    if page.locator(sel).count() > 0:
                        page.locator(sel).first.click()
                        break
            except Exception as e:
                print(f"⚠ No pude clickear submit: {e}")

            try:
                page.wait_for_url(f"{settings.base_url}/app/**", timeout=15000)
                print("✓ Login automático exitoso.")
            except Exception:
                print("⚠ Auto-login no terminó solo (posible reCAPTCHA). Resolvé el desafío en la ventana y presioná Enter aquí.")
                input()
        else:
            print("→ Credenciales prellenadas. Resolvé reCAPTCHA si aparece y dale 'Ingresar' manualmente.")
            print("  Cuando ya estés dentro del app (URL contiene /app/), presioná Enter aquí.")
            input()

        # Pequeño wait extra para asegurar que todas las cookies se setearon.
        time.sleep(1.5)

        if "/ingreso" in page.url:
            print(f"✗ Aún en /ingreso. URL actual: {page.url}")
            print("  La sesión NO se guardó. Reintentá.")
            browser.close()
            return 1

        settings.session_path.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(settings.session_path))
        print(f"✓ Sesión guardada en: {settings.session_path}")
        print(f"  URL final: {page.url}")
        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
