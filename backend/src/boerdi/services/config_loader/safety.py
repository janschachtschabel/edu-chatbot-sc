"""Safety/Policy/Privacy/Guide-Mode/Quality-Log loaders — port of ALT
config_loader/safety.py (defaults + normalizations 1:1).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from boerdi.obs.drossel import gedrosselt
from boerdi.services.config_loader._store import area
from boerdi.services.config_loader.repo_and_cards import get_repo_base_url
from boerdi.services.config_loader.schalter import FEHLT, als_schalter
from boerdi.settings import get_settings, ist_lockerer, pruefe_drosselgrenze

logger = logging.getLogger(__name__)


def load_policy_config() -> dict[str, Any]:
    return area("01-base/policy")


def load_safety_config() -> dict[str, Any]:
    return area("01-base/safety-config")


#: Die zwei Stufen der Zug-Grenzen (Paket 19, M-4) — Schlüssel in ``turn_limits``.
ZUG_STUFEN = ("anonymous", "authenticated")


def load_turn_limits() -> dict[str, str]:
    """Die Zug-Grenzen je Stufe, fertig zum Gebrauch (Paket 19, M-4 / Entscheid P19-E3).

    Kuratiert wie die übrigen Lader: genau ``anonymous`` und ``authenticated``. Leer, fehlend
    oder unbrauchbar (am Speichern vorbei, etwa direkt in der DB) ⇒ ``RATE_LIMIT_CHAT`` — ein
    Zug scheitert nie an der Config; das Unbrauchbare meldet eine gedrosselte Warnung, ohne den
    Wert. ``off`` bleibt ``off``: das Abschalten liest ``api/ratelimit``.
    """
    vorgabe = get_settings().rate_limit_chat
    block = area("01-base/safety-config").get("turn_limits")
    if not isinstance(block, dict):
        block = {}
    grenzen: dict[str, str] = {}
    for stufe in ZUG_STUFEN:
        wert = block.get(stufe)
        if wert is None or (isinstance(wert, str) and not wert.strip()):
            grenzen[stufe] = vorgabe
            continue
        try:
            if not isinstance(wert, str):
                raise ValueError(type(wert).__name__)
            grenzen[stufe] = pruefe_drosselgrenze(wert, "turn_limits")
            if ist_lockerer(wert, vorgabe):
                # Review, Punkt 7: das Studio darf den Betreiber-Schutz lockern — sichtbar.
                gedrosselt(logger, logging.WARNING, f"turn_limits:{stufe}:locker", 3600.0,
                           "turn_limits.%s=%r ist lockerer als RATE_LIMIT_CHAT=%r",
                           stufe, wert, vorgabe)
        except ValueError:
            gedrosselt(logger, logging.WARNING, f"turn_limits:{stufe}", 300.0,
                       "turn_limits.%s ist unbrauchbar (%s) — es gilt RATE_LIMIT_CHAT",
                       stufe, type(wert).__name__)
            grenzen[stufe] = vorgabe
    return grenzen


def load_quality_log_config() -> dict[str, Any]:
    return area("01-base/quality-log-config")


def load_guide_mode_config() -> dict[str, Any]:
    cfg = area("01-base/guide-mode").get("guide_mode") or {}
    # 0 honoured as "unlimited" — only missing/non-int falls back to 5 (ALT)
    raw_max = cfg.get("max_guide_targets_per_turn")
    if raw_max is None:
        max_targets = 5
    else:
        try:
            max_targets = int(raw_max)
        except (TypeError, ValueError):
            max_targets = 5

    raw_qr = cfg.get("max_guide_quick_replies")
    if raw_qr is None:
        max_guide_qrs = 2
    else:
        try:
            max_guide_qrs = int(raw_qr)
        except (TypeError, ValueError):
            max_guide_qrs = 2
    max_guide_qrs = max(1, min(3, max_guide_qrs))

    # env override replaces YAML entirely (per-deployment allow-lists)
    env_td = (get_settings().guide_trusted_domains or "").strip()
    td_raw = re.split(r"[,\s]+", env_td) if env_td else list(cfg.get("trusted_domains") or [])
    trusted_domains: list[str] = []
    for d in td_raw:
        s = str(d or "").strip()
        if not s:
            continue
        s = re.sub(r"^https?://", "", s, flags=re.IGNORECASE).strip("/").lower()
        if s and s not in trusted_domains:
            trusted_domains.append(s)

    return {
        "allowed_hosts": [
            str(h).strip().lower() for h in (cfg.get("allowed_hosts") or []) if str(h).strip()
        ],
        "url_fields_priority": list(cfg.get("url_fields_priority") or [
            "topic_page_url", "wlo_url", "url", "content_url", "preview_url",
        ]),
        "max_guide_targets_per_turn": max_targets,
        "max_guide_quick_replies": max_guide_qrs,
        "trusted_domains": trusted_domains,
        "repo_base_url": get_repo_base_url(),
    }


def load_privacy_config() -> dict[str, bool]:
    """Die Datenschutz-Schalter. Wirft bei einem unbrauchbaren Wert (``streng``): die Leser
    speichern dann nichts (Paket 18E, F1 — :func:`melde_datenschutz_unlesbar`)."""
    section = area("01-base/privacy-config").get("logging", {})
    if not isinstance(section, dict):
        # ``logging: null`` gab früher die Vorgaben (an) — fail-closed wie ein kaputter Wert.
        raise ValueError(f"privacy.logging: keine Zuordnung ({type(section).__name__})")
    return {
        "messages": als_schalter(section.get("messages", FEHLT), True,
                                 name="privacy.logging.messages", streng=True),
        "memory": als_schalter(section.get("memory", FEHLT), True,
                               name="privacy.logging.memory", streng=True),
        "quality": als_schalter(section.get("quality", FEHLT), True,
                                name="privacy.logging.quality", streng=True),
        "safety": True,  # not user-togglable — audit trail can't be silenced
    }


def melde_datenschutz_unlesbar(art: str, fehler: BaseException) -> None:
    """Die Datenschutz-Konfiguration ist nicht lesbar — der Leser speichert ``art`` nicht
    (Paket 18E, F1: fail-closed; ein ausdrückliches „aus“ darf nie an einer kaputten
    Konfiguration scheitern). Höchstens eine Warnung je Minute und Art."""
    gedrosselt(logger, logging.WARNING, f"datenschutz:{art}", 60.0,
               "Datenschutz-Konfiguration nicht lesbar (%s) — %s wird nicht gespeichert",
               type(fehler).__name__, art)
