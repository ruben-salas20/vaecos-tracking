"""Debug del validador IA — llama a MiniMax mostrando errores y respuesta cruda."""
from __future__ import annotations

import json
import sys
import traceback
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v0.4"))

from app.effi_guides.address_ai_validator import (  # noqa: E402
    SYSTEM_PROMPT,
    MiniMaxAddressValidator,
)
from app.effi_guides.effi_config import load_settings  # noqa: E402


TEST_ADDRESSES = [
    "sentro comercial santa clara En el sentro comercial santa clara",
    "Frente a banco banrrural Pegado de la farmacia manuelita",
    "Frente de la escuela urbana Salida a antigua tutuapa",
]


def main():
    settings = load_settings()
    print(f"→ ai_address_validation: {settings.ai_address_validation}")
    print(f"→ MINIMAX_API_KEY: {'(set, {} chars)'.format(len(settings.minimax_api_key)) if settings.minimax_api_key else '(EMPTY)'}")
    print(f"→ MINIMAX_MODEL    : {settings.minimax_model}")
    print(f"→ MINIMAX_BASE_URL : {settings.minimax_base_url}")
    print(f"→ Timeout          : {settings.minimax_timeout_seconds}s")
    print()

    if not settings.minimax_api_key:
        print("✗ API key vacía — el .env no se cargó o el nombre de la variable no coincide.")
        return 2

    endpoint = f"{settings.minimax_base_url}/chat/completions"
    body = {
        "model": settings.minimax_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f'Evalúa esta dirección guatemalteca:\n"{TEST_ADDRESSES[0]}"'},
        ],
        "temperature": 0.1,
        "max_tokens": 200,
    }

    print(f"→ POST {endpoint}")
    print(f"→ body.model = {body['model']}")
    print()

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.minimax_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=settings.minimax_timeout_seconds) as resp:
            print(f"✓ HTTP {resp.status}")
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"✗ HTTPError {e.code} {e.reason}")
        try:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"  Response body:\n{err_body[:2000]}")
        except Exception:
            pass
        return 1
    except urllib.error.URLError as e:
        print(f"✗ URLError: {e.reason}")
        return 1
    except Exception as e:
        print(f"✗ Exception inesperada: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 1

    print(f"→ Respuesta cruda (primeros 2000 chars):")
    print(raw[:2000])
    print()

    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        print(f"→ Content extraído:\n{content}")
    except Exception as e:
        print(f"✗ No pude extraer choices[0].message.content: {e}")
        return 1

    print()
    print("──── Ahora probamos las 3 direcciones via MiniMaxAddressValidator ────")
    v = MiniMaxAddressValidator(
        api_key=settings.minimax_api_key,
        model=settings.minimax_model,
        base_url=settings.minimax_base_url,
        timeout_seconds=settings.minimax_timeout_seconds,
    )
    for addr in TEST_ADDRESSES:
        result = v.evaluate(addr)
        print(f"\n{addr!r}")
        print(f"  → {result}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
