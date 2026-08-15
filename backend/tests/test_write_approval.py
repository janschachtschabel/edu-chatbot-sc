"""S5 — die abgenommene Änderung wird eingelöst, ohne das Modell zu fragen.

Befund 2026-08-15 (Nutzer, live): „ich komme bei Erstellung und Upload nur bis
zu der Stelle, das er eine Bestätigung will — die aber immer wieder gefragt wird
und es geht nicht weiter."

Die Ursache steckt nicht im Wall, sondern darin, wo sein Merkposten bekannt ist.
``_pending_write`` wurde bis hierher **nur** in ``services/tool_loop`` gelesen.
Damit hing die Einlösung an zwei Entscheidungen, die nichts garantiert:

1. Der Klassifikator musste auf ein „ja" hin M18 wählen — nur dieses Muster
   nennt die schreibenden Werkzeuge, und nur genannte Werkzeuge stehen dem
   Modell überhaupt zur Verfügung (``_select_active_tools``). Fällt die Wahl
   anders aus, ist die Einlösung in diesem Zug **unmöglich**.
2. Das Modell musste dasselbe Werkzeug erneut rufen — mit Argumenten, die es
   nicht kennen kann: die Historie trägt nur die gespeicherten Texte
   (``_assemble_messages`` → ``history[-10:]``), die Vorschau steht als
   Inline-Dokument daneben, und die Argumente des ersten Aufrufs standen nie
   darin. Bei einem Upload ist die Nutzlast grundsätzlich nicht wiederholbar.

Beides zusammen ist die Schleife: jedes „ja" erzeugt eine neue Frage.

Die Abnahme ist aber ein **bestimmter Zustand** — Werkzeug, Argumente und
Schlüssel liegen fertig im Merkposten. Sie einzulösen braucht kein Modell.
Diese Tests klemmen genau das fest.
"""

from __future__ import annotations

import time

import pytest

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.domain.write_confirm import remember_pending
from boerdi.i18n.bot_text import bot_text
from boerdi.services import write_approval as wa_mod
from boerdi.services.write_approval import redeem_write_approval

_SESSION = object()  # Sentinel — jede DB-Grenze ist gepatcht.

_WERKZEUG = "wlo_create_content"
_TOKEN = "Ax9-_QmZ2kLpWvRt7NbYcE4s"
# Eine Nutzlast, wie sie ein Upload trägt: genau das, was das Modell im
# Folgezug nicht zeichengleich wiederholen kann.
_ARGS = {
    "title": "Arbeitsblatt Bruchrechnung",
    "content": "# Brüche\n\nAufgabe 1: Kürze 12/18.\n" * 20,
}
_SERVERTEXT = "Der Datensatz wurde angelegt: „Arbeitsblatt Bruchrechnung“."


class _Spy:
    """Attrappe für ``call_mcp_tool_status``.

    ``ret`` darf eine Zeichenkette sein (dann gilt „kein Fehler") oder ein Paar
    ``(text, art)``. Der Kurzform wegen: die meisten Tests interessieren sich
    nicht für die Fehler-Art, und ein Paar in jeder Zeile wäre Rauschen.
    """

    def __init__(self, ret=None, raises: Exception | None = None):
        self.calls: list[tuple] = []
        self.ret = ret
        self.raises = raises

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.raises is not None:
            raise self.raises
        if isinstance(self.ret, tuple):
            return self.ret
        return (self.ret, "")


def _req(message: str = "Ja, so ausführen", action: str | None = None) -> ChatRequest:
    return ChatRequest(
        session_id="bb-1", message=message, action=action,
        environment=Environment(locale="de"),
    )


def _zustand(*, args=None, token=_TOKEN, tool=_WERKZEUG, alter: float = 0.0) -> dict:
    """Sitzungszustand mit einem offenen Vorgang, wie ``setup`` ihn lädt."""
    merkposten = remember_pending(
        tool, args if args is not None else _ARGS, token, now=time.time() - alter)
    return {"persona_id": "P-AND", "entities": {"_pending_write": merkposten}}


@pytest.fixture
def _grenzen(monkeypatch):
    """Die drei Aussenkanten: MCP-Aufruf, Sitzungs-Schreiben, Nachricht."""
    mcp = _Spy(_SERVERTEXT)
    update = _Spy()
    save = _Spy()
    monkeypatch.setattr(wa_mod, "call_mcp_tool_status", mcp)
    monkeypatch.setattr(wa_mod, "update_session", update)
    monkeypatch.setattr(wa_mod, "save_message", save)
    return mcp, update, save


