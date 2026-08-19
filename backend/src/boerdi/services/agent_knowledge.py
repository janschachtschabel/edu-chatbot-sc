"""Die interne Wissensdatenbank als Werkzeug der Agent-Schleife (Paket P).

**Der Befund** (gemessen 2026-08-18): ``query_knowledge`` wird ausschliesslich in
``response_tool_selection._select_active_tools`` gebaut und in ``tool_loop``
bedient — beides Muster-Weg. Die Agent-Schleife hatte weder den Vorabruf der
``mode: always``-Bereiche noch das Werkzeug. Im Agent-Modus gab es also **gar
kein** internes Wissen; jede Frage nach WLO, OER oder edu-sharing lief ins
Modellgedaechtnis.

**Die Vorgabe** (Nutzer, 2026-08-18): „immer alle Wissensbereiche, ausser man
spricht explizit einzelne an oder schliesst sie aus."

Drei Entscheidungen, die daraus folgen:

1. **Kein Vorabruf.** Der Muster-Weg holt die ``always``-Bereiche vor dem ersten
   Modellzug. Hier nicht: die Agent-Schleife beantwortet auch „hallo", und eine
   Einbettung ohne Bezug zu WLO zahlte fuer Wissen, das niemand braucht. Das
   Modell ruft, wenn es passt — dafuer ist es die Agent-Schleife.
2. **Alle Bereiche in EINEM Aufruf, und das ist fast gratis.**
   ``get_rag_context`` bettet die Frage einmal ein und durchsucht die Bereiche
   nebenlaeufig; die Punktzahlen sind bereichsuebergreifend vergleichbar (siehe
   dessen Docstring). „Immer alle" kostet also eine Einbettung, nicht neun.
   ``mode`` wird hier nicht gelesen: er trennt im Muster-Weg Vorabruf von Abruf
   auf Zuruf, und ohne Vorabruf gibt es nichts zu trennen.
3. **Je Bereich abwaehlbar** (Q, Nutzer-Auftrag): ``agent: false`` in
   ``rag-config`` nimmt einen Bereich aus DIESER Schleife — die Vorgabe bleibt
   „alle". Der Schalter steht NEBEN ``mode`` und ersetzt ihn nicht: ``mode``
   steuert den Muster-Weg (Vorabruf oder Abruf auf Zuruf), ``agent`` allein die
   Schleife. Wer beides in ein Feld legte, koennte „im Muster vorab, in der
   Schleife gar nicht" nicht mehr ausdruecken.
4. **Eigener Name.** ``wissen_suchen`` und nicht ``query_knowledge``: das
   gleichnamige Muster-Werkzeug nimmt EINEN Bereich als Pflichtfeld. Ein Name
   mit zwei Formen waere die Art von zweiter Wahrheit, an der Dokumentation
   auseinanderlaeuft. Die Wissensbereiche sind dieselben, das Werkzeug ist es
   nicht.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from boerdi.services.rag.retrieval import get_rag_context, get_retrieval_settings

logger = logging.getLogger(__name__)

#: Der Name, an dem die Schleife dieses virtuelle Werkzeug erkennt.
WISSEN_SUCHEN: Final = "wissen_suchen"

#: Deckel fuer das Werkzeug-Ergebnis. Wie im Muster-Weg (``tool_loop``): der
#: Treffertext geht in JEDEN folgenden Modellzug ein, ein langer Fund also
#: vielfach.
MAX_ZEICHEN: Final = 6000

_KOPF: Final = (
    "Durchsuche die interne, redaktionell gepflegte Wissensdatenbank. Nimm sie "
    "fuer Fragen zu WLO und seinem Umfeld: Prozesse, Richtlinien, Qualitaets"
    "sicherung, Lizenzen, Projekte, haeufige Fragen. Sie ist die BESSERE Quelle "
    "als dein Gedaechtnis und als das offene Netz.\n"
    "Ohne Angabe werden ALLE Bereiche zugleich durchsucht — das ist der "
    "Normalfall und kostet nicht mehr als einer. Nenne ``bereiche`` nur, wenn die "
    "Frage eindeutig zu einem gehoert, und ``ohne`` nur, wenn ein Bereich "
    "erkennbar stoert.\n\nBereiche:\n"
)

_FRAGE: Final = (
    "Die Suchanfrage. Formuliere sie als inhaltliche Frage, nicht als Stichwort — "
    "gesucht wird nach Bedeutung, nicht nach Zeichenketten."
)
_BEREICHE: Final = "Nur diese Bereiche durchsuchen. Weglassen = alle."
_OHNE: Final = "Diese Bereiche auslassen. Weglassen = keinen."


def fuer_die_schleife(rag_config: dict[str, Any]) -> list[str]:
    """Die Bereichsnamen, die in Agent und Hybrid ueberhaupt zaehlen (Q).

    Vorgabe ist ALLES; nur ein ausdrueckliches ``agent: false`` nimmt einen
    Bereich heraus. Ein fehlendes Feld heisst „dabei" — sonst haette das
    Nachruesten des Schalters still die Wissensdatenbank abgeschaltet.
    """
    return [name for name, cfg in rag_config.items()
            if (cfg or {}).get("agent", True) is not False]


def wissen_werkzeug(rag_config: dict[str, Any]) -> dict[str, Any] | None:
    """Die Werkzeug-Erklaerung — oder ``None``, wenn keine Bereiche gepflegt sind.

    ``None`` und keine leere Erklaerung: ein Werkzeug ohne durchsuchbaren Bereich
    verspricht Wissen, das es nicht gibt. Das gilt auch, wenn die Bereiche zwar
    da, aber alle abgewaehlt sind.
    """
    namen = fuer_die_schleife(rag_config)
    if not namen:
        return None
    zeilen = []
    for name in namen:
        beschreibung = (rag_config.get(name) or {}).get("description") or ""
        beschreibung = " ".join(str(beschreibung).split())
        zeilen.append(f"- {name}: {beschreibung}" if beschreibung else f"- {name}")
    return {
        "type": "function",
        "function": {
            "name": WISSEN_SUCHEN,
            "description": _KOPF + "\n".join(zeilen),
            "parameters": {
                "type": "object",
                "properties": {
                    "frage": {"type": "string", "description": _FRAGE},
                    "bereiche": {
                        "type": "array",
                        "items": {"type": "string", "enum": namen},
                        "description": _BEREICHE,
                    },
                    "ohne": {
                        "type": "array",
                        "items": {"type": "string", "enum": namen},
                        "description": _OHNE,
                    },
                },
                "required": ["frage"],
            },
        },
    }


def bereiche_aufloesen(args: dict[str, Any], rag_config: dict[str, Any]) -> list[str]:
    """Welche Bereiche dieser Aufruf durchsucht.

    Vorgabe sind alle Bereiche, die :func:`fuer_die_schleife` durchlaesst;
    ``bereiche`` schraenkt ein, ``ohne`` nimmt heraus. Namen, die es nicht gibt
    oder die abgewaehlt sind, werden still verworfen — ein erfundener Bereich darf die
    Suche nicht sprengen, er hat nur nichts beizutragen. Bleibt dabei nichts
    uebrig, ist die Einschraenkung wirkungslos: sonst haette ein Tippfehler
    stillschweigend die Wirkung von „durchsuche nichts".
    """
    alle = fuer_die_schleife(rag_config)
    gewuenscht = [b for b in (args.get("bereiche") or []) if b in alle]
    gewaehlt = gewuenscht or alle
    ohne = {b for b in (args.get("ohne") or []) if b in alle}
    return [b for b in gewaehlt if b not in ohne]


async def antwort(session: Any, args: dict[str, Any], rag_config: dict[str, Any]) -> str:
    """Ein Aufruf des Werkzeugs, als Text fuer die Nachrichtenkette.

    Gibt IMMER einen Text zurueck, nie eine Ausnahme: dieselbe Regel wie beim
    Master-Skill — ein Chat, der wegen einer Wissensquelle nicht antwortet, ist
    schlechter als einer ohne sie. Das Modell erfaehrt den Ausfall im Klartext
    und kann es sagen, statt Erfundenes an die Stelle zu setzen.
    """
    frage = str(args.get("frage") or "").strip()
    if not frage:
        return "Ohne Frage kann ich nicht suchen — nenne, wonach ich sehen soll."
    bereiche = bereiche_aufloesen(args, rag_config)
    if not bereiche:
        return "Keine Wissensbereiche zu durchsuchen."
    einstellungen = get_retrieval_settings()
    try:
        text = await get_rag_context(
            session, frage, areas=bereiche,
            top_k=einstellungen["top_k"],
            min_score=einstellungen["min_score"],
            max_chars_per_area=einstellungen["max_chars_per_area"],
        )
    except Exception as fehler:  # noqa: BLE001 - der Zug laeuft ohne weiter
        logger.warning("wissen_suchen(%d Bereiche): %s", len(bereiche), fehler)
        return ("Die Wissensdatenbank ist gerade nicht erreichbar. Sage das, "
                "statt zu raten.")
    if not text:
        logger.info("wissen_suchen(%d Bereiche): kein Treffer", len(bereiche))
        return f"Keine passende Stelle in {len(bereiche)} durchsuchten Bereichen."
    logger.info("wissen_suchen(%d Bereiche): %d Zeichen", len(bereiche), len(text))
    return text[:MAX_ZEICHEN]
