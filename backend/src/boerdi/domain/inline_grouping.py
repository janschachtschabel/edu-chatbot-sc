"""Was der NUTZER von einem Zug zu sehen bekommt (P5-3-Rest, aus ALT
llm_tool_loop.py's pure layer): die Karten-Zuordnung
(``_is_einzelinhalt_card`` / ``_is_themenseite_card`` / ``_is_pure_sammlung_card``
über :func:`_kartenart`), der Anti-Halluzinations-Fußtext
(``_ui_box_state_footer``), der Auswahl-Deckel (:func:`max_selectable_cards`)
und der Optionszeilen-Stripper (``_strip_trailing_option_lines``).

Was das MODELL zu sehen bekommt, wohnt seit 2026-08-16 nebenan in
``tool_result_redaction`` — eigener Änderungsgrund (die Antwortformen des
MCP-Servers), eigene Datei. Es fragt hier nur die Kasten-Zuordnung ab.

Framework-frei (stdlib + Logger) → ``domain/``.

**Kein reiner ALT-Port mehr** (richtiggestellt 2026-08-16): byte-genau aus ALT
``llm_tool_loop.py`` stammen ``_strip_trailing_option_lines`` und
``_ui_box_state_footer``; ``max_selectable_cards`` (2026-08-14) und
``_kartenart`` (2026-08-16) sind hier entstanden. Bis dahin behauptete dieser
Kopf „verbatim 1:1 / byte-exact" für die ganze Datei — wer daraufhin einen
AST-Abgleich gegen ALT fährt (das Verfahren, mit dem die großen Ports
abgenommen wurden), liest aus dem Ergebnis einen abgedrifteten Port statt zweier
bewusster Ergänzungen.

Erledigt, deshalb nur noch als Notiz: der Tool-Loop-Rumpf, der diese Helfer
konsumiert, ist portiert (``services/tool_loop.py`` +
``services/tool_loop_messages.py``). Und die Zwillings-Kopie der Prädikate aus
ALT ``chat_cards.py`` ist **nicht** wieder entstanden — jene Scheibe landete in
``domain/cards/build.py`` + ``lp_diversity.py`` und greift auf die Zuordnung
hier zurück, wie es der frühere Kopf erbeten hatte.
"""

from __future__ import annotations

import logging as _log

_logger = _log.getLogger(__name__)


def _strip_trailing_option_lines(text: str, quick_replies: list[str]) -> str:
    """Sicherheitsnetz: Entfernt Quick-Reply-/„Bring mich hin"-Optionszeilen,
    die das Modell gelegentlich ZUSÄTZLICH ans Ende des Antworttexts schreibt.

    Diese Optionen gehören ausschließlich ins strukturierte ``quick_replies``-
    Feld (das Frontend rendert sie als Pillen/Buttons UNTER der Antwort) — nicht
    als fetter Text in die Chat-Blase. Es werden nur Zeilen am ENDE entfernt,
    die (nach Abzug von Markdown-Deko) exakt einem Quick-Reply entsprechen oder
    eine „Bring mich hin"-Guide-Zeile sind. Inhaltliche Sätze bleiben unberührt.
    """
    if not text:
        return text

    def _norm(s: str) -> str:
        s = s.strip().lstrip("-–—•*_ \t").rstrip("*_ \t")
        return s.rstrip(":：").strip().lower()

    qr_norm = {_norm(q) for q in (quick_replies or []) if q and q.strip()}
    lines = text.split("\n")
    while lines:
        raw = lines[-1].strip()
        if not raw:
            lines.pop()
            continue
        n = _norm(raw)
        if n and (n in qr_norm or n.startswith("bring mich hin")):
            lines.pop()
            continue
        break
    return "\n".join(lines).rstrip()


# Phasen-Split Teil 2 (P13): die folgenden Helper waren Closures im Rumpf
# von ``generate_response`` und lasen ``_inline_grouping_mode`` aus dem
# umgebenden Scope — jetzt Modul-Funktionen mit explizitem Parameter
# (Call-Sites: Prefetch-Injektion + Tool-Loop).

#: Untergrenze des Auswahl-Deckels. Bis 2026-08-14 stand hier eine harte 5 im
#: Tool-Loop; weniger als das wäre eine Verschlechterung gegenüber dem Bestand.
MIN_SELECTABLE_CARDS = 5
#: Obergrenze. Die Gruppen-Deckel dürfen bis 20/20/8 gehen (``config_loader/
#: widget.py``); ihre Summe als Auswahl-Budget wäre eine Antwort mit 48 Karten.
MAX_SELECTABLE_CARDS = 20


