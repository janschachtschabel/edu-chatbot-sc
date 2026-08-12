"""Bestätigungs-Wall vor den kuratierenden MCP-Werkzeugen (E1).

Jedes schreibende Werkzeug des WLO-MCP-Servers ist zweistufig: ohne
``confirmToken`` schreibt es nichts, sondern liefert die Vorschau der Änderung
plus einen Schlüssel; erst ein zweiter Aufruf mit diesem Schlüssel führt aus.
Der Schlüssel ist an den Fingerabdruck der Änderung gebunden, gilt zehn Minuten
und genau einmal (``services/write/confirm.ts`` des Servers).

**Was diese Bindung leistet und was nicht.** Sie verhindert, dass eine
genehmigte Änderung gegen eine andere eingetauscht wird — der Server nennt genau
diesen Angriff. Sie verhindert *nicht*, dass derselbe Aufrufer beide Schritte
macht. Der Server nimmt an, zwischen Vorschau und Bestätigung stehe ein Mensch.
Bei einem Chat-Client, dessen Werkzeugschleife fünf Iterationen pro Zug fährt,
steht dort niemand: das Modell könnte die Vorschau holen, den Schlüssel aus der
eigenen Nachrichtenkette lesen und im selben Zug bestätigen.

**Der Wall setzt den Menschen wieder ein, an der einzigen Stelle, an der er im
Chat sicher steht: am Zugwechsel.** Zwei Regeln tragen ihn:

1. *Das Modell sieht den Schlüssel nie und setzt ihn nie.* Ein mitgeschickter
   ``confirmToken`` wird entfernt (:func:`strip_confirm_token`), und der
   Schlüssel wird aus dem Vorschautext geschnitten, bevor dieser in die
   Nachrichtenkette geht (:func:`redact_confirm_token`).
2. *Eingesetzt wird er nur von uns, nur für dasselbe Vorhaben, nur in einem
   späteren Zug.* Die ersten beiden Bedingungen prüft :func:`token_for`; die
   dritte kann dieses Modul nicht prüfen, weil es keinen Zugbegriff hat — sie
   liegt in der Naht (``services/tool_loop.py``), die den offenen Vorgang als
   **Schnappschuss beim Zug-Eintritt** liest. Ein in diesem Zug entstandener
   Vorgang steht nicht im Schnappschuss und ist damit in diesem Zug nicht
   bestätigbar.

Die Trennung ist Absicht: hier wohnt die *Identität eines Vorhabens*, dort die
*Zeit*. Wer die Zug-Regel sucht, findet sie an der Naht und nicht hier.

**Welche der beiden Regeln trägt.** Regel 1 zerfällt in zwei Hälften, und sie
sind ungleich wichtig. Das Entfernen auf dem **Hinweg** ist die Zusicherung: was
das Modell nicht absetzen kann, kann es nicht auslösen — das gilt unabhängig
davon, was es gesehen hat. Das Herausschneiden auf dem **Rückweg** ist
Tiefenstaffelung: es hält den Schlüssel aus Nachrichtenkette und Protokoll
heraus. Änderte der Server seinen Vorschautext so, dass
:func:`extract_confirm_token` ihn nicht mehr fände, wäre die Folge daher **kein
Loch, sondern ein Ausfall**: es ließe sich nichts mehr bestätigen. Die Naht
protokolliert diesen Fall, damit er nicht still bleibt.

**Was hier bewusst nicht nachgebaut wird:** die eigentliche Absicherung — dass
ein Schlüssel genau eine Änderung an genau einem Knoten autorisiert — leistet
der Server über den Fingerabdruck des aufgelösten ChangeSet. Ein zweiter
Mechanismus auf unserer Seite wäre Verdopplung mit eigener Driftgefahr.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Die kuratierende Oberfläche des Servers, gemessen 2026-08-10 an ``tools/list``.
# ``wlo_health_check``/``wlo_auth_status`` gehören NICHT dazu — sie sind
# Betriebs-Sonden und ändern nichts.
CURATION_TOOLS = frozenset({
    "wlo_create_content",
    "wlo_update_content",
    "wlo_delete_content",
    "wlo_submit_content",
    "wlo_create_collection",
    "wlo_rename_collection",
    "wlo_delete_collection",
    "wlo_add_to_collection",
    "wlo_remove_from_collection",
    "wlo_update_compendium",
    "wlo_set_topic_page",
    "wlo_suggest_metadata",
    "wlo_list_suggestions",
    "wlo_decide_suggestion",
})

# 13 der 14 führen einen ``confirmToken``. ``wlo_list_suggestions`` nicht — es
# listet vorhandene Vorschläge auf und ändert nichts; live am Eingabeschema
# geprüft, nicht angenommen.
CONFIRMABLE_TOOLS = CURATION_TOOLS - {"wlo_list_suggestions"}

_TOKEN_FIELD = "confirmToken"

# Der Server schreibt ``… mit confirmToken: <schlüssel> wiederholen.``
# (``previewReply`` in ``curation-shared.ts``). Der Schlüssel ist
# ``randomBytes(18).toString('base64url')``, also 24 Zeichen aus dem
# base64url-Alphabet.
_TOKEN_IN_TEXT = re.compile(rf"({_TOKEN_FIELD}:\s*)([A-Za-z0-9_-]{{16,}})")

TOKEN_PLACEHOLDER = "‹wird bei der Bestätigung eingesetzt›"

# Wie lange ein Schlüssel gilt — die Frist des Servers
# (``services/write/confirm.ts``), hier ein zweites Mal geprüft, damit ein
# sicher toter Schlüssel gar nicht erst abgesetzt wird (E4). Länger wäre
# nutzlos, kürzer verwürfe gültige Schlüssel.
TOKEN_TTL_SECONDS = 600

# Der Anschluss, ab dem die Vorschau nur noch den Aufrufer angeht: „ Dazu
# denselben Aufruf mit confirmToken: … wiederholen.\nDer Schlüssel gilt …"
# (``previewReply``). Ab dem führenden Leerzeichen, damit der Satz davor —
# was passieren würde — vollständig stehen bleibt.
_DISPLAY_TAIL = re.compile(r"\s*Dazu denselben Aufruf mit confirmToken:.*\Z", re.S)


def is_curation_tool(tool_name: str) -> bool:
    """Gehört ``tool_name`` zur kuratierenden Oberfläche?"""
    return tool_name in CURATION_TOOLS


def is_confirmable(tool_name: str) -> bool:
    """Führt ``tool_name`` einen ``confirmToken``, ist also zweistufig?"""
    return tool_name in CONFIRMABLE_TOOLS


def strip_confirm_token(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """``args`` ohne einen vom Modell gesetzten Schlüssel.

    Ein Modell, das sich einen Schlüssel ausdenkt oder einen aus dem Verlauf
    aufsammelt, darf damit nichts auslösen. Werkzeuge außerhalb der
    Kurations-Oberfläche werden nicht angefasst — dort ist ``confirmToken`` ein
    gewöhnlicher Name ohne Bedeutung.
    """
    if not is_confirmable(tool_name) or _TOKEN_FIELD not in args:
        return args
    return {k: v for k, v in args.items() if k != _TOKEN_FIELD}


def extract_confirm_token(text: str) -> str | None:
    """Der Schlüssel aus dem Vorschautext des Servers, oder ``None``."""
    treffer = _TOKEN_IN_TEXT.search(text or "")
    return treffer.group(2) if treffer else None


def redact_confirm_token(text: str) -> str:
    """``text`` mit dem Schlüssel durch :data:`TOKEN_PLACEHOLDER` ersetzt.

    Die Vorschau selbst bleibt vollständig — der Nutzer soll ja sehen, was
    passieren würde. Nur der Schlüssel geht, und der Platzhalter sagt dem
    Modell zugleich, dass es ihn nicht selbst beschaffen muss. Text ohne
    Schlüssel kommt wortgleich zurück.
    """
    return _TOKEN_IN_TEXT.sub(rf"\g<1>{TOKEN_PLACEHOLDER}", text or "")


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
    """
    return _DISPLAY_TAIL.sub("", text or "").rstrip()


