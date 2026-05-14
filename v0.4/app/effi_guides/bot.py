"""Bot de Playwright para automatizar el flujo Orden→Remisión→Guía en Effi ERP.

Diseñado contra el mapa de selectores documentado en `docs/EFFI_AUTOMATION_HANDOFF.md`.
Los selectores y tiempos pueden requerir ajuste cuando se valide contra el DOM real
(no fue posible probarlos sin conexión a Effi).

Uso típico:

    settings = load_settings()
    with EffiBot(settings) as bot:
        if not bot.health_check():
            raise NotLoggedInError("renovar effi-session.json")
        orders = bot.list_orders()
        for o in orders:
            if not o.needs_processing:
                continue
            detail = bot.get_order_detail(o.orden_id)
            ...  # classify + decide
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date, timedelta

from playwright.sync_api import (
    sync_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

from .classifier import OrderProduct, ProcessingPlan
from .effi_config import EffiSettings


# ──────────────────────────────────────────────────────────────────────
# Tipos públicos
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScrapedOrder:
    """Una fila de /app/orden_v leída del DOM."""
    orden_id: int
    cliente: str           # texto crudo de la celda 5 (nombre + DPI + teléfono + dirección concatenados)
    direccion: str         # extraído heurísticamente del texto de cliente
    telefono: str          # extraído heurísticamente (8 dígitos contiguos, formato GT)
    estado: str            # texto crudo de la última celda
    needs_processing: bool # True si "PEDIDO CONFIRMADO" sin "Remisión #N" en estado


@dataclass(frozen=True)
class OrderDetail:
    """Detalle de una orden leído del modal de remisión (sin submit)."""
    orden_id: int
    cliente: str
    direccion: str
    productos: list[OrderProduct]


# ──────────────────────────────────────────────────────────────────────
# Excepciones
# ──────────────────────────────────────────────────────────────────────


class EffiBotError(Exception):
    pass


class NotLoggedInError(EffiBotError):
    """Se redirigió a /ingreso — la sesión expiró o nunca existió."""


# ──────────────────────────────────────────────────────────────────────
# Helpers puros
# ──────────────────────────────────────────────────────────────────────


_RE_REMISION_REF = re.compile(r"Remisi[oó]n\s*#\d+", re.IGNORECASE)
_RE_PHONE_GT = re.compile(r"\b(\d{8})\b")
# Línea explícita "Dirección: ..." dentro de la celda multi-línea de cliente.
_RE_DIRECCION_LINE = re.compile(
    r"Direcci[oó]n\s*:\s*(.+?)(?:\s*\n|\s*$)",
    re.IGNORECASE,
)
# Línea explícita "Teléfono: ..." (para extraer telefono evitando confundirlo con el DPI).
_RE_PHONE_LINE = re.compile(
    r"Tel[eé]fono\s*:\s*(\d+)",
    re.IGNORECASE,
)


def needs_processing(estado: str) -> bool:
    """Una orden se procesa si está en PEDIDO CONFIRMADO sin "Remisión #N" en el estado."""
    if not estado or "PEDIDO CONFIRMADO" not in estado.upper():
        return False
    return _RE_REMISION_REF.search(estado) is None


def compute_fecha_envio(today: date | None = None) -> str:
    return (today or date.today()).strftime("%Y-%m-%d")


def compute_fecha_entrega(today: date | None = None, business_days: int = 3) -> str:
    """today + N días, excluyendo solamente domingos (confirmado por el dueño, sin feriados)."""
    d = today or date.today()
    added = 0
    while added < business_days:
        d = d + timedelta(days=1)
        if d.weekday() == 6:  # 6 = domingo en weekday()
            continue
        added += 1
    return d.strftime("%Y-%m-%d")


_RE_NOMBRE_LINE = re.compile(r"(?i)^\s*nombre\s*:\s*(.+?)\s*$")
_RE_PREFIX_LINE = re.compile(r"(?i)^\s*(dpi|tel[eé]fono|direcci[oó]n|email|correo|nit)\s*:")
_RE_CARGO_TRACKING = re.compile(r"\bB\d{6,}-\d+\b")


def _extract_name(cell_text: str) -> str:
    """Extrae el nombre del cliente de la celda multi-línea.

    Estrategia:
      1. Si aparece línea explícita 'Nombre: X', devolver X.
      2. Si no, primera línea no vacía que NO empiece con prefijo conocido
         (DPI:, Teléfono:, Dirección:, Email:, NIT:).
    """
    if not cell_text:
        return ""
    for raw_line in cell_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _RE_NOMBRE_LINE.match(line)
        if m:
            return m.group(1).strip()
        if not _RE_PREFIX_LINE.match(line):
            return line
    return cell_text.strip()


def _extract_phone(cell_text: str) -> str:
    """Extrae teléfono. Prefiere la línea explícita 'Teléfono:'; si no existe,
    cae al primer bloque de 8 dígitos contiguos (formato GT).
    """
    if not cell_text:
        return ""
    m = _RE_PHONE_LINE.search(cell_text)
    if m:
        return m.group(1)
    m = _RE_PHONE_GT.search(cell_text)
    return m.group(1) if m else ""


def _extract_direccion(cell_text: str) -> str:
    """Extrae la dirección de la celda multi-línea.

    Formato típico:
        Susana Hernandez
        DPI: 42925233
        Teléfono: 42925233
        Dirección: Guatemala / Guatemala / ... / 5ta avenida 3-51

    Estrategia:
      1. Si aparece 'Dirección:' explícito, devolver todo lo que viene después
         (hasta el final del campo — puede tener slashes, etc.).
      2. Si no, fallback: lo que viene después del último bloque de 8 dígitos
         que esté en una línea con 'Teléfono:'.
      3. Si nada de eso, devolver toda la celda.
    """
    if not cell_text:
        return ""
    m = _RE_DIRECCION_LINE.search(cell_text)
    if m:
        # Tomar TODO desde el final del prefijo "Dirección:" hasta el final del texto,
        # no solo la primera línea (algunas direcciones tienen saltos).
        idx = m.start(1)
        return cell_text[idx:].strip()
    # Fallback: usar la línea Teléfono como pivote (evita confundir con DPI).
    m = _RE_PHONE_LINE.search(cell_text)
    if m:
        return cell_text[m.end():].strip()
    return cell_text.strip()


# ──────────────────────────────────────────────────────────────────────
# Bot
# ──────────────────────────────────────────────────────────────────────


class EffiBot:
    """Wrapper de Playwright para el flujo Effi. Usar como context manager."""

    def __init__(self, settings: EffiSettings, *, headless_override: bool | None = None):
        """`headless_override=True` fuerza headless aunque settings diga lo contrario.
        Útil para jobs background (UI/cron) que NUNCA deben mostrar navegador."""
        self.settings = settings
        self._headless = settings.headless if headless_override is None else headless_override
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # ── lifecycle ────────────────────────────────────────────────────

    def __enter__(self) -> "EffiBot":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self._headless)

        storage_state = (
            str(self.settings.session_path)
            if self.settings.session_path.exists()
            else None
        )

        self._context = self._browser.new_context(storage_state=storage_state)
        self._context.set_default_timeout(self.settings.navigation_timeout_ms)
        self._page = self._context.new_page()

        # Auto-aceptar diálogos nativos del navegador (alert / confirm / prompt).
        # Effi a veces muestra confirm("¿Está seguro?") al crear remisión o guía;
        # sin handler Playwright las dismisses por default y el submit se cancela
        # silenciosamente, dejando "Pre-existing=N, current=N" en _read_new_id.
        self._page.on("dialog", lambda d: d.accept())

        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._page is not None:
                self._page.close()
        except Exception:
            pass
        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        if self._pw is not None:
            self._pw.stop()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("EffiBot debe usarse dentro de 'with'")
        return self._page

    # ── sesión ───────────────────────────────────────────────────────

    def save_session(self) -> None:
        """Guarda el storageState actual en EFFI_SESSION_PATH (cookies + localStorage)."""
        if self._context is None:
            raise RuntimeError("EffiBot debe usarse dentro de 'with'")
        self.settings.session_path.parent.mkdir(parents=True, exist_ok=True)
        self._context.storage_state(path=str(self.settings.session_path))

    def health_check(self) -> bool:
        """True si /app/calendario carga sin redirigir a /ingreso."""
        try:
            self.page.goto(self.settings.calendario_url, wait_until="domcontentloaded")
        except PlaywrightTimeoutError:
            return False
        return "/ingreso" not in self.page.url

    def try_auto_login(self) -> bool:
        """Intenta re-loguear usando EFFI_USERNAME/EFFI_PASSWORD del .env.

        Caso de uso: el cron horario detecta sesión expirada y NO queremos esperar
        que un humano renueve `effi-session.json` antes del próximo run. Si Effi
        tiene reCAPTCHA activo o las creds están mal, esto falla y el caller debe
        notificar como hoy.

        En éxito: persiste el nuevo `storageState` vía `save_session()` y devuelve
        True. En fallo: devuelve False sin tocar el archivo de sesión existente.
        """
        if not self.settings.username or not self.settings.password:
            print("  [auto-login] EFFI_USERNAME/EFFI_PASSWORD no configurados — skip")
            return False

        try:
            self.page.goto(self.settings.login_url, wait_until="domcontentloaded")
        except Exception as e:
            print(f"  [auto-login] goto login falló: {e}")
            return False

        # Llenar credenciales con selectores típicos.
        filled_user = False
        for sel in ("input[name='email']", "input[type='email']", "input[name='usuario']", "#email"):
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0:
                    loc.first.fill(self.settings.username)
                    filled_user = True
                    break
            except Exception:
                continue
        filled_pass = False
        for sel in ("input[name='password']", "input[type='password']", "#password"):
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0:
                    loc.first.fill(self.settings.password)
                    filled_pass = True
                    break
            except Exception:
                continue

        if not (filled_user and filled_pass):
            print(f"  [auto-login] no pude llenar credenciales (user={filled_user}, pass={filled_pass})")
            return False

        # Submit.
        clicked = False
        for sel in (
            "button[type='submit']",
            "button:has-text('Ingresar')",
            "button:has-text('Iniciar')",
            "input[type='submit']",
        ):
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0:
                    loc.first.click()
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            print("  [auto-login] no encontré botón de submit")
            return False

        # Esperar redirect a /app/. Si reCAPTCHA bloquea, esto timeoutea.
        try:
            self.page.wait_for_url(f"{self.settings.base_url}/app/**", timeout=15000)
        except PlaywrightTimeoutError:
            current = self.page.url
            print(f"  [auto-login] timeout esperando redirect — URL actual: {current}")
            # Probable reCAPTCHA o credenciales rechazadas.
            return False
        except Exception as e:
            print(f"  [auto-login] error inesperado: {e}")
            return False

        # Doble verificación: si por algún motivo seguimos en /ingreso, falló.
        time.sleep(1.0)
        if "/ingreso" in self.page.url:
            print(f"  [auto-login] aún en /ingreso tras submit — URL: {self.page.url}")
            return False

        try:
            self.save_session()
            print(f"  [auto-login] ✓ sesión renovada y guardada en {self.settings.session_path}")
            return True
        except Exception as e:
            print(f"  [auto-login] login OK pero save_session falló: {e}")
            # La sesión activa funciona en memoria; el próximo cron tendrá que re-loguear.
            return True

    # ── operaciones de alto nivel ───────────────────────────────────

    def list_orders(self) -> list[ScrapedOrder]:
        """Lee toda la tabla /app/orden_v en una sola pasada (sin paginar — el ERP no pagina)."""
        self.page.goto(self.settings.orden_v_url, wait_until="domcontentloaded")
        self.page.wait_for_selector("table tbody tr", timeout=self.settings.navigation_timeout_ms)

        raw = self.page.evaluate(
            """
            () => Array.from(document.querySelectorAll('table tbody tr')).map(tr => {
                const cells = tr.querySelectorAll('td');
                if (cells.length < 5) return null;
                return {
                    orden_id_raw: (cells[3]?.innerText || '').trim(),
                    cliente_raw:  (cells[4]?.innerText || '').trim(),
                    estado:       (cells[cells.length - 1]?.innerText || '').trim(),
                };
            }).filter(Boolean)
            """
        )

        result: list[ScrapedOrder] = []
        for row in raw:
            orden_id_text = re.sub(r"\D", "", row.get("orden_id_raw", ""))
            if not orden_id_text:
                continue
            cliente = row.get("cliente_raw", "")
            estado = row.get("estado", "")
            result.append(
                ScrapedOrder(
                    orden_id=int(orden_id_text),
                    cliente=cliente,
                    direccion=_extract_direccion(cliente),
                    telefono=_extract_phone(cliente),
                    estado=estado,
                    needs_processing=needs_processing(estado),
                )
            )
        return result

    def get_order_detail(self, orden_id: int) -> OrderDetail:
        """Abre el modal de remisión SOLO para leer productos. Cierra sin guardar."""
        self._open_remision_modal_for_order(orden_id)
        modal = self.page.locator("#modalCrear")

        # Esperar hasta 10s a que el modal esté visible (no solo en DOM).
        try:
            modal.wait_for(state="visible", timeout=10000)
        except PlaywrightTimeoutError:
            print(f"  [warn] modal #modalCrear nunca se hizo visible para orden {orden_id}")

        # Pequeña espera extra para AJAX que llena los conceptos.
        time.sleep(1.5)

        productos_raw = modal.evaluate(
            """
            modal => {
                // Effi puede usar textarea o input para la descripción según la versión.
                let descs = Array.from(modal.querySelectorAll(
                    'textarea[name="descripcion[]"], input[name="descripcion[]"]'
                )).map(d => (d.value || '').trim());

                // Fallback si Effi cambia a select-based.
                if (descs.every(d => !d)) {
                    descs = Array.from(modal.querySelectorAll('select[name="articulo[]"]'))
                                .map(s => {
                                    const opt = s.options[s.selectedIndex];
                                    return opt ? (opt.text || '').trim() : '';
                                });
                }

                const cants = Array.from(modal.querySelectorAll('input[name="cantidad[]"]'))
                                .map(c => parseInt(c.value, 10) || 0);

                // SOLO filas con descripción real — Effi pre-renderiza una fila vacía
                // (placeholder "agregar producto") que hay que ignorar.
                const max = Math.max(descs.length, cants.length);
                const result = [];
                for (let i = 0; i < max; i++) {
                    const d = descs[i] || '';
                    const c = cants[i] || 0;
                    if (d && c > 0) {
                        result.push({ descripcion: d, cantidad: c });
                    }
                }
                return result;
            }
            """
        )

        # Si quedó vacío después de filtrar, hay un problema real — dumpear.
        if not productos_raw:
            print(f"  [warn] no se encontraron productos en el modal de orden {orden_id}")
            self._dump_modal_html(modal, f"order_{orden_id}_empty_products")
            self._dump_modal_screenshot(orden_id)

        cliente = ""
        cli_sel = modal.locator('select[name="cliente"]')
        if cli_sel.count() > 0:
            cliente = cli_sel.first.evaluate(
                "el => (el.options[el.selectedIndex]?.text || '').trim()"
            )

        direccion = ""
        dir_sel = modal.locator('select[name="direccion_destinatario[]"]')
        if dir_sel.count() > 0:
            direccion = dir_sel.first.evaluate(
                "el => (el.options[el.selectedIndex]?.text || '').trim()"
            )

        self._dismiss_modal(modal)

        return OrderDetail(
            orden_id=orden_id,
            cliente=cliente,
            direccion=direccion,
            productos=[
                OrderProduct(descripcion=p["descripcion"], cantidad=int(p["cantidad"]))
                for p in productos_raw
                if p.get("descripcion")
            ],
        )

    def convert_to_remision(self, orden_id: int) -> int:
        """Abre el modal de remisión y lo SUBMITE. Devuelve el ID de la remisión creada.

        Estrategia:
          1. Snapshot pre-submit de IDs en /app/remision_v.
          2. Abrir modal vía dropdown action.
          3. Click "Crear y cerrar" y verificar que el submit FUE aceptado
             (modal se cierra y/o no aparece mensaje de error).
          4. Snapshot post-submit y diff para encontrar el nuevo ID.
        """
        # 0) Idempotencia: si la orden YA tiene una remisión (caso típico tras un
        #    rerun después de un fallo parcial), reusamos esa remisión en vez de
        #    crear duplicado.
        existing = self.find_remision_for_order(orden_id)
        if existing is not None:
            print(f"  [info] orden {orden_id} ya tiene remisión {existing} — reusando")
            return existing

        # 1) Snapshot pre-submit.
        pre_existing = self._snapshot_table_ids(self.settings.remision_v_url)

        # 2) Abrir modal y submitear.
        self._open_remision_modal_for_order(orden_id)
        modal = self.page.locator("#modalCrear")
        # Effi popula País/Depto/Ciudad/Dirección con cascading AJAX selects (jQuery).
        # Sin esta espera, el submit llega con campos vacíos → error de validación
        # intermitente ("El campo País del cliente, es obligatorio.", etc.).
        self._wait_modal_ajax_settled(modal)
        self._click_submit_button(modal, "Crear y cerrar")

        # 3) Verificar que el submit REALMENTE tomó efecto.
        self._post_submit_wait(modal, orden_id, "convert_to_remision")

        return self._read_new_id(self.settings.remision_v_url, pre_existing, "remision")

    def _wait_modal_ajax_settled(self, modal, timeout_ms: int = 8000) -> None:
        """Espera a que el AJAX cascading del modal de remisión termine.

        Effi popula País/Depto/Ciudad/Dirección del cliente con cascading selects
        (jQuery select2 + trigger('change')) después de que el modal ya es visible.
        Si clickeamos "Crear y cerrar" antes de que termine la cascada, el form
        submite con esos campos vacíos y el ERP devuelve errores de validación
        intermitentes (caso confirmado: órdenes 5395, 5387, 5412 en 2026-05-13/14).

        Considera settled cuando: jQuery.active === 0 Y el select de dirección_destinatario
        tiene un value no vacío. Timeout safe: si no settled, deja submitear igual
        — _post_submit_wait detecta el fallo y reporta el error real.
        """
        deadline = time.time() + (timeout_ms / 1000.0)
        last_state = {"jq": None, "dir": None}
        while time.time() < deadline:
            try:
                state = self.page.evaluate(
                    """() => {
                        const jq = window.jQuery;
                        const jqActive = jq ? jq.active : 0;
                        const dirSel = document.querySelector(
                            '#modalCrear select[name="direccion_destinatario[]"]'
                        );
                        const dirVal = dirSel ? (dirSel.value || '') : '';
                        return { jqActive, dirVal };
                    }"""
                )
                last_state["jq"] = state.get("jqActive")
                last_state["dir"] = state.get("dirVal")
                if state.get("jqActive") == 0 and state.get("dirVal"):
                    return
            except Exception:
                pass
            time.sleep(0.25)
        print(
            f"  [warn] modal AJAX no settled tras {timeout_ms}ms "
            f"(jQuery.active={last_state['jq']}, direccion={last_state['dir']!r}); "
            "submitting anyway"
        )

    def _post_submit_wait(self, modal, context_id: int, label: str) -> None:
        """Espera best-effort tras click "Crear y cerrar".

        Si el modal se cierra rápido, retorna inmediatamente.
        Si no se cierra en 5s, busca errores de validación visibles:
          - Si HAY errores → raise EffiBotError con el mensaje real (fail-fast).
          - Si NO hay errores → dumpea y retorna; _read_new_id es el juez final
            (Effi a veces succeeds dejando el modal abierto — caso confirmado
            en producción 2026-05-13: orden 5378 → guía creada pero modal lingering).
        """
        time.sleep(1.5)
        try:
            modal.wait_for(state="hidden", timeout=5000)
            return  # modal se cerró rápido → confianza alta de éxito
        except PlaywrightTimeoutError:
            pass

        # Modal lingering — recolectar errores visibles.
        try:
            diagnostic = modal.evaluate(
                """
                m => {
                    const errors = [];
                    for (const sel of ['.alert-danger', '.alert-error', '.text-danger',
                                       '.error', '.invalid-feedback', '[role="alert"]', '.is-invalid']) {
                        m.querySelectorAll(sel).forEach(el => {
                            const t = (el.innerText || '').trim();
                            if (t && t.length < 500) errors.push(t);
                        });
                    }
                    return { errors: errors.slice(0, 3) };
                }
                """
            )
            errors = diagnostic.get("errors") or []
        except Exception:
            errors = []

        # Errores visibles = señal clara de falla. Fail-fast con info útil.
        if errors:
            try:
                self._dump_modal_html(modal, f"{label}_validation_error_{context_id}")
            except Exception:
                pass
            raise EffiBotError(
                f"{label} falló con errores de validación visibles en el modal: "
                + " | ".join(errors[:3])
            )

        # Sin errores visibles pero modal lingering: posible éxito silencioso.
        # Dejamos que _read_new_id decida verificando la tabla destino.
        print(
            f"  [info] {label}: modal lingering sin errores visibles — "
            "validando éxito via tabla destino..."
        )
        try:
            self._dump_modal_html(modal, f"{label}_modal_lingered_{context_id}")
        except Exception:
            pass

    # IDs de Effi están en los miles. Cualquier número > 10M es ruido (típicamente
    # fechas que el regex `\D` consolida en 14 dígitos como 20260513115123).
    _MAX_REASONABLE_ID = 10_000_000

    def _read_new_id(self, table_url: str, pre_existing: set[int], label: str) -> int:
        """Navega a la URL limpia y devuelve el ID nuevo que NO estaba en pre_existing.

        Con 3 reintentos y waits crecientes — Effi a veces tarda en refrescar la
        tabla y devuelve fechas en col 4 si se lee demasiado rápido.
        """
        pre_clean = {i for i in pre_existing if i < self._MAX_REASONABLE_ID}

        last_current: set[int] = set()
        for attempt in range(3):
            if attempt > 0:
                time.sleep(2.0)
            try:
                self.page.goto(table_url, wait_until="networkidle", timeout=self.settings.navigation_timeout_ms)
            except PlaywrightTimeoutError:
                # networkidle puede tardar en sitios con polling; seguimos.
                pass
            except PlaywrightError as e:
                # net::ERR_ABORTED: el submit anterior aún tiene una navegación
                # en vuelo que cancela nuestro goto. Esperamos a que se quiete
                # y reintentamos en el próximo iter del loop.
                msg = str(e)
                if "ERR_ABORTED" in msg or "net::" in msg:
                    print(f"  [warn] {label} goto abortado (intento {attempt + 1}/3): {msg.splitlines()[0]}")
                    try:
                        self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass
                    time.sleep(1.0)
                    continue
                raise
            self.page.wait_for_selector("table tbody tr", timeout=self.settings.navigation_timeout_ms)
            time.sleep(1.0 + 0.5 * attempt)

            current_ids = self._snapshot_table_ids(None)
            current_clean = {i for i in current_ids if i < self._MAX_REASONABLE_ID}
            last_current = current_clean

            new_ids = [i for i in current_clean if i not in pre_clean]
            if new_ids:
                new_id = max(new_ids)
                print(
                    f"  [info] {label}_id detectado: {new_id} "
                    f"(intento {attempt + 1}, pre={len(pre_clean)}, post={len(current_clean)})"
                )
                return new_id
            print(
                f"  [warn] intento {attempt + 1}/3: no aparece {label} nuevo "
                f"(pre={len(pre_clean)}, post={len(current_clean)})"
            )

        # Tras 3 intentos no detectamos un ID válido nuevo. Dumpeamos y abortamos.
        # NO usamos _first_row_id como fallback porque producía garbage (timestamps).
        self._dump_modal_html(self.page.locator("body"), f"no_new_{label}_id")

        # Capturar contexto adicional para diagnóstico (URL/title delatan session expired).
        try:
            final_url = self.page.url
        except Exception:
            final_url = "?"
        try:
            page_title = self.page.title()
        except Exception:
            page_title = "?"
        session_hint = " — sesión Effi parece expirada (redirect a login)" if "/ingreso" in final_url else ""

        raise EffiBotError(
            f"No pude detectar el {label} recién creado tras 3 intentos. "
            f"Pre-existing={len(pre_clean)}, último current={len(last_current)}. "
            f"URL final: {final_url}, title: {page_title!r}.{session_hint} "
            "Posibles causas: diálogo del navegador interceptado sin handler, "
            "validación server-side sin error visible, tabla con caché, o sesión expirada."
        )

    def _snapshot_table_ids(self, table_url: str | None) -> set[int]:
        """Si table_url se da, navega ahí. Devuelve set de IDs (col 4) en rango razonable.

        Filtra los valores > 10M (sospecha de timestamp tipo YYYYMMDDHHMMSS) y los <= 0.
        """
        if table_url is not None:
            try:
                self.page.goto(table_url, wait_until="networkidle", timeout=self.settings.navigation_timeout_ms)
            except PlaywrightTimeoutError:
                pass
            self.page.wait_for_selector("table tbody tr", timeout=self.settings.navigation_timeout_ms)
            time.sleep(1.0)
        ids = self.page.evaluate(
            """
            () => Array.from(document.querySelectorAll('table tbody tr td:nth-child(4)'))
                       .map(td => (td.innerText || '').trim().replace(/\\D/g, ''))
                       .filter(Boolean)
                       .map(s => parseInt(s, 10))
                       .filter(n => !isNaN(n) && n > 0)
            """
        )
        return {i for i in ids if i < self._MAX_REASONABLE_ID}

    def _find_id_in_table(
        self,
        table_url: str,
        search_id: int,
        id_col_index: int = 3,
    ) -> int | None:
        """Busca en una tabla de Effi una fila que referencia `search_id` y devuelve
        el ID propio de esa fila (col `id_col_index + 1`, default col 4).

        Estrategia: navega a la URL, escanea cada fila buscando `search_id` como
        token exacto en CUALQUIER celda EXCEPTO la columna de ID propia. Sirve para:
          - Encontrar remision que referencia orden_id (caso recovery post-fail).
          - Encontrar guia que referencia remision_id (caso recovery post-fail).

        Devuelve None si no encuentra match — la columna de referencia puede
        variar y no queremos asumir su índice.
        """
        try:
            self.page.goto(table_url, wait_until="networkidle", timeout=self.settings.navigation_timeout_ms)
        except PlaywrightTimeoutError:
            pass
        except PlaywrightError as e:
            if "ERR_ABORTED" in str(e) or "net::" in str(e):
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass
                time.sleep(1.0)
                try:
                    self.page.goto(table_url, wait_until="domcontentloaded", timeout=self.settings.navigation_timeout_ms)
                except Exception:
                    return None
            else:
                raise
        try:
            self.page.wait_for_selector("table tbody tr", timeout=self.settings.navigation_timeout_ms)
        except PlaywrightTimeoutError:
            return None
        time.sleep(1.0)

        found = self.page.evaluate(
            """
            ({ searchId, idCol }) => {
                const re = new RegExp('(^|\\\\D)' + searchId + '(\\\\D|$)');
                const rows = Array.from(document.querySelectorAll('table tbody tr'));
                for (const row of rows) {
                    const cells = Array.from(row.querySelectorAll('td'));
                    let hit = false;
                    for (let i = 0; i < cells.length; i++) {
                        if (i === idCol) continue;
                        const txt = (cells[i].innerText || '').trim();
                        if (txt && re.test(txt)) { hit = true; break; }
                    }
                    if (hit && cells[idCol]) {
                        const idTxt = (cells[idCol].innerText || '').replace(/\\D/g, '');
                        const id = parseInt(idTxt, 10);
                        if (!isNaN(id) && id > 0 && id < 10000000) return id;
                    }
                }
                return null;
            }
            """,
            {"searchId": str(search_id), "idCol": id_col_index},
        )
        return int(found) if found else None

    def find_remision_for_order(self, orden_id: int) -> int | None:
        """Devuelve el remision_id que referencia a orden_id, o None si no existe."""
        return self._find_id_in_table(self.settings.remision_v_url, orden_id)

    def find_guia_for_remision(self, remision_id: int) -> int | None:
        """Devuelve el guia_id que referencia a remision_id, o None si no existe."""
        return self._find_id_in_table(self.settings.guia_transporte_url, remision_id)

    def create_guia(
        self,
        remision_id: int,
        plan: ProcessingPlan,
        fecha_envio: str,
        fecha_entrega: str,
    ) -> int:
        """Abre el modal de guía sobre la remisión indicada, llena los campos y submite.

        Snapshot ANTES de empezar el flujo de creación para detectar el ID nuevo.
        """
        # 0) Idempotencia: si la remisión YA tiene una guía (rerun tras fallo
        #    parcial — típicamente ERR_ABORTED al leer el ID post-submit), reusamos.
        existing = self.find_guia_for_remision(remision_id)
        if existing is not None:
            print(f"  [info] remisión {remision_id} ya tiene guía {existing} — reusando")
            return existing

        # 1) Snapshot pre-submit de guías existentes.
        pre_existing = self._snapshot_table_ids(self.settings.guia_transporte_url)

        # 2) Abrir el modal de guía via dropdown action en /app/remision_v.
        self.page.goto(self.settings.remision_v_url, wait_until="domcontentloaded")
        self.page.wait_for_selector("table tbody tr", timeout=self.settings.navigation_timeout_ms)
        self._click_dropdown_action(remision_id, "Crear guía de transporte")

        modal = self.page.locator("#modalCrear")
        modal.wait_for(state="visible", timeout=self.settings.navigation_timeout_ms)

        # 3) Llenar campos.
        self._fill_jquery(modal.locator("#fecha_envio_CR"), fecha_envio)
        self._fill_jquery(modal.locator("#fecha_entrega_esperada_CR"), fecha_entrega)
        self._select_jquery(modal.locator("#transportadora_CR"), "1")

        # AJAX cascading + bug conocido: el ERP pisa fecha_entrega tras el change
        # de transportadora; re-aplicamos.
        time.sleep(2.5)
        self._fill_jquery(modal.locator("#fecha_entrega_esperada_CR"), fecha_entrega)

        if plan.contenido_modo == "copiar_documento":
            check = modal.locator("#contenido_check_CR")
            if check.count() > 0:
                check.check()
        else:
            self._fill_jquery(modal.locator("#contenido_CR"), plan.contenido_texto or "")

        self._fill_jquery(
            modal.locator("#valor_declarado_CR"),
            f"{plan.valor_declarado:.2f}",
        )

        # 4) Submit, verificar éxito, y leer ID nuevo.
        self._click_submit_button(modal, "Crear y cerrar")
        self._post_submit_wait(modal, remision_id, "create_guia")

        # Path feliz: leer ID nuevo via diff. Si falla (ERR_ABORTED, networkidle
        # timeout persistente, etc.), intentamos fallback explícito buscando guía
        # que referencie esta remisión — la guía PUEDE haberse creado.
        try:
            return self._read_new_id(self.settings.guia_transporte_url, pre_existing, "guia")
        except EffiBotError as primary_err:
            print(
                f"  [warn] _read_new_id falló: {primary_err}. "
                f"Intentando fallback find_guia_for_remision({remision_id})..."
            )
            recovered = self.find_guia_for_remision(remision_id)
            if recovered is not None:
                print(f"  [info] recovered guia_id={recovered} via fallback")
                return recovered
            raise

    def read_guia_row_data(self, guia_id: int) -> dict | None:
        """Lee tracking number CARGO EXPRESO y valor a recaudar del row del
        guia_id en /app/guia_transporte_v.

        Returns dict con:
          - "tracking": str | None  — formato 'B<digits>-<digits>'
          - "valor_recaudar": float | None  — extraído de 'Recaudo: $NNN'

        Devuelve None si no se encuentra el row. Los campos individuales pueden
        ser None si el patrón específico no se encuentra en el row.
        """
        try:
            self.page.goto(
                self.settings.guia_transporte_url,
                wait_until="networkidle",
                timeout=self.settings.navigation_timeout_ms,
            )
        except PlaywrightTimeoutError:
            pass
        try:
            self.page.wait_for_selector("table tbody tr", timeout=self.settings.navigation_timeout_ms)
        except PlaywrightTimeoutError:
            return None
        time.sleep(1.0)

        try:
            row_text = self.page.evaluate(
                """
                (guiaIdStr) => {
                    const target = String(guiaIdStr);
                    const rows = document.querySelectorAll('table tbody tr');
                    for (const row of rows) {
                        const cells = Array.from(row.querySelectorAll('td'));
                        if (cells.length < 4) continue;
                        const idText = (cells[3].innerText || '').trim().replace(/\\D/g, '');
                        if (idText !== target) continue;
                        return cells.map(c => (c.innerText || '').trim()).join(' | ');
                    }
                    return null;
                }
                """,
                guia_id,
            )
        except Exception:
            return None
        if not row_text:
            return None

        # Tracking: B + 6+ digits + '-' + digits
        tracking_match = _RE_CARGO_TRACKING.search(row_text)
        tracking = tracking_match.group(0) if tracking_match else None

        # Valor a recaudar: 'Recaudo: $NNN' (con o sin decimales, con o sin $).
        valor_match = re.search(
            r"recaudo\s*:\s*\$?\s*([\d,]+(?:\.\d{1,2})?)",
            row_text,
            re.IGNORECASE,
        )
        valor_recaudar = None
        if valor_match:
            try:
                valor_recaudar = float(valor_match.group(1).replace(",", ""))
            except ValueError:
                valor_recaudar = None

        return {"tracking": tracking, "valor_recaudar": valor_recaudar}

    # Alias retrocompatible — algunos callers viejos esperan solo el tracking.
    def read_guia_tracking_number(self, guia_id: int) -> str | None:
        data = self.read_guia_row_data(guia_id)
        return data.get("tracking") if data else None

    # ── helpers internos ────────────────────────────────────────────

    def _open_remision_modal_for_order(self, orden_id: int) -> None:
        self.page.goto(self.settings.orden_v_url, wait_until="domcontentloaded")
        self.page.wait_for_selector("table tbody tr", timeout=self.settings.navigation_timeout_ms)
        self._click_dropdown_action(orden_id, "Convertir en remisión")
        modal = self.page.locator("#modalCrear")
        modal.wait_for(state="visible", timeout=self.settings.navigation_timeout_ms)

    def _click_dropdown_action(self, row_id: int, action_text: str) -> None:
        """Encuentra la fila por ID en col 4 y navega al href de la acción del dropdown.

        En lugar de hacer click en el menú del dropdown (que es frágil — el menú se
        cierra solo, el elemento queda 'no visible' aunque exista en DOM), leemos
        directamente el href del <a> y navegamos a él. Per handoff §5.1/5.2, el href
        contiene el blob encriptado action=... que abre el modal automáticamente.
        """
        row = self.page.locator(
            f"xpath=//table//tbody/tr[td[4][normalize-space(text())='{row_id}']]"
        )
        if row.count() == 0:
            raise EffiBotError(f"No se encontró fila para ID {row_id}")

        link = row.locator(f"a:has-text(\"{action_text}\")").first
        if link.count() == 0:
            # Fallback: el link puede estar fuera del <tr> (en un menú flotante).
            link = self.page.locator(f"a:has-text(\"{action_text}\")").first

        href = link.get_attribute("href")
        if not href:
            raise EffiBotError(
                f"No se pudo leer href del link '{action_text}' en fila {row_id}"
            )
        self.page.goto(href, wait_until="domcontentloaded")

    def _click_submit_button(self, container, button_text: str) -> None:
        """Click en botón de submit por texto.

        IMPORTANTE: NO usar form.submit() — el ERP tiene <input name=action> que
        shadow-ea form.action y redirige a /app/calendario. SIEMPRE click manual.
        """
        btn = container.locator(f"button:has-text(\"{button_text}\")").first
        btn.click()

    def _dismiss_modal(self, modal) -> None:
        """Cierra un modal sin guardar (cancelar, X, o tecla Escape)."""
        for selector in (
            "button:has-text(\"Cancelar\")",
            ".modal-header button[aria-label=\"Close\"]",
            "button.close",
        ):
            loc = modal.locator(selector)
            if loc.count() > 0:
                try:
                    loc.first.click()
                    return
                except Exception:
                    continue
        self.page.keyboard.press("Escape")

    def _fill_jquery(self, locator, value: str) -> None:
        """Setea value y dispara change() de jQuery (necesario para los AJAX cascading)."""
        locator.evaluate(
            "(el, value) => { el.value = value; if (window.jQuery) window.jQuery(el).trigger('change'); }",
            value,
        )

    def _select_jquery(self, locator, value: str) -> None:
        """Setea el option seleccionado y dispara change() (selects con select2)."""
        locator.evaluate(
            "(el, value) => { el.value = value; if (window.jQuery) window.jQuery(el).trigger('change'); }",
            value,
        )

    def _first_row_id(self) -> int:
        """Lee el ID de la primera fila (col 4) — la más reciente tras un submit."""
        cell = self.page.locator("table tbody tr td:nth-child(4)").first
        text = cell.inner_text()
        return int(re.sub(r"\D", "", text))

    def _debug_dir(self):
        """Crea (si no existe) y devuelve el directorio de debug."""
        debug_dir = self.settings.db_path.parent / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        return debug_dir

    def _dump_modal_html(self, modal, tag: str) -> None:
        """Guarda outerHTML del modal y del body completo (por si el modal está vacío)."""
        from datetime import datetime as _dt
        ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = None
        try:
            debug_dir = self._debug_dir()
        except Exception as e:
            print(f"  [debug] FALLO creando {self.settings.db_path.parent / 'debug'}: {e}")
            return
        print(f"  [debug] dir destino: {debug_dir.resolve()}")

        # 1) Modal HTML (puede venir vacío si el selector no matcheó).
        try:
            modal_html = modal.evaluate("el => el ? el.outerHTML : '<<modal locator did not resolve>>'")
            path = debug_dir / f"{tag}_modal_{ts}.html"
            path.write_text(modal_html or "<<empty>>", encoding="utf-8")
            print(f"  [debug] modal HTML       → {path.name} ({len(modal_html or '')} chars)")
        except Exception as e:
            print(f"  [debug] no pude dumpear modal HTML: {e}")

        # 2) Body completo — útil si el modal aún no existía en el DOM.
        try:
            body_html = self.page.evaluate("() => document.body.outerHTML")
            path = debug_dir / f"{tag}_body_{ts}.html"
            path.write_text(body_html, encoding="utf-8")
            print(f"  [debug] body HTML        → {path.name} ({len(body_html)} chars)")
        except Exception as e:
            print(f"  [debug] no pude dumpear body: {e}")

        # 3) URL actual — para confirmar que estamos donde creemos.
        try:
            print(f"  [debug] page URL: {self.page.url}")
        except Exception:
            pass

    def _dump_modal_screenshot(self, orden_id: int) -> None:
        """Guarda un screenshot full-page para ver qué pasaba visualmente."""
        try:
            from datetime import datetime as _dt
            ts = _dt.now().strftime("%Y%m%d_%H%M%S")
            debug_dir = self._debug_dir()
            path = debug_dir / f"order_{orden_id}_screenshot_{ts}.png"
            self.page.screenshot(path=str(path), full_page=True)
            print(f"  [debug] screenshot       → {path.name}")
        except Exception as e:
            print(f"  [debug] no pude tomar screenshot: {e}")
