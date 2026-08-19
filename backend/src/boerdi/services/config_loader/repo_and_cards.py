"""Repo-URL + card-pipeline loaders — port of ALT config_loader/repo_and_cards.py
(env overrides now via settings; clamps 1:1).
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.services.config_loader._store import area
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

_PROD_DEFAULT = "https://redaktion.openeduhub.net"
_FALLBACK_HOSTS = [
    _PROD_DEFAULT,
    "https://repository.staging.openeduhub.net",
    "https://repository.openeduhub.net",
]

#: Zuletzt aufgelöste Angabe als ``(Adresse, Quelle)``. Nur fürs Protokoll: die
#: Auflösung wird gemeldet, wenn sie sich ÄNDERT — beim ersten Zug, und wieder,
#: wenn die Redaktion sie im Studio umstellt. Ohne dieses Merkmal stünde die
#: Zeile bei jedem Kartenfeld im Log.
_letzte_aufloesung: tuple[str, str] | None = None


def reset_repo_base_url_cache() -> None:
    """Merkmal der letzten Auflösung vergessen (Tests; Config-Wechsel)."""
    global _letzte_aufloesung
    _letzte_aufloesung = None


def _repo_aus_der_konfig() -> str:
    """Die Studio-Angabe, oder "" wenn keine brauchbare da ist.

    Unbrauchbar heißt: leer, kein String, oder keine Adresse. Der letzte Fall
    wird gemeldet — eine vertippte Angabe soll nicht still auf Produktion
    zurückfallen, denn genau diese Stille war der Befund.
    """
    try:
        roh = (area("01-base/card-pipeline").get("card_pipeline") or {}).get("repo_base_url")
    except Exception:
        logger.debug("card-pipeline-Bereich nicht lesbar; Repoangabe kommt aus der "
                     "Umgebung", exc_info=True)
        return ""
    text = str(roh or "").strip().rstrip("/")
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        logger.warning(
            "repo_base_url in der Konfiguration ist keine Adresse (%r) — es gilt "
            "die Umgebungsvariable REPO_BASE_URL", text,
        )
        return ""
    return text


def get_repo_base_url() -> str:
    """Das Repositorium, gegen das dieser Chatbot läuft.

    Reihenfolge: **Konfiguration** (``01-base/card-pipeline.repo_base_url``) vor
    **Umgebung** (``REPO_BASE_URL``, Vorgabe Staging). Die Konfiguration
    gewinnt, weil die Angabe dort nachlesbar sein soll — eine Einstellung, die
    nur in der Deploy-Umgebung existiert, kann im Studio niemand prüfen
    (Nutzer-Vorgabe 2026-08-14). Der geltende Wert steht in ``GET /api/health``.

    Ohne Schrägstrich am Ende: alle Verbraucher hängen ``/edu-sharing/…`` an.

    Die Vorgabe ist **Staging**, seit sie am 2026-08-19 auf Produktion stand,
    während der MCP-Server Staging befragte: ``rewrite_repo_host_v2`` schrieb
    die Treffer damit auf einen Host um, auf dem es sie nicht gibt. Eine
    vergessene Angabe darf nicht im Wirkbetrieb landen.
    """
    global _letzte_aufloesung
    wert = _repo_aus_der_konfig()
    quelle = "Konfiguration"
    if not wert:
        wert = str(get_settings().repo_base_url or "").strip().rstrip("/")
        quelle = "Umgebung"
    if _letzte_aufloesung != (wert, quelle):
        _letzte_aufloesung = (wert, quelle)
        logger.info("Repositorium: %s (Quelle: %s)", wert, quelle)
    return wert


def rewrite_repo_host(url: str) -> str:
    """Rewrite the prod-default host prefix to the configured base (ALT v1)."""
    if not isinstance(url, str) or not url:
        return url
    base = get_repo_base_url()
    if base == _PROD_DEFAULT or not url.startswith(_PROD_DEFAULT):
        return url
    return base + url[len(_PROD_DEFAULT):]


def _known_repo_hosts() -> list[str]:
    return load_card_pipeline_config()["known_repo_hosts"]


def rewrite_repo_host_v2(url: str, target_repo_base: str | None = None) -> str:
    """Bidirectional host rewrite over the known_repo_hosts list (ALT v2)."""
    if not isinstance(url, str) or not url:
        return url
    target = (target_repo_base or get_repo_base_url()).rstrip("/")
    for host in _known_repo_hosts():
        if host != target and url.startswith(host):
            return target + url[len(host):]
    return url


def load_card_pipeline_config() -> dict[str, Any]:
    cfg = area("01-base/card-pipeline").get("card_pipeline") or {}

    def _int(key: str, default: int, lo: int, hi: int) -> int:
        raw = cfg.get(key)
        try:
            v = int(raw) if raw is not None else default
        except (TypeError, ValueError):
            v = default
        return max(lo, min(hi, v))

    pool_size = _int("pool_size", 20, 5, 50)
    llm_pool = _int("llm_curation_pool", min(15, pool_size), 1, pool_size)
    final = _int("final_selection_size", 5, 1, 10)
    hosts_raw = cfg.get("known_repo_hosts") or list(_FALLBACK_HOSTS)
    hosts: list[str] = []
    for h in hosts_raw:
        s = str(h or "").strip().rstrip("/")
        if s and s not in hosts:
            hosts.append(s)
    return {
        "pool_size": pool_size,
        "llm_curation_pool": llm_pool,
        "final_selection_size": final,
        "enable_llm_curation": bool(cfg.get("enable_llm_curation", True)),
        "min_displayed_cards": _int("min_displayed_cards", 5, 0, final),
        "known_repo_hosts": hosts or list(_FALLBACK_HOSTS),
    }


def card_pipeline_v2_enabled() -> bool:
    return get_settings().card_pipeline_v2  # env CARD_PIPELINE_V2, default off