def change_fingerprint(tool_name: str, args: dict[str, Any]) -> str:
    """Identität eines Vorhabens: Werkzeug plus Argumente, ohne Schlüssel.

    Sortiert, damit die Reihenfolge, in der das Modell die Argumente nennt,
    nicht zur Eigenschaft der Änderung wird. Der Schlüssel selbst zählt nicht
    mit — sonst passte ein Bestätigungsaufruf nie zu seiner eigenen Vorschau.

    Das ist bewusst **nicht** derselbe Fingerabdruck wie der des Servers: der
    bildet den aufgelösten ChangeSet ab (alte und neue Werte im Repositorium)
    und ist die eigentliche Absicherung. Dieser hier beantwortet nur die
    Vorfrage, ob wir überhaupt vom selben Vorhaben sprechen.
    """
    sauber = strip_confirm_token(tool_name, args)
    return json.dumps([tool_name, sauber], sort_keys=True, ensure_ascii=False, default=str)


def remember_pending(
    tool_name: str, args: dict[str, Any], token: str, *, now: float
) -> dict[str, Any]:
    """Der Merkposten für einen offenen Bestätigungsvorgang.

    ``now`` reicht der Aufrufer herein (Epochensekunden, wie
    ``services/page_context.py`` es für seinen Zwischenspeicher tut): dieses
    Modul ist rein und hat keine Uhr. Der Zeitpunkt trägt die Frist aus
    :func:`is_expired`.

    Ein reines Dict, weil es als JSONB in ``session_state["entities"]`` liegt
    — der Konvention für zugübergreifenden Zustand: ``_``-präfigierter
    Schlüssel **in ``entities``**, wie ``_last_pattern`` und ``_frame``.

    Der Zusatz „in ``entities``" ist der Kern und nicht Beiwerk: von
    ``session_state`` überdauern nur die fünf Spalten aus ``update_session``
    einen Zug. Bis 2026-08-11 lag der Merkposten eine Ebene darüber, wurde nie
    gespeichert, und damit war **keine Bestätigung je einlösbar** — jedes „ja"
    erzeugte eine neue Vorschau. Der Debug-Auszug streicht ``_``-Schlüssel
    heraus, der Schlüssel bleibt also gespeichert und trotzdem unsichtbar.

    **Der Vorschautext gehört bewusst NICHT hier hinein** (S2, 2026-08-11).
    Beide beschreiben zwar dasselbe Vorhaben, haben aber verschiedene
    Lebensdauern: der Merkposten überdauert Züge, die sichtbare Vorschau gilt
    nur für den Zug, der sie erzeugt hat. Und der Bestätigungspfad *entfernt*
    den Merkposten — läge der Text darin, risse eine Bestätigung in demselben
    Zug eine frisch erzeugte Vorschau mit. Er wohnt deshalb in
    ``session_state["_write_preview"]`` — auf oberster Ebene, wo nichts
    gespeichert wird, und die Antwort verbraucht ihn dort.
    """
    return {
        "tool": tool_name,
        "fingerprint": change_fingerprint(tool_name, args),
        "token": token,
        "minted_at": now,
    }


