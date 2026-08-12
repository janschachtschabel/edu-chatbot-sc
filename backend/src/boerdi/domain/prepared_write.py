"""Die vorbereitete Anfrage aus einer MCP-Antwort (E3).

Im eingebetteten Betrieb führt der MCP-Server eine bestätigte Änderung nicht
aus, sondern **beschreibt** sie: er antwortet mit ``structuredContent``
statt zu schreiben. Ausgeführt wird sie in der Repository-Seite, mit der
Anmeldung, die dort schon besteht — so trägt die Änderung den Namen der Person
und nicht den eines Sammelkontos. Der Bauvorschlag steht in
``docs/plans/2026-08-12-einbettung-ohne-repo-aenderung.md`` (E2–E4), die
erzeugende Seite in ``services/write/prepared-request.ts`` des Servers.

**Warum hier geprüft wird und nicht nur umgefüllt.** Was durch diese Naht geht,
setzt später ein fremder Browser ab, mit den Rechten einer echten Person. Damit
ist die MCP-Antwort an dieser Stelle *Eingabe*, nicht Zwischenstand — auch wenn
sie von unserem eigenen Server kommt.

**Was diese Prüfung leistet:** die Anfrage ist ein Pfad und kann die Herkunft
des Repositoriums nicht verlassen. Ein ``//example.org/x`` sieht wie ein Pfad
aus, führt ein ``fetch`` aber an einen fremden Rechner; dasselbe gilt für den
Rückstrich, den Browser in Adressen wie einen Schrägstrich behandeln.

**Was sie bewusst NICHT leistet:** die Frage, ob dieser eine Aufruf erlaubt ist.
Die Erlaubnisliste aus Methode und Pfadmuster gehört ins Widget (E4), das den
Aufruf tatsächlich absetzt — und dort in dessen Bündel, nicht in eine zweite,
driftende Kopie hier. Jede Seite bewacht ihre eigene Grenze.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Lesen wird nie vorbereitet — das erledigt der Server selbst. Genau diese drei
# Methoden kennt auch der Typ auf der anderen Seite (``PreparedMethod``).
WRITING_METHODS = frozenset({"POST", "PUT", "DELETE"})


@dataclass(frozen=True, slots=True)
class PreparedWrite:
    """Ein Schreibzugriff, beschrieben statt ausgeführt."""

    method: str
    #: Pfad ab der Herkunft (``/edu-sharing/rest/…``); die Seite setzt ihre
    #: eigene davor, weil unsere ein interner Name sein kann.
    path: str
    #: Serialisierter JSON-Rumpf, oder ``None`` wo der Endpunkt keinen nimmt.
    body: str | None
    #: Der Satz für hinterher. Er gehört zum Werkzeug, das die Änderung kennt,
    #: nicht zu dem, der sie absetzt.
    done_message: str


def single_prepared_write(writes: list[PreparedWrite]) -> PreparedWrite | None:
    """Die eine Anfrage, die dieser Zug ausliefern darf — oder ``None``.

    Der Bestätigungs-Wall (``domain/write_confirm.py``) lässt je Zug höchstens
    **einen** Schlüssel einlösen; mehr als eine Vorbereitung ist damit kein
    Mehrfachfall, sondern ein gebrochener Zusicherungszustand. Dann ist nicht
    feststellbar, welcher Änderung ein Mensch zugestimmt hat — und unter dieser
    Unklarheit etwas auszuführen ist genau das, was der ganze Weg vermeidet.
    Also lieber keine: eine nicht ausgeführte Änderung kostet eine Wiederholung,
    eine falsch ausgeführte kostet einen Datensatz.
    """
    if len(writes) == 1:
        return writes[0]
    return None


def _is_safe_path(path: Any) -> bool:
    """Ist ``path`` ein Pfad, der die eigene Herkunft nicht verlassen kann?"""
    if not isinstance(path, str) or not path.startswith("/"):
        return False
    # ``//host/x`` ist protokoll-relativ und landet bei einem fremden Rechner.
    # Der Rückstrich zählt mit: Browser normalisieren ihn in Adressen zu ``/``,
    # ``/\host`` wirkt also wie ``//host``.
    if "\\" in path or path.startswith("//"):
        return False
    return not any(ord(zeichen) < 0x20 or ord(zeichen) == 0x7F for zeichen in path)


def read_prepared_write(structured: Any) -> PreparedWrite | None:
    """Die vorbereitete Anfrage aus ``structuredContent`` — oder ``None``.

    ``None`` ist der Normalfall und keine Ausnahme: jedes lesende Werkzeug und
    jede Vorschau antwortet ohne strukturierten Teil. Auch alles Fehlerhafte
    endet hier still bei ``None``, denn es gibt nichts zu retten — eine halb
    gelesene Anfrage abzusetzen wäre schlimmer als keine.
    """
    if not isinstance(structured, dict):
        return None
    request = structured.get("preparedRequest")
    if not isinstance(request, dict):
        return None

    method = request.get("method")
    if method not in WRITING_METHODS:
        return None
    if not _is_safe_path(request.get("path")):
        return None

    body = request.get("body")
    if body is not None and not isinstance(body, str):
        return None

    done_message = structured.get("doneMessage")
    return PreparedWrite(
        method=str(method),
        path=str(request["path"]),
        body=body,
        done_message=done_message if isinstance(done_message, str) else "",
    )
