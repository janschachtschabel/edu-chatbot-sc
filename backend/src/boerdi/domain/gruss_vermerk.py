"""Welche Seite in welcher Sprache schon begrüßt wurde (Kontext-Gruß, T2 Paket 7).

``graph/nodes/context_greeting`` merkt sich je Sitzung die begrüßten Seiten
(``entities._greeted_pages``, eine FIFO-Liste — jsonb). Bis Paket 7 galt eine Seite
in JEDER Sprache als begrüßt: nach einem Sprachwechsel blieb der Gruß in der alten
Sprache stehen. Nutzer-Entscheid 2026-10-09: „bei Sprachwechsel passenden
Seitengruß“. Jetzt gehört die Sprache zum Eintrag, und je Seite steht nur die
zuletzt begrüßte Sprache — hin und zurück grüßt also wieder.

Der Eintrag der Vorgabe-Sprache ist die bloße Signatur, wie bisher: laufende
(deutsche) Sitzungen behalten nach dem Deploy ihre Einträge und werden nicht ein
zweites Mal begrüßt.

**Seit Paket 19 (M-8) steht die Signatur nicht mehr im Klartext im Vermerk**: sie
trägt die Adresse fremder Seiten samt Query und Suchbegriffe — so lag 30 Tage der
Browserverlauf der Person in ``sessions.entities``. Vermerkt wird ein HMAC-SHA256 mit
einem Salz je Sitzung (``hmac:…``, Review 19-1: ein bloßer SHA-256 ließe sich für
bekannte Adressen per Wörterbuch umkehren). Das Salz legt der Knoten beim ersten
Vermerk unter ``entities._gruss_salz`` an. Ältere Einträge — Klartext und der
ungesalzene ``sha256:…`` des ersten Stands — gelten weiter (kein zweiter Gruß) und
werden beim nächsten Gruß derselben Seite ersetzt.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from boerdi.i18n import DEFAULT, SUPPORTED, Locale

#: Trenner der Sprache im Eintrag — nur für andere Sprachen als die Vorgabe.
_SPRACHE = "|lang:"


def eintrag(signatur: str, sprache: Locale) -> str:
    """Der Eintrag für ``signatur`` in ``sprache``."""
    return signatur if sprache == DEFAULT else f"{signatur}{_SPRACHE}{sprache}"


def neues_salz() -> str:
    """Ein frisches Salz für eine Sitzung (128 Bit)."""
    return secrets.token_hex(16)


def verdeckt(signatur: str, salz: str) -> str:
    """Die Signatur, wie sie im Vermerk steht: HMAC-SHA256 mit dem Salz der Sitzung."""
    wert = hmac.new(salz.encode("utf-8"), signatur.encode("utf-8"), hashlib.sha256)
    return "hmac:" + wert.hexdigest()


def _formen(signatur: str, salz: str | None) -> list[str]:
    """Jede Form, in der diese Signatur je vermerkt wurde — die aktuelle zuerst."""
    alte = ["sha256:" + hashlib.sha256(signatur.encode("utf-8")).hexdigest(), signatur]
    return [verdeckt(signatur, salz), *alte] if salz else alte


def schon_begruesst(
    begruesst: list[str], signatur: str, sprache: Locale, salz: str | None,
) -> bool:
    """Wurde diese Seite zuletzt in dieser Sprache begrüßt? Ältere Formen zählen mit."""
    return any(eintrag(s, sprache) in begruesst for s in _formen(signatur, salz))


def vermerken(
    begruesst: list[str], signatur: str, sprache: Locale, deckel: int, salz: str,
) -> list[str]:
    """Die Liste nach einem Gruß: andere Sprachen und ältere Formen derselben Seite fallen
    weg, der neue Eintrag kommt ans Ende, gekappt auf die letzten ``deckel``.

    Die Einträge der Seite werden gebildet, nicht zerlegt (Paket 9): die Signatur
    trägt Adresse und Suchbegriff, und steht dort selbst ``|lang:``, schnitt das
    Zerlegen falsch — der Eintrag der alten Sprache blieb stehen."""
    eigene = {eintrag(form, s) for form in _formen(signatur, salz) for s in SUPPORTED}
    neu = [e for e in begruesst if e not in eigene]
    neu.append(eintrag(verdeckt(signatur, salz), sprache))
    return neu[-deckel:]
