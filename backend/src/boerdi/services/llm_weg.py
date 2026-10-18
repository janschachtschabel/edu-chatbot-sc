"""Der Weg eines Modellaufrufs als Daten (Paket 13, A1).

``llm.route`` entscheidet Schnittstelle und Server; die Messbedingungen eines Laufs
brauchen dieselbe Entscheidung zum Vergleichen — ohne Schlüssel und Kopfzeilen. Ein
eigenes Modul, weil ``llm.py`` an der 300-Zeilen-Grenze steht.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from boerdi.services.betriebsschalter import service_tier
from boerdi.services.llm import route
from boerdi.services.llm_models import (
    get_chat_model,
    get_provider,
    get_reasoning_effort,
    get_verbosity,
    param_rules,
)
from boerdi.services.llm_responses import RESPONSES_PRAEFIX


def weg_beschreibung(model: str | None = None) -> dict[str, Any]:
    """Anbieter, Modell, Schnittstelle, Server und die Denkparameter, die mitgehen.

    ``basis`` ist Host plus Pfad der Basis-URL — kein Schema, keine Anfrage-Parameter.
    Die Denkparameter stehen nur, wo das Modell sie bekommt (``gpt5_params``); der Tarif
    nur bei OpenAI direkt (wie ``llm.wire_transport``).
    """
    resolved = model or get_chat_model()
    litellm_model, api_base, _schluessel, _kopf = route(resolved)
    teile = urlsplit(api_base)
    regeln = param_rules(resolved)
    anbieter = get_provider()
    return {
        "anbieter": anbieter,
        "modell": resolved,
        "api": "responses" if litellm_model.startswith(RESPONSES_PRAEFIX) else "chat",
        "basis": f"{teile.netloc}{teile.path}".rstrip("/"),
        "denkparameter": regeln.gpt5_params,
        "reasoning_effort": get_reasoning_effort() if regeln.gpt5_params else None,
        "verbosity": get_verbosity() if regeln.gpt5_params else None,
        "service_tier": (
            service_tier() if anbieter == "openai" and regeln.gpt5_familie else None),
    }
