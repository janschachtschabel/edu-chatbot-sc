"""M17 — Volltext anzeigen (services/content_text_action.py).

Nutzer-Vorgabe 2026-07-30: „bei den volltexten ist die idee das der user den
vollen inhalt braucht z.B. ein arbeitsblatt in markdown und nicht nur die
metadaten um tatsächlich damit arbeiten zu können". Der Weg ist deshalb
**deterministisch** — der Text geht unverändert in die Inline-Dokument-Box.
Ein Antwort-LLM dazwischen würde ihn kürzen oder umschreiben (und ein
50000-Zeichen-Dokument passt ohnehin in keine Antwort-Länge).

Diese Tests pinnen genau das: Wortlaut unverändert, und jeder Grund, den der
Server für einen fehlenden Volltext nennt, wird benannt statt verschluckt.
Konvention wie bei ``test_direct_actions``: MCP + Persistenz werden **auf
diesem Modul** gepatcht, die reinen Helfer laufen echt.
"""

from __future__ import annotations

import json

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.services import content_text_action


def _req(locale: str = "de-DE", **params) -> ChatRequest:
    return ChatRequest(
        session_id="bb-1", message="", action="show_content_text", action_params=params,
        environment=Environment(locale=locale),
    )


def _envelope(**over) -> str:
    base = {
        "nodeId": "abc-123",
        "title": "Arbeitsblatt Bruchrechnung",
        "text": "# Arbeitsblatt\n\nAufgabe 1: Kürze 6/8.\n\nAufgabe 2: …",
        "source": "repository",
        "sourceUrl": "https://wlo.example/abc-123",
        "charCount": 52,
        "truncated": False,
    }
    base.update(over)
    return json.dumps(base)


class _Spy:
    """Merkt sich Aufrufe (MCP- bzw. Persistenz-Grenze)."""

    def __init__(self, result: str = "") -> None:
        self.result = result
        self.calls: list[tuple] = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


def _patch(monkeypatch, mcp_result: str) -> _Spy:
    mcp = _Spy(mcp_result)
    monkeypatch.setattr(content_text_action, "call_mcp_tool", mcp)
    monkeypatch.setattr(content_text_action, "save_message", _Spy())
    return mcp


async def test_volltext_landet_unveraendert_in_der_box(monkeypatch):
    mcp = _patch(monkeypatch, _envelope())

    resp = await content_text_action._handle_show_content_text(
        None, _req(node_id="abc-123"), {"persona_id": "P-AND"},
    )

    # Der Wortlaut ist der Kern des Features — kein Kürzen, kein Umschreiben.
    assert len(resp.inline_documents) == 1
    doc = resp.inline_documents[0]
    assert doc.content == "# Arbeitsblatt\n\nAufgabe 1: Kürze 6/8.\n\nAufgabe 2: …"
    assert doc.title == "Arbeitsblatt Bruchrechnung"
    assert doc.meta["node_id"] == "abc-123"
    # Der begleitende Bubble-Text nennt die Quelle, wiederholt aber nicht den
    # Inhalt (sonst stünde alles doppelt da).
    assert doc.content not in resp.content
    assert mcp.calls[0][0][0] == "get_wlo_content_text"
    assert mcp.calls[0][0][1]["nodeId"] == "abc-123"


async def test_der_volltext_wird_persistiert_nicht_nur_die_begleitzeile(monkeypatch):
    # Nur mit dem Dokument in der Historie kann ein Folge-Zug (M11) daran
    # weiterarbeiten — der Antwort-Prompt bekommt die letzten 10 Nachrichten,
    # keinen Box-Inhalt. ``turn_persist`` macht es für M09/M10 genauso
    # („wir persistieren automatisch den vollen Material-Inhalt").
    mcp = _Spy(_envelope())
    save = _Spy()
    monkeypatch.setattr(content_text_action, "call_mcp_tool", mcp)
    monkeypatch.setattr(content_text_action, "save_message", save)

    resp = await content_text_action._handle_show_content_text(
        None, _req(node_id="abc-123"), {},
    )

    gespeichert = save.calls[0][0][3]
    assert "Aufgabe 1: Kürze 6/8." in gespeichert
    assert gespeichert != resp.content


async def test_der_zug_wird_als_m17_vermerkt(monkeypatch):
    # Ohne diese Markierung weiß der nächste Zug nicht, dass ein Vor-Inhalt
    # existiert — dieselbe Markierung setzt die Lernpfad-Direkt-Aktion für M09.
    _patch(monkeypatch, _envelope())
    state: dict = {}

    await content_text_action._handle_show_content_text(
        None, _req(node_id="abc-123"), state,
    )

    assert state.get("last_pattern") == "M17"


async def test_ohne_volltext_wird_der_zug_nicht_als_vor_inhalt_markiert(monkeypatch):
    # Ein Rechte-Fall hat keinen Text — ihn als Vor-Inhalt zu markieren, würde
    # einen Bearbeiten-Zug auf ein leeres Dokument schicken.
    _patch(monkeypatch, _envelope(text="", reason="access_denied", charCount=0))
    state: dict = {}

    await content_text_action._handle_show_content_text(
        None, _req(node_id="abc-123"), state,
    )

    assert "last_pattern" not in state