# ── Wann NICHT eingelöst wird ────────────────────────────────────────────


class TestZurueckhaltung:
    @pytest.mark.asyncio
    async def test_ohne_offenen_vorgang_passiert_nichts(self, _grenzen):
        mcp, _u, _s = _grenzen
        antwort = await redeem_write_approval(
            _SESSION, _req(), {"persona_id": "P-AND", "entities": {}})
        assert antwort is None
        assert mcp.calls == [], "Ohne Abnahme darf nichts geschrieben werden"

    @pytest.mark.asyncio
    async def test_ein_vorbehalt_ist_keine_zustimmung(self, _grenzen):
        # „ja, aber …" ist der Auftrag zu einer NEUEN Vorschau. Die alte
        # Nutzlast auszuführen wäre eine Änderung, der niemand zugestimmt hat.
        mcp, _u, _s = _grenzen
        antwort = await redeem_write_approval(
            _SESSION, _req("ja, aber nenn es anders"), _zustand())
        assert antwort is None
        assert mcp.calls == []

    @pytest.mark.asyncio
    async def test_eine_neue_anweisung_ist_keine_zustimmung(self, _grenzen):
        mcp, _u, _s = _grenzen
        antwort = await redeem_write_approval(
            _SESSION, _req("such mir was zu Optik"), _zustand())
        assert antwort is None
        assert mcp.calls == []

    @pytest.mark.asyncio
    async def test_abgelaufener_vorgang_wird_nicht_ausgefuehrt(self, _grenzen):
        # E4: der Schlüssel gilt zehn Minuten. Ein sicher toter Schlüssel wird
        # gar nicht erst abgesetzt — der Zug läuft normal weiter und zeigt eine
        # frische Vorschau.
        mcp, _u, _s = _grenzen
        antwort = await redeem_write_approval(
            _SESSION, _req(), _zustand(alter=1200.0))
        assert antwort is None
        assert mcp.calls == []

    @pytest.mark.asyncio
    async def test_ohne_gemerkte_argumente_bleibt_es_beim_alten_weg(
        self, monkeypatch, _grenzen
    ):
        # Über ``MAX_REMEMBERED_ARGS_BYTES`` merkt sich ``remember_pending``
        # keine Argumente. Dann kann dieser Weg nichts ausführen — und tut es
        # auch nicht, statt mit halben Angaben zu schreiben. Der
        # Fingerabdruck-Weg im Tool-Loop trägt diesen Fall weiter.
        mcp, _u, _s = _grenzen
        zustand = _zustand()
        zustand["entities"]["_pending_write"].pop("args")
        assert await redeem_write_approval(_SESSION, _req(), zustand) is None
        assert mcp.calls == []


# ── Die Einlösung selbst ─────────────────────────────────────────────────


