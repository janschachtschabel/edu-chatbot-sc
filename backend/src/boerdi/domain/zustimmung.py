"""Die Zustimmung des Menschen zu einer offenen Abnahme (S4, 2026-08-14).

Aus ``domain/write_confirm`` gelöst (Paket 9, Review Paket 7 — Dateigrößen): dort
steht der Wall um den Schlüssel, hier die Frage, ob eine Nachricht eine Abnahme
ist. Ob ein Zug eine Abnahme ist oder eine Nachbesserung, steht **nicht in den
Argumenten des Modells** — beide Male ruft es dasselbe Werkzeug mit ähnlichen
Werten. Es steht in der Nachricht des Menschen.
"""

from __future__ import annotations

import re

# Stämme, die eine Abnahme tragen. Umlaute sind aufgelöst, weil ``_woerter``
# vor dem Vergleich normalisiert. Die beiden Knopf-Beschriftungen aus
# ``i18n/bot_text`` („Ja, so ausführen" / „Yes, go ahead") fallen bewusst unter
# diese Stämme — dann braucht dieses Modul keine Sprachkenntnis und keinen
# Parameter. Ein Test klemmt genau das fest: wer den Knopf umbenennt, ohne
# einen Stamm zu treffen, bekommt einen roten Test und keine stille Schleife.
_ZUSTIMMUNG = frozenset({
    "ja", "jawohl", "bestatige", "bestatigen", "bestatigt", "bestatigung",
    "ausfuhren", "ausfuhrung", "abnehmen", "ok", "okay", "passt", "einverstanden",
    # Paket 7 (K1, Nutzer 2026-10-09): Gatekeeper-Skills fragen nach „Freigabe“.
    # Ganze Wörter wie alle hier — „frei“ allein zählt nicht.
    "freigabe", "freigeben", "freigegeben", "freigebe",
    "yes", "confirm", "confirmed", "ahead", "proceed",
})

# Was daneben stehen darf (Review Paket 9, MAJOR 2). Bis dahin zählte jeder kurze
# Satz mit einem Zustimmungs-Wort, solange keines aus einer Liste von Verneinungen,
# Vorbehalten und Ablehnungen darin stand — und die wurde nie vollständig:
# „Freigabe aufgehoben“, „ok, vergiss es“ und „yes but use another title“ führten
# den Schreibvorgang aus. Seither gehört JEDES Wort zur Zustimmung oder hierher.
# Alles andere kostet eine zweite Frage — auch die Nachbesserung „ja, aber ändere
# den Titel“, die die alte Nutzlast gerade NICHT ausführen darf.
#
# Hier steht nichts, das verneint, aufschiebt oder allein „nein danke“ heißen kann:
# kein „danke“, kein „alles (gut)“, kein „gleich“, kein „mal“.
_BEIWORT = frozenset({
    "bitte", "gern", "gerne", "so", "genau", "klar", "gut", "super", "prima", "perfekt",
    "ich", "es", "das", "die", "der", "den", "ist", "und", "dann", "jetzt", "sofort",
    "direkt", "hiermit", "los", "weiter",
    # Die Freigabe erteilen, das Vorhaben ausführen.
    "mach", "mache", "machen", "gebe", "erteile", "erteilt", "speichern", "hinzufugen",
    "erstellen", "eintragen", "durchfuhren", "hochladen",
    # „Zum <Verb> bitte bestätigen.“ — so endet jede Vorschau des MCP-Servers, und
    # Skills geben den Satz zum Abtippen vor. Ohne „ablehnen“: dort ist das Wort
    # Vorgang und Absage zugleich, die Zustimmung trägt dann der Knopf.
    "zum", "anlegen", "ubernehmen", "aufnehmen", "herausnehmen", "entfernen",
    "annehmen", "hinterlegen", "umstellen",
    "please", "sure", "go", "do", "it", "i", "and", "then", "now", "that", "this",
    "fine", "good", "great", "perfect", "save", "create", "add", "apply",
})

# Eine Rückfrage ist keine Abnahme (Review Paket 7, A-3): „Welche Freigabe?“ trägt
# einen Zustimmungs-Stamm und hätte den offenen Vorgang ausgeführt. Fragewörter
# stehen in keiner der beiden Listen; das Zeichen braucht eine eigene Prüfung, denn
# „ja?“ besteht sonst nur aus Zustimmung.
_FRAGEZEICHEN = ("?", "？")

# Eine Abnahme ist kurz. Der Deckel haelt lange Saetze heraus, in denen ein
# „ja" nur beilaeufig vorkommt.
_WORTGRENZE = 6

_WORTTRENNER = re.compile(r"[^0-9a-z]+")
_UMLAUTE = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "s"})


def _woerter(text: str) -> list[str]:
    """``text`` als Wortliste, kleingeschrieben und ohne Umlaute."""
    flach = (text or "").lower().translate(_UMLAUTE)
    return [w for w in _WORTTRENNER.split(flach) if w]


# Das Veto (Paket 10, A-6): was eine Absage, einen Aufschub oder eine Änderung
# trägt, führt nie aus — auch wenn die LLM-Prüfung danach „zustimmung“ sagte.
# Nur Eindeutiges: ein Veto zu viel schneidet der Person den Weg über die LLM-Prüfung
# ab (dann bleibt ihr der Knopf). Ganze Wörter …
_VETO_WORT = frozenset({
    "nein", "nee", "ne", "no", "nicht", "nichts", "nie", "niemals", "nix", "stopp", "stop",
    "warte", "warten", "spater", "spaeter", "vergiss",
    "not", "nope", "nah", "never", "dont", "don", "wait", "later", "abort", "hold",
    "nevermind", "instead", "change",
})
# … und Wortanfänge (nach ``_woerter``: klein, ohne Umlaute).
_VETO_STAMM = (
    "kein", "abbrech", "abbruch", "abgebroch", "verweiger", "ablehn", "abgelehn", "widerruf",
    "storn", "absag", "abgesag", "aufheb", "aufgehob", "zuruckzieh", "zuruckgezog",
    "zuruckweis", "zuruckgewies", "vergess", "ander", "statt", "cancel",
)


def hat_veto(text: str) -> bool:
    """Trägt ``text`` eine Absage, Rückfrage oder Änderung? Dann gilt er nie als Zustimmung."""
    if any(z in (text or "") for z in _FRAGEZEICHEN):
        return True
    return any(w in _VETO_WORT or w.startswith(_VETO_STAMM) for w in _woerter(text))


def is_affirmation(text: str) -> bool:
    """Ist ``text`` eine glatte Zustimmung zu einer offenen Abnahme?

    Bewusst eng: jedes Wort gehoert zur Zustimmung oder ist ein harmloses
    Beiwort, und der Satz ist kurz. Der Preis einer zu engen Regel ist eine
    ueberfluessige zweite Frage, der Preis einer zu weiten eine Aenderung, der
    niemand zugestimmt hat.
    """
    woerter = _woerter(text)
    if not woerter or len(woerter) > _WORTGRENZE:
        return False
    if any(z in (text or "") for z in _FRAGEZEICHEN):
        return False
    if any(w not in _ZUSTIMMUNG and w not in _BEIWORT for w in woerter):
        return False
    return any(w in _ZUSTIMMUNG for w in woerter)