async def test_gekuerzter_volltext_wird_als_solcher_ausgewiesen(monkeypatch):
    # Der Server deckelt bei 50000 Zeichen. Ein Nutzer, der mit dem Dokument
    # arbeiten will, muss wissen, dass er nur einen Teil hat.
    _patch(monkeypatch, _envelope(truncated=True, charCount=50000))

    resp = await content_text_action._handle_show_content_text(
        None, _req(node_id="abc-123"), {},
    )

    assert resp.inline_documents[0].meta["truncated"] is True
    assert "gekürzt" in resp.content.lower()


async def test_access_denied_wird_benannt_und_bietet_alternativen(monkeypatch):
    # Nutzer-Entscheid: „muss dann irgendwie zurückmelden das kein volltext
    # verfügbar ist und eine ki generierung anbieten als alternative oder eine
    # suche nach anderen inhalten."
    _patch(monkeypatch, _envelope(text="", reason="access_denied", charCount=0))

    resp = await content_text_action._handle_show_content_text(
        None, _req(node_id="abc-123", title="Arbeitsblatt Bruchrechnung"), {},
    )

    assert resp.inline_documents == []
    assert "nicht frei zugänglich" in resp.content
    # Die beiden vom Nutzer benannten Auswege stehen als Quick-Replies bereit.
    qr = " | ".join(resp.quick_replies).lower()
    assert "erstell" in qr
    assert "alternativ" in qr or "andere" in qr


async def test_jeder_andere_grund_wird_unterschieden(monkeypatch):
    # Ein Extraktionsfehler ist kein Rechteproblem — ein Wiederholen kann hier
    # helfen, bei ``access_denied`` nie. Diese Unterscheidung ist der Grund,
    # warum W5-3a den ``reason`` überhaupt ausliest.
    _patch(monkeypatch, _envelope(text="", reason="extraction_failed", charCount=0))

    resp = await content_text_action._handle_show_content_text(
        None, _req(node_id="abc-123"), {},
    )

    assert "nicht frei zugänglich" not in resp.content
    assert resp.debug.entities["reason"] == "extraction_failed"


async def test_ohne_node_id_wird_kein_mcp_aufruf_gemacht(monkeypatch):
    mcp = _patch(monkeypatch, _envelope())

    resp = await content_text_action._handle_show_content_text(None, _req(), {})

    assert mcp.calls == []
    assert resp.inline_documents == []
    assert resp.content


async def test_mcp_fehler_bleibt_eine_ehrliche_antwort(monkeypatch):
    async def _boom(*_a, **_k):
        raise RuntimeError("MCP weg")

    monkeypatch.setattr(content_text_action, "call_mcp_tool", _boom)
    monkeypatch.setattr(content_text_action, "save_message", _Spy())

    resp = await content_text_action._handle_show_content_text(
        None, _req(node_id="abc-123"), {},
    )

    assert resp.inline_documents == []
    assert resp.content
    assert resp.debug.pattern == "M17"


# ── Sprache der Antwort (C1-f2b) ───────────────────────────────────────
# M17 spricht ohne Modell: jeder Satz hier ist deterministisch und muss der
# Widget-Sprache folgen wie die LLM-Antwort (C1-f1/f2a).


async def test_m17_deutsch_bleibt_der_gepinnte_wortlaut(monkeypatch):
    _patch(monkeypatch, _envelope())
    resp = await content_text_action._handle_show_content_text(
        None, _req(node_id="abc-123"), {},
    )
    assert resp.content.startswith("Hier ist der Inhalt von „Arbeitsblatt Bruchrechnung“.")
    assert resp.quick_replies[0] == "Mach den Text kürzer"


async def test_m17_englisches_widget_bekommt_englische_saetze(monkeypatch):
    _patch(monkeypatch, _envelope())
    resp = await content_text_action._handle_show_content_text(
        None, _req(locale="en-GB", node_id="abc-123"), {},
    )
    assert resp.content.startswith("Here is the content of “Arbeitsblatt Bruchrechnung”.")
    assert "Source: https://wlo.example/abc-123" in resp.content
    assert resp.quick_replies == [
        "Make the text shorter", "Put it in simpler words", "Show similar materials",
    ]


async def test_m17_grund_und_ausweg_folgen_der_sprache(monkeypatch):
    _patch(monkeypatch, _envelope(text="", reason="access_denied"))
    resp = await content_text_action._handle_show_content_text(
        None, _req(locale="en-GB", node_id="abc-123", title="Worksheet"), {},
    )
    assert "About the material “Worksheet”:" in resp.content
    assert "not freely accessible" in resp.content
    assert resp.quick_replies[0] == "Create your own material on this instead"


async def test_m17_fehlende_node_id_folgt_der_sprache(monkeypatch):
    _patch(monkeypatch, "")
    resp = await content_text_action._handle_show_content_text(
        None, _req(locale="en-GB"), {},
    )
    assert resp.content == "You have not told me which material to open."
