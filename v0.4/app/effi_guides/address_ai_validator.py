"""Validador de direcciones por IA — capa de segunda opinión sobre el regex.

Se usa SOLO cuando el regex devuelve REVIEW o INVALID. Si la IA tiene confianza
en que la dirección es válida (ej. detecta un centro comercial conocido con
typo, o un landmark + referencia clara sin ubicación nominal), upgradea a VALID.

Si la IA tampoco está confidente, mantiene REVIEW o INVALID — la operadora
ve AMBAS razones (regex + IA) en la cola humana.

Default: MiniMax (OpenAI-compatible). Si MINIMAX_API_KEY no está configurada,
el validador NO se instancia y el runner cae al regex puro.
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass

from .address_validator import AddressResult, AddressValidation


# ── Esqueleto del prompt (lógica estable — NO se edita desde la UI) ──────
# Las instrucciones base: categorías, formato Effi, reglas. Si esto se rompe,
# el validador entero falla — por eso vive en código, versionado.
_PROMPT_HEAD = (
    "Eres un mensajero experimentado de CARGO EXPRESO en Guatemala. "
    "Tu trabajo es decidir si una dirección permite llegar al destino para entregar un paquete.\n\n"
    "Categorías:\n"
    "- 'valid'   : la dirección permite entregar. Incluye: estructura urbana con calle/avenida/zona, "
    "aldea/colonia/barrio con landmark, retiro en agencia CARGO EXPRESO, centros comerciales "
    "identificables (aunque tengan typos como 'sentro' por 'centro'), edificios/mercados específicos, "
    "o cualquier combinación de landmarks clara aunque falte la 'ubicación nominal' (basta con que un "
    "mensajero sepa adónde llegar).\n"
    "- 'review'  : la dirección PUEDE servir pero tiene ambigüedad real (ej. landmark sin colonia "
    "y zona/municipio amplia, lugar repetido en varias ubicaciones del país).\n"
    "- 'invalid' : la dirección NO permite entregar. Vacía, trivial ('en mi casa', 'casa'), "
    "solo nombre de departamento sin más, o solo un landmark genérico sin ubicación.\n\n"
    "FORMATO Effi: las direcciones llegan a veces con prefijo estructural "
    "'Depto / Municipio / Localidad (Zona N) / texto libre'. El prefijo viene de dropdowns "
    "del ERP — NO cuenta como dirección del cliente. Lo que importa es si el TEXTO LIBRE "
    "(después del último ' / ') es suficiente para entregar. Si la 'Zona N' del prefijo es lo único "
    "que satisface la estructura urbana, la dirección es INSUFICIENTE.\n\n"
    "REGLA CLAVE — landmarks genéricos sin nombre propio NO son suficientes: 'ferretería', "
    "'iglesia', 'tienda', 'mercado', 'farmacia', 'comedor' sin nombre específico ('Ferretería La "
    "Económica', 'Iglesia San Pedro') o sin relación espacial precisa ('a la par del rótulo rojo') "
    "deben marcarse INVALID o REVIEW. Una calle/avenida con solo el número de vía (ej. '6 avenida') "
    "necesita ADEMÁS un número de inmueble (formato 'X-Y' como '12-51' o '0-54') o un landmark "
    "específico para ser entregable.\n\n"
    "Considera typos comunes en español guatemalteco (sentro=centro, kalle=calle, sona=zona, "
    "banrrural=Banrural, krk=cerca, kasa=casa, kuadras=cuadras, etc.). Acepta abreviaturas "
    "locales (z=zona, av=avenida).\n\n"
    "EJEMPLOS DE REFERENCIA — calibrá tu juicio contra estos casos del negocio:"
)

_PROMPT_TAIL = (
    "Responde ÚNICAMENTE con un JSON en una sola línea, sin texto adicional:\n"
    '{"status": "valid|review|invalid", "reason": "razón breve en español, máximo 15 palabras"}'
)

# Ejemplos few-shot por defecto — fallback si la tabla effi_address_examples
# está vacía o no se puede leer. La fuente normal de ejemplos es la DB
# (tabla effi_address_examples, editable en /effi/address-examples).
_DEFAULT_EXAMPLES: list[tuple[str, str, str]] = [
    ("5 calle 12-51 zona uno de mixco", "valid", "Estructura urbana cardinal completa"),
    ("Aldea El Florido frente a la iglesia católica, Escuintla", "valid", "Aldea identificable con landmark claro"),
    ("Cargo expreso Morales (retiro en agencia)", "valid", "Retiro en agencia CARGO EXPRESO"),
    ("9 Calle 0-54 zona 3 colonia las victorias enfrente a la vieja bodega de tecnoprosa", "valid", "Dirección urbana cardinal con landmark"),
    ("sentro comercial santa clara En el sentro comercial santa clara", "valid", "Centro comercial Santa Clara identificable pese al typo"),
    ("Frente a banco banrrural Pegado de la farmacia manuelita", "valid", "Dos landmarks comerciales en el mismo punto"),
    ("Frente de la escuela urbana Salida a antigua tutuapa", "review", "Landmark y referencia pero municipio/colonia imprecisos"),
    ("Saliendo de antigua para chimaltenango, despues de la 2da curva, casa del señor Pedro color celeste", "valid", "Ruta clara entre 2 ciudades con casa específica identificable"),
    ("Colonia la promesa La democracia", "review", "Colonia genérica sin landmark ni estructura cardinal"),
    ("Retalhuleu Caballo blanco", "invalid", "Solo nombres de lugar sin referencia ni dirección"),
    ("en mi casa", "invalid", "Trivial sin ubicación concreta"),
    ("Por ahi por las afueras Pregunten por mi", "invalid", "Demasiado vago, sin referencia concreta"),
    ("Guatemala / Guatemala / Guatemala (Zona 4) / 6 avenida Ferretería", "invalid", 'Texto libre es solo "6 avenida Ferretería" — sin número de inmueble ni ferretería con nombre'),
    ("Guatemala / Mixco / Zona 1 / 5 calle 12-51 frente a la iglesia", "valid", "Texto libre completo: calle + número de inmueble + landmark"),
    ("Calle principal tienda", "invalid", "Calle genérica, landmark sin nombre"),
    ("5 avenida frente a la iglesia", "review", "Avenida sin número ni zona; iglesia genérica sin nombre"),
    ("zona 1 cerca del mercado", "review", "Zona muy amplia, mercado genérico — qué mercado?"),
]


def build_system_prompt(examples: list[tuple[str, str, str]] | None = None) -> str:
    """Compone el system prompt: esqueleto + ejemplos few-shot + cierre.

    `examples` es una lista de tuplas (address, veredicto, reason). Si es None
    o vacía, usa los ejemplos default hardcodeados — el validador nunca queda
    sin ejemplos.
    """
    if not examples:
        examples = _DEFAULT_EXAMPLES
    lines = [_PROMPT_HEAD, ""]
    for address, veredicto, reason in examples:
        # Escapar comillas dobles del reason para que el JSON de ejemplo sea válido.
        safe_reason = (reason or "").replace('"', '\\"')
        lines.append(f'Dirección: "{address}"')
        lines.append(f'Veredicto: {{"status": "{veredicto}", "reason": "{safe_reason}"}}')
        lines.append("")
    lines.append(_PROMPT_TAIL)
    return "\n".join(lines)


# Prompt por defecto (con ejemplos hardcodeados) — alias de compatibilidad
# para código/scripts que importaban SYSTEM_PROMPT.
SYSTEM_PROMPT = build_system_prompt()


@dataclass(frozen=True)
class AIValidationResult:
    """Veredicto de la IA sobre una dirección."""
    status: AddressValidation
    reason: str
    raw_response: str
    model: str

    def merge_into(self, regex_result: AddressResult) -> AddressResult:
        """Devuelve un AddressResult con el veredicto IA, preservando patterns del regex."""
        return AddressResult(
            status=self.status,
            matched_patterns=regex_result.matched_patterns,
            reasons=tuple(list(regex_result.reasons) + [f"[IA] {self.reason}"]),
            normalized=regex_result.normalized,
        )


class MiniMaxAddressValidator:
    """Validador IA via MiniMax (endpoint compatible OpenAI chat completion).

    Cache in-memory por dirección normalizada para evitar llamar dos veces con
    la misma entrada dentro de una corrida. NO persiste entre runs.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "MiniMax-M2.7",
        base_url: str = "https://api.minimax.io/v1",
        timeout_seconds: int = 15,
        system_prompt: str | None = None,
    ):
        if not api_key:
            raise ValueError("MiniMaxAddressValidator requires api_key")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        # system_prompt se arma desde los ejemplos de la DB; si no se pasa,
        # usa el default con ejemplos hardcodeados.
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        self._cache: dict[str, AIValidationResult] = {}

    def evaluate(self, address: str) -> AIValidationResult | None:
        """Llama a MiniMax. Devuelve None si la llamada falla (caller debe fallback)."""
        if not address or not address.strip():
            return None

        key = _normalize_for_cache(address)
        if key in self._cache:
            return self._cache[key]

        try:
            content = self._call_api(address)
        except Exception:
            return None

        result = self._parse_response(content)
        if result is None:
            return None
        self._cache[key] = result
        return result

    # ── internals ────────────────────────────────────────────────────

    def _call_api(self, address: str) -> str:
        endpoint = f"{self.base_url}/chat/completions"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f'Evalúa esta dirección guatemalteca:\n"{address}"'},
            ],
            "temperature": 0.1,
            # M2.7 es un modelo de razonamiento: usa tokens en <think>...</think>
            # antes de la respuesta final. Le damos margen amplio para que
            # quede presupuesto para el JSON tras la cadena de pensamiento.
            "max_tokens": 1024,
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        # OpenAI-compatible response shape.
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ""

    def _parse_response(self, content: str) -> AIValidationResult | None:
        if not content:
            return None
        # Modelos de razonamiento (como MiniMax-M2.7) producen <think>...</think>
        # ANTES del JSON final. Removemos cualquier bloque de razonamiento
        # explícito y luego buscamos el ÚLTIMO objeto JSON (el veredicto final).
        cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        # Buscar todos los objetos JSON candidatos y quedarse con el último válido.
        candidates = re.findall(r"\{[^{}]*\}", cleaned, re.DOTALL)
        if not candidates:
            # Fallback: el texto puede tener {...} con nesting, buscar greedy.
            m = re.search(r"\{.*\}", cleaned, re.DOTALL)
            candidates = [m.group(0)] if m else []
        if not candidates:
            return None

        data = None
        for cand in reversed(candidates):
            try:
                data = json.loads(cand)
                break
            except json.JSONDecodeError:
                continue
        if data is None:
            return None

        status_raw = (data.get("status") or "").strip().lower()
        reason = (data.get("reason") or "").strip()
        if status_raw not in ("valid", "review", "invalid"):
            return None
        return AIValidationResult(
            status=AddressValidation(status_raw),
            reason=reason or "(sin razón provista)",
            raw_response=content,
            model=self.model,
        )


