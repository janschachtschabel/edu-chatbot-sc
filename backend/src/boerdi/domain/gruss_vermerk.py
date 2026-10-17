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
"""

from __future__ import annotations

from boerdi.i18n import DEFAULT, SUPPORTED, Locale

#: Trenner der Sprache im Eintrag — nur für andere Sprachen als die Vorgabe.
_SPRACHE = "|lang:"


def eintrag(signatur: str, sprache: Locale) -> str:
    """Der Eintrag für ``signatur`` in ``sprache``."""
    return signatur if sprache == DEFAULT else f"{signatur}{_SPRACHE}{sprache}"


def schon_begruesst(begruesst: list[str], signatur: str, sprache: Locale) -> bool:
    """Wurde diese Seite zuletzt in dieser Sprache begrüßt?"""
    return eintrag(signatur, sprache) in begruesst


def vermerken(begruesst: list[str], signatur: str, sprache: Locale, deckel: int) -> list[str]:
    """Die Liste nach einem Gruß: andere Sprachen derselben Seite fallen weg, der
    neue Eintrag kommt ans Ende, gekappt auf die letzten ``deckel``.

    Die Einträge der Seite werden gebildet, nicht zerlegt (Paket 9): die Signatur
    trägt Adresse und Suchbegriff, und steht dort selbst ``|lang:``, schnitt das
    Zerlegen falsch — der Eintrag der alten Sprache blieb stehen."""
    eigene = {eintrag(signatur, s) for s in SUPPORTED}
    neu = [e for e in begruesst if e not in eigene]
    neu.append(eintrag(signatur, sprache))
    return neu[-deckel:]
