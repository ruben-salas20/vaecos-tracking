"""Agent loop tool-use con MiniMax M2.7.

Protocolo:
1. System prompt describe las tools disponibles + formato JSON estricto
2. El modelo responde JSON con `{"action": "tool_call", "tool": "...", "args": {...}}`
   o con `{"action": "answer", "text": "..."}`
3. Si es tool_call: ejecutamos, agregamos al contexto, re-llamamos al modelo
4. Si es answer: cerramos el turno, persistimos respuesta final

Hard limits:
- max_iterations: 5 (evita loops infinitos del modelo)
- max_history_messages: 40 (≈20 turnos user+assistant del histórico previo)
- timeout por llamada: 30s
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime

from .repository import ChatRepository
from .tools import TOOL_REGISTRY, execute_tool, tools_for_prompt


# ── Configuración ─────────────────────────────────────────────────────


MAX_ITERATIONS = 5
MAX_HISTORY_MESSAGES = 40
DEFAULT_TIMEOUT_SECONDS = 30


def _build_system_prompt() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return (
        "Eres el asistente de VAECOS, una plataforma de tracking de guías + finanzas.\n\n"
        f"Hoy es {today}. Moneda de finanzas: COP (peso colombiano).\n"
        "Respondés SIEMPRE en español, de forma concisa, directa y útil.\n\n"
        "════════════════════════════════════════════════════════════\n"
        "QUÉ ES VAECOS (overview rápido)\n"
        "════════════════════════════════════════════════════════════\n"
        "App Flask + SQLite con sidebar de navegación. Áreas principales:\n"
        "  • Operación: Centro Operativo, Todas las guías, Buscar, Requiere atención\n"
        "  • Inteligencia: Analytics, Por recoger, Historial de corridas\n"
        "  • Finanzas: Movimientos, Analytics finanzas\n"
        "  • Acciones: Nueva corrida, Importar guías (Excel), Creador guías Effi (bot)\n"
        "  • Admin: Reglas, Usuarios, Catálogo Effi, Catálogo finanzas\n\n"
        "DOS tipos de preguntas y cómo responderlas:\n\n"
        "  TIPO 1 — DATOS DEL NEGOCIO (cuántas guías, balance del mes, etc.):\n"
        "    → Llamar tools de data: get_logistic_summary, get_finanzas_summary,\n"
        "      search_guides, get_top_clients, list_recent_runs.\n\n"
        "  TIPO 2 — CÓMO USAR LA APP / QUÉ ES / DÓNDE ESTÁ / QUÉ SIGNIFICA:\n"
        "    → SIEMPRE llamar PRIMERO `get_app_help` con un topic relevante.\n"
        "    Ejemplos que CADA UNO debe disparar get_app_help:\n"
        "      - '¿cómo importo un Excel?' → get_app_help(topic='importar excel')\n"
        "      - '¿qué significa Gestión novedad?' → get_app_help(topic='estados')\n"
        "      - '¿dónde edito categorías?' → get_app_help(topic='finanzas categorias')\n"
        "      - '¿qué hace el bot Effi?' → get_app_help(topic='effi bot')\n"
        "      - '¿cómo lanzo una corrida?' → get_app_help(topic='corridas')\n"
        "      - '¿qué es VAECOS?' → get_app_help(topic='overview')\n"
        "    El manual SÍ es una fuente AUTORITATIVA — NO es 'conocimiento general'.\n"
        "    Después de recibir el contenido del manual, parafrasealo de forma concisa al usuario.\n\n"
        "REGLA: Antes de decir 'no tengo esa información', SIEMPRE probá get_app_help primero\n"
        "para preguntas de tipo 'cómo/qué/dónde/qué significa'. Solo decí 'no sé' si el manual\n"
        "tampoco trae el dato.\n\n"
        "════════════════════════════════════════════════════════════\n"
        "REGLA #1 — CERO ALUCINACIONES (la regla más importante)\n"
        "════════════════════════════════════════════════════════════\n"
        "NUNCA inventes datos, números, nombres, fechas, IDs, porcentajes ni cantidades.\n"
        "SI NO TENÉS LA DATA en el resultado de una tool, decilo explícitamente.\n"
        "NO uses 'conocimiento general' para responder sobre VAECOS — TODA la data del negocio\n"
        "viene EXCLUSIVAMENTE de las tools (data tools O `get_app_help`). Si la pregunta no se\n"
        "puede contestar con tus tools (incluyendo el manual), decilo: 'No tengo forma de saber eso'.\n\n"
        "IMPORTANTE: `get_app_help` ES una fuente legítima — NO confundir con 'conocimiento general'.\n"
        "Cuando el manual responde una pregunta, eso ES una respuesta válida con respaldo.\n\n"
        "Ejemplos del comportamiento CORRECTO:\n"
        "  Usuario: '¿Cuándo entregaron la guía X?'\n"
        "  → Si search_guides devuelve un row sin fecha_entrega → respondé: 'La guía X existe \n"
        "    pero no tengo la fecha exacta de entrega en mi data. Te puedo decir el estado actual: ...'\n"
        "  → NUNCA inventes una fecha.\n\n"
        "  Usuario: '¿Cuál es el margen real del producto Y?'\n"
        "  → No hay tool para eso → respondé: 'No tengo acceso a costos de producto por guía,\n"
        "    así que no puedo calcular margen real. Lo que sí puedo darte es el valor declarado total.'\n"
        "  → NUNCA inventes un porcentaje.\n\n"
        "  Usuario: '¿Cuántos pedidos vienen de Colombia vs Guatemala?'\n"
        "  → No hay tool de geolocalización → respondé: 'No tengo esa distinción en mis datos.\n"
        "    Las guías están en effi (transportadora guatemalteca) pero no tengo país del cliente.'\n\n"
        "Cuando tengas DUDA sobre si la respuesta está en tus datos, llamá a la tool relevante PRIMERO\n"
        "para verificar, y si la tool no trae lo que necesitás, decí honestamente que no sabés.\n\n"
        "════════════════════════════════════════════════════════════\n"
        "TOOLS DISPONIBLES (es TODA la data que tenés sobre VAECOS):\n"
        "════════════════════════════════════════════════════════════\n"
        f"{tools_for_prompt()}\n\n"
        "════════════════════════════════════════════════════════════\n"
        "PROTOCOLO ESTRICTO de respuesta (formato JSON)\n"
        "════════════════════════════════════════════════════════════\n"
        "Cada vez que respondas, lo haces con UN ÚNICO objeto JSON al final, sin código markdown, sin texto adicional.\n"
        "Dos formatos posibles:\n\n"
        '  1) Llamar una función:\n'
        '     {"action": "tool_call", "tool": "<nombre>", "args": {<argumentos>}}\n\n'
        '  2) Responder al usuario:\n'
        '     {"action": "answer", "text": "<respuesta en español, puede usar saltos de línea con \\n>"}\n\n'
        "REGLAS OPERATIVAS:\n"
        "- Para preguntas que necesitan datos del negocio → SIEMPRE llamá la tool primero\n"
        "- Después de recibir un resultado, evaluá: ¿la data alcanza para responder? Si no → decílo\n"
        "- Minimizá tool calls: máximo 3 por mensaje del usuario\n"
        "- Si no sabés qué tool usar para una pregunta, NO inventes — preguntá al usuario qué necesita\n"
        "- Para preguntas conversacionales triviales ('hola', 'qué podés hacer'), respondé directamente sin tool calls\n"
        "- Formatea números financieros con separador de miles ('1.234.567 COP')\n"
        "- Si una tool devuelve {error: ...}, NO la llames de nuevo con los mismos args; respondé al usuario explicando\n"
        "- NO mezcles datos de tools distintas en cálculos sin verificar que sean comparables\n"
        "- NO calcules porcentajes inventando totales — usá solo los totales que la tool devolvió\n"
        "- NO asumas correlaciones entre logística y finanzas si la data no las muestra explícitamente\n"
        "- NO incluyas explicaciones FUERA del JSON. Tu salida es SOLO el JSON.\n"
    )


# ── Cliente MiniMax ───────────────────────────────────────────────────


@dataclass
class AgentSettings:
    api_key: str
    model: str = "MiniMax-M2.7"
    base_url: str = "https://api.minimax.io/v1"
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


class _MiniMaxClient:
    def __init__(self, settings: AgentSettings):
        self.settings = settings

    def chat(self, messages: list[dict]) -> str:
        """Llamada bloqueante. Devuelve content del primer choice. Raise on HTTP error."""
        endpoint = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        body = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 2048,
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.settings.timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ""


# ── Parser de respuesta ───────────────────────────────────────────────


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _extract_action(content: str) -> dict | None:
    """Extrae el último objeto JSON válido del content del modelo.

    M2.7 a veces escribe <think>...</think> antes del JSON. Lo removemos y luego
    buscamos el último objeto JSON.
    """
    if not content:
        return None
    cleaned = _THINK_RE.sub("", content).strip()

    # Buscamos todos los objetos top-level {...} y nos quedamos con el último parseable.
    # Soportamos nesting simple usando balance de braces.
    candidates = []
    depth = 0
    start = -1
    for i, ch in enumerate(cleaned):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                candidates.append(cleaned[start:i + 1])
                start = -1

    for cand in reversed(candidates):
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict) and obj.get("action") in ("tool_call", "answer"):
                return obj
        except json.JSONDecodeError:
            continue
    return None


# ── Agent ─────────────────────────────────────────────────────────────


@dataclass
class AgentResult:
    answer: str
    tool_calls: list[dict]   # [{tool, args, summary}]
    iterations: int
    error: str | None = None


class Agent:
    def __init__(self, settings: AgentSettings, repo: ChatRepository, db_path: str):
        self.client = _MiniMaxClient(settings)
        self.repo = repo
        self.db_path = db_path

    def run_turn(self, user_id: int, conv_id: int, user_message: str) -> AgentResult:
        # Persistimos el mensaje del usuario
        self.repo.add_message(conv_id, role="user", content=user_message)

        # Construimos el contexto del modelo desde el histórico
        history = self.repo.list_messages(conv_id, limit=MAX_HISTORY_MESSAGES)
        messages = [{"role": "system", "content": _build_system_prompt()}]
        for m in history:
            if m.role == "tool":
                # tool result → role 'user' con prefijo, porque no todos los modelos
                # tienen 'tool' role en OpenAI-compatible APIs antiguas.
                messages.append({
                    "role": "user",
                    "content": f"[Resultado de tool {m.tool_name}]:\n{m.content}",
                })
            elif m.role == "assistant":
                # Reinyectamos el JSON que produjo
                messages.append({"role": "assistant", "content": m.content})
            elif m.role == "user":
                messages.append({"role": "user", "content": m.content})

        tool_calls_made: list[dict] = []

        for iteration in range(1, MAX_ITERATIONS + 1):
            try:
                raw_response = self.client.chat(messages)
            except urllib.error.HTTPError as e:
                err_msg = f"HTTPError {e.code}: {e.read().decode('utf-8', errors='ignore')[:200]}"
                return AgentResult(answer="", tool_calls=tool_calls_made, iterations=iteration, error=err_msg)
            except Exception as e:
                return AgentResult(
                    answer="", tool_calls=tool_calls_made, iterations=iteration,
                    error=f"{type(e).__name__}: {e}",
                )

            action = _extract_action(raw_response)
            if action is None:
                # Modelo no respetó el formato JSON. Caso típico: respondió texto
                # libre con <think>...</think> + respuesta. Limpiamos y persistimos
                # como answer normal para que el chat_history funcione correcto.
                cleaned = _THINK_RE.sub("", raw_response).strip()
                # Quitar también cualquier ```json o ``` markdown que el modelo agregue.
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.MULTILINE).strip()
                if not cleaned:
                    cleaned = "(respuesta vacía del modelo)"
                self.repo.add_message(
                    conv_id, role="assistant",
                    content=json.dumps({"action": "answer", "text": cleaned}, ensure_ascii=False),
                )
                return AgentResult(
                    answer=cleaned,
                    tool_calls=tool_calls_made, iterations=iteration,
                    error="Modelo no respetó formato JSON (respuesta limpiada)",
                )

            if action["action"] == "answer":
                answer_text = (action.get("text") or "").strip()
                # Persistimos el JSON crudo (para audit) Y el texto plano para el UI
                self.repo.add_message(
                    conv_id, role="assistant",
                    content=json.dumps({"action": "answer", "text": answer_text}, ensure_ascii=False),
                )
                return AgentResult(
                    answer=answer_text, tool_calls=tool_calls_made, iterations=iteration,
                )

            if action["action"] == "tool_call":
                tool_name = action.get("tool", "")
                tool_args = action.get("args") or {}
                if not isinstance(tool_args, dict):
                    tool_args = {}

                # Persistimos el call del modelo en formato LIMPIO (sin <think>).
                # El razonamiento es ephemeral; lo que importa para futuras llamadas es
                # el contenido estructurado del tool_call.
                clean_call = json.dumps(
                    {"action": "tool_call", "tool": tool_name, "args": tool_args},
                    ensure_ascii=False,
                )
                self.repo.add_message(
                    conv_id, role="assistant", content=clean_call,
                    tool_name=tool_name, tool_args=tool_args,
                )

                # Ejecutamos
                t0 = time.time()
                result = execute_tool(tool_name, self.db_path, tool_args)
                latency_ms = int((time.time() - t0) * 1000)
                ok = "error" not in result
                result_json = json.dumps(result, ensure_ascii=False)[:8000]

                # Audit
                self.repo.log_tool_call(
                    user_id=user_id, tool_name=tool_name, args=tool_args,
                    result_summary=result_json, latency_ms=latency_ms,
                    ok=ok, error_msg=result.get("error") if not ok else None,
                )

                # Persistimos resultado para re-feed
                self.repo.add_message(
                    conv_id, role="tool", content=result_json, tool_name=tool_name,
                )
                tool_calls_made.append({"tool": tool_name, "args": tool_args, "ok": ok})

                # Agregamos al contexto para la próxima iteración
                messages.append({"role": "assistant", "content": raw_response})
                messages.append({
                    "role": "user",
                    "content": f"[Resultado de tool {tool_name}]:\n{result_json}",
                })
                continue

        # Si llegamos acá, agotamos iteraciones
        return AgentResult(
            answer="(El asistente excedió el límite de operaciones — refrasea tu pregunta o probá una más específica.)",
            tool_calls=tool_calls_made, iterations=MAX_ITERATIONS,
            error="max_iterations_exceeded",
        )


def build_agent(settings_obj, db_path: str, repo: ChatRepository) -> Agent | None:
    """Factory: None si no hay MINIMAX_API_KEY configurada."""
    api_key = getattr(settings_obj, "minimax_api_key", "") or ""
    if not api_key:
        return None
    return Agent(
        settings=AgentSettings(
            api_key=api_key,
            model=getattr(settings_obj, "minimax_model", "MiniMax-M2.7"),
            base_url=getattr(settings_obj, "minimax_base_url", "https://api.minimax.io/v1"),
            timeout_seconds=getattr(settings_obj, "minimax_timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
        ),
        repo=repo,
        db_path=db_path,
    )