def _normalize_for_cache(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _load_examples_from_db(db_path) -> list[tuple[str, str, str]]:
    """Lee los ejemplos few-shot ACTIVOS de la tabla effi_address_examples.

    Si la tabla está vacía o la lectura falla, devuelve lista vacía — el
    caller (build_system_prompt) cae a los _DEFAULT_EXAMPLES hardcodeados.
    """
    if not db_path:
        return []
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT address, veredicto, reason FROM effi_address_examples "
                "WHERE activo = 1 ORDER BY veredicto, id"
            ).fetchall()
        finally:
            conn.close()
        return [(r[0], r[1], r[2]) for r in rows]
    except Exception:
        return []


def build_validator_from_settings(settings) -> MiniMaxAddressValidator | None:
    """Factory: devuelve un MiniMaxAddressValidator si está habilitado y configurado.

    Si AI_ADDRESS_VALIDATION está off o falta MINIMAX_API_KEY, devuelve None
    y el runner usa solo regex.

    Los ejemplos few-shot se leen de la tabla effi_address_examples (editable
    en /effi/address-examples). Si la tabla está vacía, usa los default.
    """
    if not getattr(settings, "ai_address_validation", False):
        return None
    if not getattr(settings, "minimax_api_key", ""):
        return None

    db_path = getattr(settings, "db_path", None)
    examples = _load_examples_from_db(db_path)
    system_prompt = build_system_prompt(examples)  # examples vacío → default

    return MiniMaxAddressValidator(
        api_key=settings.minimax_api_key,
        model=settings.minimax_model,
        base_url=settings.minimax_base_url,
        timeout_seconds=settings.minimax_timeout_seconds,
        system_prompt=system_prompt,
    )
