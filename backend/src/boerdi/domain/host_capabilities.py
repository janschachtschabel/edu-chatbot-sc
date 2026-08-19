"""Was die einbettende Anwendung ANZEIGT und ERLAUBT — als Prompt-Block (O-C).

Rein und ohne Seiteneffekte: eine Zeichenkette aus zwei Angaben. Beide
Prompt-Wege koennen sie einsetzen, ohne dass jemand die Logik zweimal schreibt.

**Nur was ABWEICHT, wird gesagt.** Die Vorgabe (Gliederung an, alle Werkzeuge)
erzeugt KEINEN Block: ein Satz, der den Normalfall beschreibt, kostet in jedem
Zug Token und sagt nichts.

**Eine Behauptung, die dieser Entwurf zunaechst enthielt, ist falsch** und steht
hier als Warnung, damit sie nicht zurueckkehrt: „die Anwendung zeigt keine
Ergebnis-Kacheln". Gemessen am Widget (``chat-shell.component.html``) sind die
beiden Zweige ``!cardsVisible`` und ``cardsVisible`` vollstaendig und schliessen
einander aus — Treffer erscheinen IMMER, entweder als Kacheln mit Vorschaubild
oder als Textlinks in Boxen. ``show-cards`` waehlt zwischen diesen beiden
Darstellungen; es schaltet nichts ab. Deshalb gibt es hier auch keinen
``show_cards``-Eingang: er koennte nur eine Lage beschreiben, die es im Produkt
nicht gibt. Sollte je eine echte Unterdrueckung dazukommen (ALTs
``cards-enabled``), kommt der Eingang mit ihr zurueck.

Was ``inline-result-grouping="false"`` dagegen WIRKLICH aendert, steht in
``grouping/result-grouping.displayContent``: ohne Gruppierung bleiben die
Aufzaehlungs-Links im Antworttext stehen, statt in die Boxen zu wandern — der
Leser saehe dieselben Treffer zweimal.
"""

from __future__ import annotations

from typing import Final

#: Die drei benannten Werkzeug-Modi. Benannt und nicht als freie Liste, weil eine
#: Umbenennung im MCP sonst still die Rechte einer Einbettung aendern wuerde.
LESEND: Final = "read-only"
KURATIEREND: Final = "curate"
VOLL: Final = "full"
MODI: Final = frozenset({LESEND, KURATIEREND, VOLL})

#: Die Ueberschrift des Blocks. Oeffentlich, damit ein Test sie pruefen kann,
#: ohne die Formulierung abzuschreiben.
KOPF: Final = "## Diese Anwendung"

#: Die Ausnahmen vom Praefix-Test: ``wlo_*``-Namen, die NICHTS aendern.
#:
#: Der Praefix-Test unten liest ``wlo_`` als „schreibend" — das stimmt fuer den
#: ganzen Kuratier-Katalog, aber zwei lesende Werkzeuge tragen dasselbe Praefix.
#: Ohne diese Liste fiele in ``read-only`` die Frage „ist die Person angemeldet?"
#: weg, und das Modell muesste raten, statt es sagen zu koennen.
#: Ein Waechter haelt die Liste an den echten Katalogen fest
#: (``test_host_capabilities.TestLesendeWloWerkzeuge``).
LESENDE_WLO_WERKZEUGE: Final = frozenset({"wlo_auth_status", "wlo_health_check"})

_OHNE_GLIEDERUNG: Final = (
    "Diese Anwendung gruppiert Treffer NICHT in Boxen (Themenseiten, Sammlungen, "
    "Materialien) und entfernt auch keine Link-Aufzaehlung aus deinem Text. "
    "Schreibe eine noetige Gliederung selbst — und zaehle die Treffer nicht "
    "zusaetzlich als Linkliste auf, sie stehen bereits unter deiner Antwort."
)
_NUR_LESEN: Final = (
    "Du kannst in dieser Anwendung NICHTS aendern: schreibende Werkzeuge stehen "
    "dir nicht zur Verfuegung. Sag es, wenn jemand eine Aenderung will, statt sie "
    "zu versprechen."
)
_KURATIEREND: Final = (
    "Kuratieren ist erlaubt (anlegen, aendern, einsortieren) — zweistufig wie "
    "immer: erst Vorschau, dann das Ja der Person. Nachschlagen ausserhalb von WLO "
    "(Wikipedia, fremde Adressen) steht dir hier NICHT zur Verfuegung."
)


def prompt_block(
    *,
    inline_result_grouping: bool | None = None,
    tool_mode: str | None = None,
) -> str:
    """Der Block — oder ``""``, wenn alles auf Vorgabe steht.

    ``None`` heisst jeweils „die Anwendung sagt nichts" und gilt als Vorgabe.
    """
    saetze: list[str] = []
    if inline_result_grouping is False:
        saetze.append(_OHNE_GLIEDERUNG)
    modus = (tool_mode or "").strip().lower()
    if modus == LESEND:
        saetze.append(_NUR_LESEN)
    elif modus == KURATIEREND:
        saetze.append(_KURATIEREND)
    if not saetze:
        return ""
    return f"{KOPF}\n" + "\n".join(saetze)


def erlaubt(werkzeugname: str, tool_mode: str | None) -> bool:
    """Darf dieses MCP-Werkzeug in diesem Modus benutzt werden?

    Die Zuordnung haengt am NAMENSPRAEFIX, nicht an einer gepflegten Liste: neue
    schreibende Werkzeuge heissen ``wlo_*`` (Bestand, 2026-08), neue lesende
    ``search_*``/``get_*``/``lookup_*``/``browse_*``. Eine Liste haette bei jedem
    neuen Werkzeug still zu wenig oder zu viel erlaubt.

    **Zwei benannte Ausnahmen** (:data:`LESENDE_WLO_WERKZEUGE`): das Praefix ist
    die Regel, nicht das Gesetz — ``wlo_auth_status`` und ``wlo_health_check``
    tragen es, ohne etwas zu aendern. Die Ausnahme steht als Liste da, weil sie
    endlich und pruefbar ist; die Regel bleibt der Praefix, weil sie mitwaechst.
    """
    modus = (tool_mode or "").strip().lower()
    if modus not in MODI or modus == VOLL:
        return True
    schreibend = (werkzeugname.startswith("wlo_")
                  and werkzeugname not in LESENDE_WLO_WERKZEUGE)
    ausserhalb = werkzeugname in {"get_wikipedia_summary", "get_url_text"}
    if modus == LESEND:
        return not schreibend
    return not ausserhalb  # curate: alles ausser dem Blick nach draussen