def is_expired(pending: dict[str, Any] | None, *, now: float) -> bool:
    """Ist die Frist des Schlüssels verstrichen? (E4)

    Der Merkposten überdauert bis zum Sitzungsende; entfernt wird er nur auf
    dem Bestätigungspfad oder durch eine neue Vorschau desselben Werkzeugs.
    Fragt jemand Stunden später zufällig **exakt** dasselbe erneut an, wurde
    der alte Schlüssel bis E4 eingesetzt, vom Server abgelehnt und durch eine
    neue Vorschau beantwortet: ein überflüssiger Werkzeugaufruf, keine falsche
    Änderung, kein Loch — die Frist gilt serverseitig. Sie hier ein zweites Mal
    zu prüfen spart den Aufruf; sie ist **nicht** die Absicherung.

    Ein Merkposten ohne Zeitpunkt stammt aus der Zeit vor E4 und gilt als
    abgelaufen: nicht beweisbar frisch heisst nicht absetzen. Das kostet genau
    den einen Aufruf, den E4 sonst spart, und nur für die Sitzung, die beim
    Deploy gerade lief.
    """
    if not pending:
        return True
    minted = pending.get("minted_at")
    if not isinstance(minted, int | float):
        return True
    return (now - minted) >= TOKEN_TTL_SECONDS


def token_for(
    pending: dict[str, Any] | None, tool_name: str, args: dict[str, Any], *, now: float
) -> str | None:
    """Der einzusetzende Schlüssel — nur wenn es dasselbe Vorhaben ist und die
    Frist noch läuft.

    ``pending`` ist der Schnappschuss vom Zug-Eintritt; dass er aus einem
    *früheren* Zug stammt, verantwortet der Aufrufer (siehe Modul-Docstring).
    """
    if not pending or pending.get("tool") != tool_name:
        return None
    if pending.get("fingerprint") != change_fingerprint(tool_name, args):
        return None
    if is_expired(pending, now=now):
        return None
    return pending.get("token") or None