class TestEinloesung:
    @pytest.mark.asyncio
    async def test_ausgefuehrt_wird_genau_das_abgenommene(self, _grenzen):
        # DER PUNKT. Kein Modell hat hier etwas zusammengestellt: Werkzeug,
        # Argumente und Schlüssel kommen aus dem Merkposten. Damit sind
        # „gezeigt" und „ausgeführt" dasselbe — zeichengleich, auch bei einer
        # Nutzlast, die niemand wiederholen könnte.
        mcp, _u, _s = _grenzen
        antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
        assert antwort is not None
        (name, args), _kw = mcp.calls[0]
        assert name == _WERKZEUG
        assert args == {**_ARGS, "confirmToken": _TOKEN}

    @pytest.mark.asyncio
    async def test_der_servertext_ist_die_antwort(self, _grenzen):
        # Der Server berichtet, was TATSÄCHLICH ankam. Ginge das durch das
        # Modell, wäre es eine Nacherzählung — dieselbe Begründung wie bei der
        # Volltext-Aktion (``content_text_action``).
        _m, _u, _s = _grenzen
        antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
        assert _SERVERTEXT in antwort.content

    @pytest.mark.asyncio
    async def test_der_schluessel_erreicht_die_antwort_nie(self, monkeypatch, _grenzen):
        # Tiefenstaffelung: nennte der Server in seiner Erfolgsmeldung einen
        # Schlüssel, ginge er über die Antwort in Verlauf und Protokoll.
        mcp, _u, save = _grenzen
        mcp.ret = f"Angelegt. confirmToken: {_TOKEN} wäre der nächste."
        antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
        assert _TOKEN not in antwort.content
        assert _TOKEN not in str(save.calls)

    @pytest.mark.asyncio
    async def test_der_merkposten_ist_danach_weg_und_das_steht_in_der_db(self, _grenzen):
        # Ohne das Speichern wäre der Vorgang beim nächsten „ja" erneut da —
        # und der Zug schriebe ein zweites Mal.
        _m, update, _s = _grenzen
        zustand = _zustand()
        await redeem_write_approval(_SESSION, _req(), zustand)
        assert "_pending_write" not in zustand["entities"]
        assert update.calls, "Der verbrauchte Vorgang muss in die DB"
        assert "_pending_write" not in update.calls[0][1]["entities"]

    @pytest.mark.asyncio
    async def test_ein_zweites_ja_loest_nichts_erneut_aus(self, _grenzen):
        mcp, _u, _s = _grenzen
        zustand = _zustand()
        await redeem_write_approval(_SESSION, _req(), zustand)
        assert await redeem_write_approval(_SESSION, _req(), zustand) is None
        assert len(mcp.calls) == 1

    @pytest.mark.asyncio
    async def test_die_antwort_wird_gespeichert(self, _grenzen):
        _m, _u, save = _grenzen
        await redeem_write_approval(_SESSION, _req(), _zustand())
        assert save.calls, "Ohne Persistenz fehlt die Ausführung im Verlauf"
        assert save.calls[0][0][2] == "assistant"


# ── Wenn es schiefgeht ───────────────────────────────────────────────────


class TestFehlerString:
    """Die HÄUFIGE Fehlerform — und die, die durchgerutscht war (Review S5-R).

    ``transport.call_tool`` fängt **jede** Ausnahme ab und macht daraus ein
    Fehler-Dict (``transport.py:146``); ``call_mcp_tool`` gibt daraufhin den
    String ``"MCP error: …"`` zurück. Es wird also praktisch nie geworfen —
    abgelehnter Schlüssel, fehlende Rechte, Zeitüberschreitung, Server weg:
    alles kommt als gewöhnlicher Rückgabewert.

    Bis zum Review lief genau das in den Erfolgszweig: Protokoll meldete
    „eingelöst", der Nutzer bekam den rohen Servertext als Antwort, und der
    Merkposten war verbraucht.
    """

    @pytest.mark.asyncio
    async def test_ein_fehler_string_gilt_nicht_als_erfolg(self, _grenzen):
        mcp, _u, _s = _grenzen
        mcp.ret = "MCP error: confirmToken abgelaufen oder bereits verbraucht"
        antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
        assert antwort is not None
        assert "MCP error" not in antwort.content, (
            "Der rohe Servertext ist ein Interna-Auszug und gehört nicht vor den Nutzer"
        )
        assert antwort.debug.entities.get("reason") == "mcp_error"

    @pytest.mark.asyncio
    async def test_eine_ablehnung_darf_klar_sagen_dass_nichts_geschah(self, _grenzen):
        # Wenn der Server GEANTWORTET hat, steht fest, dass er nicht geschrieben
        # hat. Diese Person auf Verdacht in WLO nachsehen zu schicken, wäre
        # unnötig — sie kann direkt nachbessern.
        mcp, _u, _s = _grenzen
        mcp.ret = ("MCP error: Titel zu lang", "tool")
        antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
        assert antwort.content == bot_text("de", "write.executeRejected")
        assert "nichts geändert" in antwort.content

    @pytest.mark.asyncio
    async def test_der_text_behauptet_nichts_ueber_den_bestand(self, _grenzen):
        # Der Kern von Befund 2: ob die Änderung angekommen ist, ist von hier
        # aus NICHT feststellbar — Ablehnung und Zeitüberschreitung sehen
        # identisch aus. Ein Satz, der „es wurde nichts geändert" behauptet,
        # schickt die Person im Zweifel in eine Dublette.
        mcp, _u, _s = _grenzen
        mcp.ret = ("MCP error: read timeout", "transport")
        antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
        assert "nichts geändert" not in antwort.content
        assert antwort.content == bot_text("de", "write.executeUnconfirmed")

    @pytest.mark.asyncio
    async def test_ohne_bekannte_art_gilt_der_unklare_text(self, _grenzen):
        # Die vorsichtige Richtung: was nicht als Ablehnung BELEGT ist, zählt
        # als unklar. Nachsehen kostet eine Minute, eine Dublette bleibt.
        mcp, _u, _s = _grenzen
        mcp.ret = ("MCP error: irgendwas", "")
        antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
        assert antwort.content == bot_text("de", "write.executeUnconfirmed")

    @pytest.mark.asyncio
    async def test_auch_hier_ist_der_vorgang_verbraucht(self, _grenzen):
        mcp, _u, _s = _grenzen
        mcp.ret = "MCP error: irgendwas"
        zustand = _zustand()
        await redeem_write_approval(_SESSION, _req(), zustand)
        assert "_pending_write" not in zustand["entities"]

    @pytest.mark.asyncio
    async def test_ein_erfolg_der_zufaellig_so_anfaengt_bleibt_erfolg(self, _grenzen):
        # Gegenprobe: die Erkennung hängt am Präfix, nicht an einem Vorkommen
        # irgendwo im Text. Ein Servertext, der das Wort später nennt, ist kein
        # Fehlschlag.
        mcp, _u, _s = _grenzen
        mcp.ret = "Angelegt. Hinweis: ein MCP error trat nicht auf."
        antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
        assert antwort.content == mcp.ret


