"""Was Menschen von einem Schreibvorgang sehen — Abnahme-Box und Studio.

Aus ``domain/write_confirm`` gelöst (Paket 9, Review Paket 7 — Dateigrößen): dort
steht der Wall um den Schlüssel, hier, was davon angezeigt wird. Beide Helfer
nehmen weg, was nur die Maschine angeht — den Anschluss an den Aufrufer und den
Schlüssel —, und lassen den Rest stehen.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from boerdi.domain.write_confirm import (
    OFFENER_PLAN_KEY,
    TOKEN_PLACEHOLDER,
    redact_confirm_token,
)

#: Schlüssel der Vorschau-Kopie im Merkposten (Paket 19, Review 19-5) und ihr Deckel.
VORSCHAU_KOPIE = "vorschau"
_KOPIE_ZEICHEN = 4000

# Der Anschluss, ab dem die Vorschau nur noch den Aufrufer angeht: „ Dazu
# denselben Aufruf mit confirmToken: … wiederholen.\nDer Schlüssel gilt …"
# (``previewReply``). Gesucht wird die Stelle, nicht ein Muster — warum das
# LETZTE Vorkommen zählt, steht bei :func:`preview_for_display`.
_DISPLAY_TAIL_MARKER = "Dazu denselben Aufruf mit confirmToken:"


def preview_for_display(text: str) -> str:
    """Der Vorschautext ohne den Teil, der nur die Maschine angeht (S2).

    Der Server schließt jede Vorschau mit zwei Sätzen an den *Aufrufer*: wie
    der Aufruf zu wiederholen ist und wie lange der Schlüssel gilt. In einer
    Box, die eine Lehrkraft um Zustimmung bittet, ist das Rauschen — und der
    Satz vor ihnen (``Die Sammlung wird angelegt.``) gehört sehr wohl dazu.
    Geschnitten wird deshalb genau am Anschluss, nicht am Satzanfang.

    Dies liest deutschen Servertext, hängt also an dessen Wortlaut. Ändert der
    ihn, findet die Funktion den Anschluss nicht mehr — dann steht zu VIEL in
    der Box, nie zu wenig. Diese Richtung ist Absicht: eine Abnahme über einem
    gekürzten Unterschied wäre der Fehler, den die Box gerade verhindern soll.

    **Geschnitten wird am LETZTEN Anschluss** (2026-08-15, live gemessen). Der
    Server gibt Titel und Beschreibung des Vorhabens wörtlich in die Vorschau
    und hängt seinen Block danach an; bringt einer dieser Werte den Satz mit,
    steht er zweimal im Text. Am ersten zu schneiden hiesse mitten in einen
    Wert des Vorhabens zu schneiden — und damit genau die Richtung zu
    verletzen, die der Absatz darüber zusichert. Bei
    ``wlo_create_collection`` schreibt die Person diesen Wert selbst; bei
    ``wlo_update_content`` zeigt die Vorschau die **alten** Werte des Knotens,
    die jemand anderes geschrieben haben kann. Dieselbe Wurzel trifft
    :func:`extract_confirm_token`, dort mit anderer Folge.
    """
    stelle = (text or "").rfind(_DISPLAY_TAIL_MARKER)
    if stelle < 0:
        return (text or "").rstrip()
    return text[:stelle].rstrip()


#: Deckel für den Titel in :func:`ziel_zeile` — ihn hat jemand anderes geschrieben.
_TITEL_ZEICHEN = 120


#: Was als Kennung in die Zeile darf: Buchstaben, Ziffern, Bindestrich (eine nodeId).
_KENNUNG = re.compile(r"[0-9A-Za-z-]{8,64}")
#: Anführungszeichen, die im Titel die Klammer der Zeile vorzeitig schlössen.
_ANFUEHRUNG = str.maketrans({z: "'" for z in "„“”\"«»"})


def _einzeilig(wert: object) -> str:
    """Fremdtext als eine Zeile ohne Steuer- und Formatzeichen — sonst ``""``."""
    if not isinstance(wert, str):
        return ""
    # Formatzeichen (weiches Trennzeichen, Breitenlose) fallen weg, statt Wörter zu trennen.
    ohne = "".join(z for z in wert if unicodedata.category(z) != "Cf")
    return " ".join("".join(z if z.isprintable() else " " for z in ohne).split())


def _titel_fuer_die_zeile(titel: str) -> str:
    """Der Titel so, dass er die Zeile nicht umdeuten kann: keine schließenden
    Anführungszeichen, kein klickbarer Markdown-Link, gedeckelt."""
    sicher = titel.translate(_ANFUEHRUNG).replace("](", "] (")
    if len(sicher) <= _TITEL_ZEICHEN:
        return sicher
    return sicher[:_TITEL_ZEICHEN - 1].rstrip() + "…"


def ziel_zeile(bestaetigung: object, text: str) -> str | None:
    """Die Zeile, die sagt, WAS sich ändert — ``Geändert wird (Kennung): „Titel“`` — oder ``None``.

    Der Vorschautext des Servers besteht bei einer Metadaten-Änderung nur aus den Feldzeilen
    (``Fach: „…“ → „…“``): weder Titel noch Kennung. Beides steht im strukturierten Teil
    (``confirm.preview.target``). Ohne die Zeile sähe vor dem Ja niemand, woran sich etwas
    ändert, sobald die KI den Datensatz nicht vorher gelesen hat (Review 2026-11-13, M1).

    * Keine Zeile, wenn der Server das Ziel selbst benennt — in seiner Form ``„Titel“
      (Kennung)`` (Einreichen, Vorschlagen, Entscheiden). Der Titel irgendwo im Text genügt
      nicht: als Feldwert oder Schlagwort benennt er nichts (zweites Review, M-1).
    * Keine Zeile beim Löschen (der Server schreibt ``Löscht: …``) und ohne Titel (Anlegen:
      den Datensatz gibt es noch nicht).
    * Die Kennung steht VOR dem Titel und muss wie eine aussehen; der Titel ist Fremdtext und
      könnte sonst eine falsche Kennung vortäuschen.
    * „Datensatz“ oder „Sammlung“ sagt die Zeile nicht: der Server meldet eine Sammlung, die
      über ``wlo_update_content`` geändert wird, als ``content``.

    Der Wortlaut ist deutsch wie der Servertext, vor dem er steht.
    """
    if not isinstance(bestaetigung, dict):
        return None
    vorschau = bestaetigung.get("preview")
    if not isinstance(vorschau, dict) or vorschau.get("action") != "change":
        return None
    ziel = vorschau.get("target")
    if not isinstance(ziel, dict):
        return None
    titel, kennung = _einzeilig(ziel.get("title")), ziel.get("nodeId")
    if not titel or not isinstance(kennung, str) or not _KENNUNG.fullmatch(kennung):
        return None
    if f"„{titel}“ ({kennung})" in (text or ""):
        return None
    return f"Geändert wird ({kennung}): „{_titel_fuer_die_zeile(titel)}“"


def merke_vorschau(merkposten: dict[str, Any], vorschau: str) -> dict[str, Any]:
    """Eine Kopie der gezeigten Vorschau in den Merkposten legen (Paket 19, Review 19-5).

    Die Box selbst lebt nur einen Zug (``session_state["_write_preview"]``, S2). Konnte die
    Zustimmungsprüfung im Folgezug nicht urteilen, zeigt der Vorlauf sie aus dieser Kopie
    erneut — der Bestätigungs-Chip meint dann sichtbar genau das. Ohne Schlüssel, ohne den
    Anschluss an den Aufrufer, gedeckelt. Gibt ``merkposten`` zurück."""
    merkposten[VORSCHAU_KOPIE] = preview_for_display(
        redact_confirm_token(vorschau or ""))[:_KOPIE_ZEICHEN]
    return merkposten


def entities_for_display(entities: dict[str, Any]) -> dict[str, Any]:
    """``entities`` für eine Anzeige außerhalb des Zugs (Studio-Sitzungsansicht).

    Der Merkposten bleibt sichtbar — Werkzeug, Argumente, Frist —, nur sein
    Schlüssel weicht :data:`TOKEN_PLACEHOLDER`: er löst eine bestätigte Änderung
    aus und gehört allein dem Vorlauf (Review Paket 2, 2026-10-01). Eine Kopie;
    die Sitzung selbst bleibt unberührt.
    """
    gezeigt = dict(entities)
    # Paket M5 (Review, Befund 6): der Fortsetzungs-Schlüssel eines Plans schreibt ebenso.
    for schluessel in ("_pending_write", OFFENER_PLAN_KEY):
        merkposten = gezeigt.get(schluessel)
        if isinstance(merkposten, dict) and "token" in merkposten:
            gezeigt[schluessel] = {**merkposten, "token": TOKEN_PLACEHOLDER}
    return gezeigt