def max_selectable_cards(display_rules: dict) -> int:
    """Wie viele Karten ``select_top_cards`` höchstens wählen darf.

    Der Deckel folgt den Studio-Gruppen (``display_rules.groups``), statt eine
    eigene Zahl zu führen. Grund (Befund 2026-08-14): der Tool-Loop kappte die
    LLM-Auswahl hart auf 5 Karten über ALLE Boxen hinweg, und
    ``_apply_widget_modes_postprocess`` filtert die Karten anschließend auf
    genau diese IDs. Die Box-Deckel in ``turn_persist`` greifen erst danach —
    sie konnten also nur noch kürzen, nie ergänzen. Belegten Einzelinhalte die
    fünf Plätze, verschwand die gesuchte Sammlung, auch bei exaktem
    Titeltreffer: gemessen an „Optik", das der MCP als Treffer 1 liefert.

    Die Summe ist bewusst großzügig — sie ist ein *Budget*, keine Vorgabe. Was
    am Ende steht, entscheiden weiterhin die Box-Deckel; dieser Wert sorgt nur
    dafür, dass für jede Box überhaupt etwas übrig bleiben KANN.

    Die Materialien-Box zählt mit ihrem *größeren* Deckel: ``turn_persist``
    nimmt im Lernpfad-Zug ``materialien_max_lernpfad`` (Vorgabe 5) statt
    ``materialien_max`` (3) — zwei Alternativen für dieselbe Box, nicht zwei
    Boxen. Ein Budget, das nur die kleinere Zahl kennt, hungerte im M09-Zug
    genau die Sammlung aus, um die es hier geht.
    """
    grp = display_rules.get("groups") or {}

    def _wert(key: str, vorgabe: int) -> int:
        try:
            return max(0, int(grp.get(key) or vorgabe))
        except (TypeError, ValueError):
            return vorgabe

    summe = (_wert("themenseiten_max", 3)
             + _wert("sammlungen_max", 3)
             + max(_wert("materialien_max", 3),
                   _wert("materialien_max_lernpfad", 5)))
    return max(MIN_SELECTABLE_CARDS, min(MAX_SELECTABLE_CARDS, summe))


def _kartenart(c: dict) -> str:
    """``"topic_page"`` | ``"collection"`` | ``"content"`` — der Kasten, in dem
    diese Karte landen wird.

    **Spiegelt ``domain.cards.normalize._infer_node_type``, nicht die
    Frontend-Prädikate** — und das ist der Punkt: die drei Prädikate hier laufen
    auf NOCH NICHT normalisierten Karten, das Frontend sieht die normalisierten.
    Wer hier die Frontend-Bedingung nachbaut, misst eine Stufe zu früh.

    Konkret unterschied sich die bisherige Hand-Kopie in ``topic_page_url``: der
    Envelope-Leser setzt bei ``search_wlo_all`` genau dieses Feld und KEIN
    Varianten-Array. Gemessen am Optik-Zug (2026-08-16) meldete der Fußtext
    deshalb „0 Themenseite(n) sichtbar, 4 Sammlung(en)", während das Frontend
    2 und 2 rendert.

    Von Hand nachgebaut statt importiert, weil dieses Modul zur Importzeit
    abhängigkeitsfrei bleibt (Kopfkommentar) und ``normalize`` den
    ``config_loader`` mitbringt. Ändert sich ``_infer_node_type``, gehört diese
    Funktion mit — dafür steht sie als EINE Stelle statt als drei.
    """
    nt = (c.get("node_type") or "").strip().lower()
    if (nt == "topic_page"
            or c.get("topic_pages")
            or str(c.get("topic_page_url") or "").strip()):
        return "topic_page"
    if nt == "collection":
        return "collection"
    return "content"


def _is_einzelinhalt_card(c: dict) -> bool:
    """True wenn die Card im Frontend als Einzelinhalt rendert (also NICHT
    in den sichtbaren Boxen erscheint, nur über die Such-CTA erreichbar ist)."""
    return _kartenart(c) == "content"


def _is_themenseite_card(c: dict) -> bool:
    """True wenn die Card in den Themenseiten-Kasten läuft."""
    return _kartenart(c) == "topic_page"


def _is_pure_sammlung_card(c: dict) -> bool:
    """True wenn die Card eine Sammlung OHNE kuratierte Themenseite ist."""
    return _kartenart(c) == "collection"


def _ui_box_state_footer(cards: list[dict], _inline_grouping_mode: bool) -> str:
    """Strukturierte Beschreibung dessen, was der User NACH diesem Tool-
    Call in den Result-Group-Boxen tatsächlich sieht. Wird im
    inline_grouping_mode an JEDE Tool-Result-Message angehängt, damit
    die LLM bei der Text-Generation **nur über tatsächlich Sichtbares**
    spricht (Anti-Hallucination, vgl. User-Feedback 2026-05-21:
    Bot kündigte „zwei Sammlungen" an, UI zeigte keine).

    Nicht für Card-Aufzählung — nur Counts pro Box-Typ. Reihenfolge
    entspricht der Render-Reihenfolge im Chat (Themenseiten >
    Sammlungen > Webseiten-Inhalte > Such-CTA)."""
    if not _inline_grouping_mode:
        return ""
    n_topic = sum(1 for c in cards if _is_themenseite_card(c))
    n_coll = sum(1 for c in cards if _is_pure_sammlung_card(c))
    n_content = sum(1 for c in cards if _is_einzelinhalt_card(c))
    return (
        "\n\n[UI-BOX-STATUS nach diesem Tool-Call — gilt fuer deinen "
        "Antwort-Text]: "
        f"{n_topic} Themenseite(n) sichtbar, "
        f"{n_coll} Sammlung(en) sichtbar, "
        f"{n_content} Einzelinhalt(e) NICHT sichtbar (nur via Such-CTA "
        "zur externen Suche erreichbar). "
        "WAHRHEITSPFLICHT: Sprich im Text nur ueber die sichtbaren "
        "Boxen UND verweise auf die Such-CTA, wenn der User nach "
        "Einzelinhalten / Material-Typen gefragt hat. NIEMALS "
        "Sammlungen/Themenseiten erfinden, die der UI-Status nicht "
        "zeigt — das ist eine Halluzination."
    )
