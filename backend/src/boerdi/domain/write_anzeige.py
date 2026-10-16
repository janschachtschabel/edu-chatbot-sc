"""Was Menschen von einem Schreibvorgang sehen — Abnahme-Box und Studio.

Aus ``domain/write_confirm`` gelöst (Paket 9, Review Paket 7 — Dateigrößen): dort
steht der Wall um den Schlüssel, hier, was davon angezeigt wird. Beide Helfer
nehmen weg, was nur die Maschine angeht — den Anschluss an den Aufrufer und den
Schlüssel —, und lassen den Rest stehen.
"""

from __future__ import annotations

from typing import Any

from boerdi.domain.write_confirm import TOKEN_PLACEHOLDER

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


def entities_for_display(entities: dict[str, Any]) -> dict[str, Any]:
    """``entities`` für eine Anzeige außerhalb des Zugs (Studio-Sitzungsansicht).

    Der Merkposten bleibt sichtbar — Werkzeug, Argumente, Frist —, nur sein
    Schlüssel weicht :data:`TOKEN_PLACEHOLDER`: er löst eine bestätigte Änderung
    aus und gehört allein dem Vorlauf (Review Paket 2, 2026-10-01). Eine Kopie;
    die Sitzung selbst bleibt unberührt.
    """
    merkposten = entities.get("_pending_write")
    if not isinstance(merkposten, dict) or "token" not in merkposten:
        return entities
    return {**entities, "_pending_write": {**merkposten, "token": TOKEN_PLACEHOLDER}}
