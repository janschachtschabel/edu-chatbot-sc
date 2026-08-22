"""Der Weg von der ``.env`` in den Container — die Luecke, die K2 offenliess.

**Gemessen am 2026-08-18:** ``CORS_ALLOW_ALL=false`` in ``deploy/.env`` blieb in
Produktion wirkungslos. ``docker compose`` liest die ``.env`` nur zur Ersetzung
IN der Compose-Datei; was nicht unter ``environment:`` steht, erreicht den
Container nie. Der Schalter war gebaut, getestet und dokumentiert — und genau
auf dem Weg, den ``deploy/INSTALL-schnellstart.md`` beschreibt, tot. Der
Betreiber haette geglaubt, er habe zugemacht: dieselbe stille Uebersteuerung,
gegen die K2 die Warnzeile eingezogen hat, nur eine Ebene hoeher.

Der Fehler ist eine KLASSE, kein Einzelfall — jeder kuenftige Schalter kann so
verschwinden. Deshalb prueft der erste Test alle dokumentierten Schluessel.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_DEPLOY = Path(__file__).resolve().parents[2] / "deploy"
_ENV_BEISPIEL = _DEPLOY / ".env.example"
_COMPOSE = _DEPLOY / "compose.prod.yml"


def _dokumentierte_schluessel() -> list[str]:
    """Die Namen, die ``deploy/.env.example`` einem Betreiber anbietet."""
    return re.findall(r"^([A-Z_][A-Z0-9_]*)=", _ENV_BEISPIEL.read_text("utf-8"), re.M)


def test_jeder_dokumentierte_schluessel_steht_in_compose() -> None:
    """Was die Beispiel-``.env`` anbietet, muss in ``compose.prod.yml`` vorkommen.

    Die Zusage ist bewusst schwach — sie prueft nur, dass der Name ueberhaupt
    auftaucht, nicht an welcher Stelle. Genau das reicht gegen den gemessenen
    Fehler (Name kommt NIRGENDS vor => erreicht niemanden) und erzeugt keine
    Fehlalarme fuer Werte, die zurecht woanders stehen: ``PUBLIC_HOST`` in den
    traefik-Labels, ``BOERDI_IMAGE`` unter ``image:``, ``POSTGRES_*`` beim
    Datenbank-Dienst. Wo es genau stehen muss, prueft der Test darunter.
    """
    text = _COMPOSE.read_text("utf-8")
    fehlend = [k for k in _dokumentierte_schluessel() if not re.search(rf"\b{k}\b", text)]
    assert fehlend == [], (
        f"in deploy/.env.example dokumentiert, in compose.prod.yml nirgends "
        f"verdrahtet: {fehlend} — diese Werte erreichen den Container nie"
    )


def test_eval_chat_url_hat_einen_container_tauglichen_default() -> None:
    """``EVAL_CHAT_URL`` muss im Container auf den EIGENEN Port zeigen.

    Gemessen auf Prod am 2026-08-22: die Compose reichte den Wert nur leer
    durch (``${EVAL_CHAT_URL:-}``), der Code-Default zeigt auf ALT-Port 8000 —
    das Image lauscht aber auf 8100. Jeder Eval-Start brach damit im Preflight
    mit „Chat-Backend nicht erreichbar" ab, bis ein Betreiber die Variable von
    Hand setzte. Der Default ist der Selbstaufruf im Container (kein Umweg
    ueber traefik/TLS); die ``.env`` darf weiterhin uebersteuern.
    """
    for compose in (_COMPOSE, _DEPLOY / "compose.dev.yml"):
        dienste = yaml.safe_load(compose.read_text("utf-8"))["services"]
        umgebung = dienste["backend"]["environment"]
        wert = str(umgebung.get("EVAL_CHAT_URL", ""))
        assert "http://127.0.0.1:8100/api/chat" in wert, (
            f"{compose.name}: EVAL_CHAT_URL ohne Selbstaufruf-Default — "
            f"Eval-Starts laufen im Container gegen ALT-Port 8000 (Wert: {wert!r})"
        )


def test_die_cors_schalter_erreichen_den_backend_dienst() -> None:
    """Die drei CORS-Namen muessen in der Umgebung des Backends stehen.

    Nicht irgendwo in der Datei: ``environment:`` des Dienstes ``backend`` ist
    der einzige Ort, von dem aus ``settings.py`` sie liest.
    """
    dienste = yaml.safe_load(_COMPOSE.read_text("utf-8"))["services"]
    umgebung = dienste["backend"]["environment"]
    assert isinstance(umgebung, dict), "environment als Liste — Test anpassen"
    for name in ("CORS_ORIGINS", "CORS_ALLOW_ALL", "CORS_ALLOW_EXTENSIONS"):
        assert name in umgebung, f"{name} erreicht den Backend-Container nicht"
