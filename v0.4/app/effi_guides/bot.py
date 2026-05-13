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
        # 1) Snapshot pre-submit.
        pre_existing = self._snapshot_table_ids(self.settings.remision_v_url)

        # 2) Abrir modal y submitear.
        self._open_remision_modal_for_order(orden_id)
        modal = self.page.locator("#modalCrear")
        self._click_submit_button(modal, "Crear y cerrar")

        # 3) Verificar que el submit REALMENTE tomó efecto.
        self._post_submit_wait(modal, orden_id, "convert_to_remision")

        return self._read_new_id(self.settings.remision_v_url, pre_existing, "remision")

    def _post_submit_wait(self, modal, context_id: int, label: str) -> None:
        """Espera best-effort tras click "Crear y cerrar".

        Si el modal se cierra rápido, retorna inmediatamente.
        Si no se cierra en 5s, registra warning + dumpea (para diagnóstico)
        pero NO falla — el juez REAL de éxito es _read_new_id, que verifica
        en la tabla destino si apareció un ID nuevo. Effi a veces deja el modal
        visible aunque la operación interna haya succeded (caso confirmado en
        producción 2026-05-13: orden 5378 → guía creada pero modal lingering).
        """
        time.sleep(1.5)
        try:
            modal.wait_for(state="hidden", timeout=5000)
            return  # modal se cerró rápido → confianza alta de éxito
        except PlaywrightTimeoutError:
            pass

        # Modal lingering — diagnóstico sin abortar.
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

        print(
            f"  [info] {label}: modal lingering tras submit "
            f"(errores visibles: {errors or 'ninguno'}) — "
            "validando éxito via tabla destino..."
        )
        # Dump opcional para análisis futuro, sin abortar.
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
        raise EffiBotError(
            f"No pude detectar el {label} recién creado tras 3 intentos. "
            f"Pre-existing={len(pre_clean)}, último current={len(last_current)}. "
            "Posiblemente la submit falló o la tabla no refrescó."
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

        return self._read_new_id(self.settings.guia_transporte_url, pre_existing, "guia")

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
