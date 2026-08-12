"""E3: die vorbereitete Anfrage aus der MCP-Antwort — lesen und prüfen.

Im eingebetteten Betrieb schreibt der MCP-Server nicht selbst, sondern
beschreibt die Änderung: er antwortet mit ``structuredContent`` statt sie
auszuführen (E2, ``services/write/prepared-request.ts`` dort). Ausgeführt wird
sie **im Browser**, mit der Anmeldung, die in der Repository-Seite schon
besteht.

Genau das macht diese Naht zur Vertrauensgrenze und nicht zu einer
Feld-Umfüllung: was hier durchgeht, schickt später ein fremder Browser mit den
Rechten einer echten Person ab. Deshalb prüfen die Tests unten vor allem, was
**nicht** durchkommt — allen voran alles, was den Aufruf von der Herkunft des
Repositoriums fortführen könnte.

Die Prüfung im Widget (E4) ersetzt diese nicht und wird von ihr nicht ersetzt:
jede Seite bewacht ihre eigene Grenze.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest
from mcp.types import CallToolResult, TextContent

from boerdi.domain.prepared_write import (
    PreparedWrite,
    read_prepared_write,
    single_prepared_write,
)
from boerdi.services.mcp import client, tool_cache, transport

# Eine Antwort, wie der Server sie beim Bestätigen liefert (gemessen am
# Werkzeug ``wlo_add_to_collection``, 2026-08-12).
FILING = {
    "preparedRequest": {
        "method": "PUT",
        "path": "/edu-sharing/rest/collection/v1/collections/-home-/coll-1/references/node-1",
    },
    "doneMessage": "„Arbeitsblatt Brüche“ ist jetzt in „Bruchrechnung“.",
}


def test_die_fertige_anfrage_wird_vollstaendig_gelesen() -> None:
    gelesen = read_prepared_write(FILING)
    assert gelesen == PreparedWrite(
        method="PUT",
        path="/edu-sharing/rest/collection/v1/collections/-home-/coll-1/references/node-1",
        body=None,
        done_message="„Arbeitsblatt Brüche“ ist jetzt in „Bruchrechnung“.",
    )


def test_ein_rumpf_faehrt_mit_wenn_der_endpunkt_einen_nimmt() -> None:
    gelesen = read_prepared_write({
        "preparedRequest": {"method": "POST", "path": "/edu-sharing/rest/x", "body": '{"a":1}'},
        "doneMessage": "erledigt",
    })
    assert gelesen is not None
    assert gelesen.body == '{"a":1}'


def test_eine_gewoehnliche_antwort_ohne_strukturierten_teil_ergibt_nichts() -> None:
    # Der Normalfall: jedes lesende Werkzeug und jede Vorschau antworten ohne
    # ``structuredContent``. Das darf keine Ausnahme sein, sondern schlicht
    # „hier ist nichts vorbereitet".
    assert read_prepared_write(None) is None
    assert read_prepared_write({}) is None
    assert read_prepared_write({"foo": "bar"}) is None
    assert read_prepared_write("kein Objekt") is None


def test_ein_protokoll_relativer_pfad_wird_abgelehnt() -> None:
    # ``fetch("//example.org/x")`` geht an eine FREMDE Herkunft — die Anfrage
    # sähe wie ein Pfad aus und verließe das Repositorium. Der Server baut so
    # etwas nie (``toRepositoryPath`` gibt immer einen einfachen ``/``-Pfad),
    # also kostet die Ablehnung nichts Echtes.
    for pfad in ["//example.org/x", "/\\example.org/x", "\\\\example.org/x"]:
        anfrage = {"preparedRequest": {"method": "PUT", "path": pfad}}
        assert read_prepared_write(anfrage) is None, pfad


def test_eine_absolute_adresse_wird_abgelehnt() -> None:
    for pfad in ["https://example.org/x", "http://repository/x", "javascript:alert(1)"]:
        anfrage = {"preparedRequest": {"method": "PUT", "path": pfad}}
        assert read_prepared_write(anfrage) is None, pfad


def test_nur_die_drei_aendernden_methoden_kommen_durch() -> None:
    for methode in ["GET", "HEAD", "OPTIONS", "TRACE", "put", "", "PUT DELETE"]:
        assert read_prepared_write({
            "preparedRequest": {"method": methode, "path": "/edu-sharing/rest/x"},
        }) is None, methode
    for methode in ["POST", "PUT", "DELETE"]:
        assert read_prepared_write({
            "preparedRequest": {"method": methode, "path": "/edu-sharing/rest/x"},
        }) is not None, methode


def test_fehlende_oder_falsch_getypte_teile_ergeben_nichts() -> None:
    for kaputt in [
        {"preparedRequest": {"method": "PUT"}},
        {"preparedRequest": {"path": "/edu-sharing/rest/x"}},
        {"preparedRequest": {"method": "PUT", "path": 42}},
        {"preparedRequest": {"method": "PUT", "path": "/x", "body": {"nicht": "text"}}},
        {"preparedRequest": "kein Objekt"},
    ]:
        assert read_prepared_write(kaputt) is None, kaputt


def test_ein_pfad_mit_zeilenumbruch_wird_abgelehnt() -> None:
    # Steuerzeichen in einer Adresse sind nie legitim und der klassische Weg,
    # eine Anfrage in zwei zu spalten.
    assert read_prepared_write({
        "preparedRequest": {"method": "PUT", "path": "/edu-sharing/rest/x\nX-Foo: bar"},
    }) is None


def test_ohne_abschlusssatz_bleibt_die_anfrage_gueltig() -> None:
    # Der Satz ist die Formulierung für hinterher, nicht die Erlaubnis. Fehlt
    # er, ist die Anfrage trotzdem eine Anfrage — nur ohne Text.
    gelesen = read_prepared_write(
        {"preparedRequest": {"method": "PUT", "path": "/edu-sharing/rest/x"}})
    assert gelesen is not None
    assert gelesen.done_message == ""


# ── Die Naht: vom SDK-Ergebnis bis in den Sammler ────────────────────────
# Zwei Stationen, an denen der strukturierte Teil bisher verlorenging: der
# Transport reichte nur Textblöcke weiter, und der Client las nur Text.


NICHT_AUSGEFUEHRT = "Die Änderung wurde hier nicht ausgeführt."


class _FakeSession:
    """Eine initialisierte ``ClientSession``, die ein festes Ergebnis liefert."""

    def __init__(self, call_result: CallToolResult) -> None:
        self._call_result = call_result

    async def call_tool(self, name, arguments=None):  # noqa: ANN001, ANN202 — Test-Double
        return self._call_result


@pytest.fixture()
def sammler():
    """Frischer ContextVar-Sammler und leerer Tool-Cache je Test."""
    tool_cache.clear_tool_cache()
    client.reset_prepared_writes()
    yield
    tool_cache.clear_tool_cache()
    client.reset_prepared_writes()


def _antwort(text: str, structured: dict | None) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        isError=False,
        structuredContent=structured,
    )


def test_der_transport_reicht_den_strukturierten_teil_durch(monkeypatch) -> None:
    # Bis E3 endete die Anfrage hier: ``call_tool`` normalisierte auf reine
    # Textblöcke, und ``structuredContent`` fiel still weg.
    @asynccontextmanager
    async def _fake_open(url):  # noqa: ANN001, ANN202 — Test-Double
        yield _FakeSession(_antwort(NICHT_AUSGEFUEHRT, FILING))

    monkeypatch.setattr(transport, "_open_session", _fake_open)
    ergebnis = asyncio.run(transport.call_tool("wlo_add_to_collection", {}, url="https://u/mcp"))
    assert ergebnis["result"]["structuredContent"] == FILING


def test_ohne_strukturierten_teil_bleibt_die_ergebnisform_unveraendert(monkeypatch) -> None:
    # Der Normalfall für 40 der 41 Werkzeuge. Ein zusätzlicher Schlüssel mit
    # ``None`` wäre kein Fehler, aber eine Formänderung für jeden Leser.
    @asynccontextmanager
    async def _fake_open(url):  # noqa: ANN001, ANN202 — Test-Double
        yield _FakeSession(_antwort("ERGEBNIS", None))

    monkeypatch.setattr(transport, "_open_session", _fake_open)
    ergebnis = asyncio.run(transport.call_tool("search_wlo_content", {}, url="https://u/mcp"))
    assert ergebnis == {"result": {"content": [{"type": "text", "text": "ERGEBNIS"}]}}


def _wire(monkeypatch, structured: dict | None) -> None:
    async def fake_call_tool(tool_name, arguments=None, *, url=None):  # noqa: ANN001, ANN202
        antwort: dict = {"content": [{"type": "text", "text": NICHT_AUSGEFUEHRT}]}
        if structured is not None:
            antwort["structuredContent"] = structured
        return {"result": antwort}

    monkeypatch.setattr(transport, "call_tool", fake_call_tool)
    monkeypatch.setattr(client, "_get_server_url_for_tool", lambda t: "https://fake/mcp")


def test_der_client_sammelt_die_vorbereitete_anfrage(monkeypatch, sammler) -> None:
    _wire(monkeypatch, FILING)
    text = asyncio.run(
        client.call_mcp_tool("wlo_add_to_collection", {"collectionId": "c", "nodeId": "n"}))

    # Der Text bleibt, was er war: das Modell soll lesen, dass hier nichts
    # geschrieben wurde.
    assert "nicht ausgeführt" in text
    gesammelt = client.get_prepared_writes()
    assert len(gesammelt) == 1
    assert gesammelt[0].method == "PUT"
    assert gesammelt[0].path.endswith("/references/node-1")


def test_eine_gewoehnliche_antwort_sammelt_nichts(monkeypatch, sammler) -> None:
    _wire(monkeypatch, None)
    asyncio.run(client.call_mcp_tool("search_wlo_content", {"query": "x"}))
    assert client.get_prepared_writes() == []


def test_eine_unbrauchbare_anfrage_wird_verworfen(monkeypatch, sammler) -> None:
    # Der Fall, auf den es ankommt: was hier durchkäme, setzte später ein
    # Browser mit fremden Rechten ab. Lieber nichts als etwas Halbes.
    _wire(monkeypatch, {"preparedRequest": {"method": "PUT", "path": "//example.org/x"}})
    text = asyncio.run(
        client.call_mcp_tool("wlo_add_to_collection", {"collectionId": "c", "nodeId": "n"}))
    assert client.get_prepared_writes() == []
    assert "nicht ausgeführt" in text, "der Text des Werkzeugs bleibt trotzdem stehen"


# ── Die Regel: höchstens eine je Zug ─────────────────────────────────────


def test_ohne_vorbereitung_gibt_es_nichts_auszuliefern() -> None:
    assert single_prepared_write([]) is None


def test_die_eine_vorbereitete_anfrage_wird_ausgeliefert() -> None:
    eine = read_prepared_write(FILING)
    assert single_prepared_write([eine]) is eine


def test_bei_mehreren_wird_keine_ausgeliefert() -> None:
    # Der Bestätigungs-Wall lässt je Zug höchstens einen Schlüssel einlösen,
    # zwei Vorbereitungen sind also ein gebrochener Zusicherungszustand. Dann
    # ist NICHT feststellbar, welcher der beiden zugestimmt wurde — und unter
    # Unklarheit auszuführen ist genau das, was dieser ganze Weg vermeidet.
    zwei = [read_prepared_write(FILING), read_prepared_write(FILING)]
    assert single_prepared_write(zwei) is None
