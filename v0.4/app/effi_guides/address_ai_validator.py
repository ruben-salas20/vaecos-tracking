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


SYSTEM_PROMPT = (
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
    "Considera typos comunes en español guatemalteco (sentro=centro, kalle=calle, sona=zona, "
    "banrrural=Banrural, krk=cerca, kasa=casa, kuadras=cuadras, etc.). Acepta abreviaturas "
    "locales (z=zona, av=avenida).\n\n"
    "EJEMPLOS DE REFERENCIA — calibrá tu juicio contra estos casos del negocio:\n\n"
    'Dirección: "5 calle 12-51 zona uno de mixco"\n'
    'Veredicto: {"status": "valid", "reason": "Estructura urbana cardinal completa"}\n\n'
    'Dirección: "Aldea El Florido frente a la iglesia católica, Escuintla"\n'
    'Veredicto: {"status": "valid", "reason": "Aldea identificable con landmark claro"}\n\n'
    'Dirección: "Cargo expreso Morales (retiro en agencia)"\n'
    'Veredicto: {"status": "valid", "reason": "Retiro en agencia CARGO EXPRESO"}\n\n'
    'Dirección: "9 Calle 0-54 zona 3 colonia las victorias enfrente a la vieja bodega de tecnoprosa"\n'
    'Veredicto: {"status": "valid", "reason": "Dirección urbana cardinal con landmark"}\n\n'
    'Dirección: "sentro comercial santa clara En el sentro comercial santa clara"\n'
    'Veredicto: {"status": "valid", "reason": "Centro comercial Santa Clara identificable pese al typo"}\n\n'
    'Dirección: "Frente a banco banrrural Pegado de la farmacia manuelita"\n'
    'Veredicto: {"status": "valid", "reason": "Dos landmarks comerciales en el mismo punto"}\n\n'
    'Dirección: "Frente de la escuela urbana Salida a antigua tutuapa"\n'
    'Veredicto: {"status": "review", "reason": "Landmark y referencia pero municipio/colonia imprecisos"}\n\n'
    'Dirección: "Saliendo de antigua para chimaltenango, despues de la 2da curva, casa del señor Pedro color celeste"\n'
    'Veredicto: {"status": "valid", "reason": "Ruta clara entre 2 ciudades con casa específica identificable"}\n\n'
    'Dirección: "Colonia la promesa La democracia"\n'
    'Veredicto: {"status": "review", "reason": "Colonia genérica sin landmark ni estructura cardinal"}\n\n'
    'Dirección: "Retalhuleu Caballo blanco"\n'
    'Veredicto: {"status": "invalid", "reason": "Solo nombres de lugar sin referencia ni dirección"}\n\n'
    'Dirección: "en mi casa"\n'
    'Veredicto: {"status": "invalid", "reason": "Trivial sin ubicación concreta"}\n\n'
    'Dirección: "Por ahi por las afueras Pregunten por mi"\n'
    'Veredicto: {"status": "invalid", "reason": "Demasiado vago, sin referencia concreta"}\n\n'
    "Responde ÚNICAMENTE con un JSON en una sola línea, sin texto adicional:\n"
    '{"status": "valid|review|invalid", "reason": "razón breve en español, máximo 15 palabras"}'
)


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
    ):
        if not api_key:
            raise ValueError("MiniMaxAddressValidator requires api_key")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
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
                {"role": "system", "content": SYSTEM_PROMPT},
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


def build_validator_from_settings(settings) -> MiniMaxAddressValidator | None:
    """Factory: devuelve un MiniMaxAddressValidator si está habilitado y configurado.

    Si AI_ADDRESS_VALIDATION está off o falta MINIMAX_API_KEY, devuelve None
    y el runner usa solo regex.
    """
    if not getattr(settings, "ai_address_validation", False):
        return None
    if not getattr(settings, "minimax_api_key", ""):
        return None
    return MiniMaxAddressValidator(
        api_key=settings.minimax_api_key,
        model=settings.minimax_model,
        base_url=settings.minimax_base_url,
        timeout_seconds=settings.minimax_timeout_seconds,
    )