class TestVorbereiteteAnfrage:
    @pytest.mark.asyncio
    async def test_mehrere_vorbereitete_anfragen_werden_gemeldet(
        self, monkeypatch, _grenzen, caplog
    ):
        # Mehr als eine ist ein gebrochener Zusicherungszustand: es ist nicht
        # feststellbar, welcher Änderung zugestimmt wurde, also wird KEINE
        # ausgeliefert. Der Nachbar ``turn_persist`` protokolliert das; ohne
        # eine Zeile sieht der Nutzer eine Erfolgsmeldung, und nichts passiert.
        from boerdi.domain.prepared_write import PreparedWrite

        def _zwei():
            return [
                PreparedWrite(method="POST", path="/a", body=None, done_message=""),
                PreparedWrite(method="POST", path="/b", body=None, done_message=""),
            ]

        monkeypatch.setattr(wa_mod, "get_prepared_writes", _zwei)
        with caplog.at_level("WARNING"):
            antwort = await redeem_write_approval(_SESSION, _req(), _zustand())

        assert antwort.prepared_write is None
        assert "vorbereitete" in caplog.text.lower()


class TestFehlschlag:
    """Der SELTENE Weg: eine Ausnahme kommt an ``call_mcp_tool`` vorbei.

    Der Transport fängt normalerweise alles ab (siehe ``TestFehlerString``);
    was hier geprüft wird, ist die Wache dahinter — ein Zug darf auch dann
    nicht ohne Antwort enden.
    """

    @pytest.mark.asyncio
    async def test_ein_mcp_fehler_wird_benannt_statt_verschluckt(
        self, monkeypatch, _grenzen
    ):
        mcp, _u, _s = _grenzen
        mcp.raises = RuntimeError("connection refused")
        antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
        assert antwort is not None, "Der Zug darf nicht ohne Antwort enden"
        assert antwort.content.strip(), "Der Nutzer muss erfahren, dass nichts geschah"

    @pytest.mark.asyncio
    async def test_ein_fehler_verraet_die_ursache_nicht_nach_aussen(self, _grenzen):
        mcp, _u, _s = _grenzen
        mcp.raises = RuntimeError("Bearer wlo2.geheim — connection refused")
        antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
        assert "wlo2." not in antwort.content
        assert "connection refused" not in antwort.content

    @pytest.mark.asyncio
    async def test_nach_einem_fehler_ist_der_vorgang_trotzdem_verbraucht(self, _grenzen):
        # Der Schlüssel gilt serverseitig genau einmal. Ob der Aufruf ankam,
        # ist von hier aus nicht feststellbar — ihn ein zweites Mal abzusetzen
        # könnte also doppelt schreiben. Lieber eine frische Abnahme verlangen.
        mcp, _u, _s = _grenzen
        mcp.raises = RuntimeError("timeout")
        zustand = _zustand()
        await redeem_write_approval(_SESSION, _req(), zustand)
        assert "_pending_write" not in zustand["entities"]
