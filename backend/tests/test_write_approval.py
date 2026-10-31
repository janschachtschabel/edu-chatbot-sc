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

import litellm
import pytest

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.domain.write_confirm import remember_pending
from boerdi.i18n.bot_text import bot_text
from boerdi.services import write_approval as wa_mod
from boerdi.services import zustimmung_pruefen as _zp
from boerdi.services.llm_parallel import LlmAusgelastet
from boerdi.services.write_approval import discard_stale_approval, redeem_write_approval

# Die echte Prüfung — ``conftest`` ersetzt sie für alle Tests (kein Netz).
_ECHTES_URTEIL = _zp._llm_urteil

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


def _zustand(*, args=None, token=_TOKEN, tool=_WERKZEUG, alter: float = 0.0,
             caller: str = "") -> dict:
    """Sitzungszustand mit einem offenen Vorgang, wie ``setup`` ihn lädt.

    ``caller`` ist das Kennzeichen des Aufrufers, der die Vorschau auslöste. Die
    Vorgabe ``""`` (anonym) entspricht dem Testlauf ohne Block und Dienst-Token.
    """
    merkposten = remember_pending(
        tool, args if args is not None else _ARGS, token, now=time.time() - alter,
        caller=caller)
    return {"persona_id": "P-AND", "entities": {"_pending_write": merkposten}}


@pytest.fixture
def _grenzen(monkeypatch):
    """Die drei Aussenkanten: MCP-Aufruf, Sitzungs-Schreiben, Nachricht — und
    das Schreibrecht: diese Tests stehen für eine angemeldete Person (seit
    Paket 7, S4, ist das die Bedingung; ``TestNurMitSchreibrecht`` prüft sie)."""
    mcp = _Spy(_SERVERTEXT)
    update = _Spy()
    save = _Spy()
    monkeypatch.setattr(wa_mod, "call_mcp_tool_status", mcp)
    monkeypatch.setattr(wa_mod, "update_session", update)
    monkeypatch.setattr(wa_mod, "save_message", save)
    monkeypatch.setattr(wa_mod, "schreiben_erlaubt", lambda: True)
    return mcp, update, save


class TestNurMitSchreibrecht:
    """Paket 7 (S4, P5-9): ohne persönliche Anmeldung — und ohne die
    Studio-Erlaubnis für das Gastkonto — wird nichts eingelöst. Bis dahin
    schrieb ein „ja“ im Muster-Modus mit dem Dienst-Block (B-H3)."""

    @pytest.mark.asyncio
    async def test_ohne_schreibrecht_wird_nicht_eingeloest(self, monkeypatch, _grenzen):
        monkeypatch.setattr(wa_mod, "schreiben_erlaubt", lambda: False)
        mcp, update, _ = _grenzen
        zustand = _zustand()
        assert await redeem_write_approval(_SESSION, _req(), zustand) is None
        assert mcp.calls == []
        # Verworfen, auch in der Datenbank: einlösen kann ihn so niemand mehr.
        assert "_pending_write" not in zustand["entities"]
        assert update.calls


    @pytest.mark.asyncio
    @pytest.mark.parametrize("grund", ["verborgen", "nur-lesen"])
    async def test_ein_abgeschaltetes_werkzeug_wird_nicht_eingeloest(
            self, monkeypatch, _grenzen, grund):
        """Review Paket 7 (MAJOR 11): ein „ja“ löste den gemerkten Vorgang direkt aus —
        auch wenn das Studio das Werkzeug inzwischen verborgen hat oder die Einbettung
        nur lesen darf. Er wird verworfen wie ohne Schreibrecht."""
        req = _req()
        if grund == "verborgen":
            monkeypatch.setattr(wa_mod, "verborgene_werkzeuge", lambda: frozenset({_WERKZEUG}))
        else:
            req.environment.tool_mode = "read-only"
        mcp, update, _ = _grenzen
        zustand = _zustand()
        assert await redeem_write_approval(_SESSION, req, zustand) is None
        assert mcp.calls == []
        assert "_pending_write" not in zustand["entities"]
        assert update.calls


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


# ── Wann ein offener Vorgang verfällt (Audit 2026-09-29) ─────────────────


class TestVerfall:
    """Bestätigen kann nur die Antwort DIREKT auf die Vorschau.

    Ein Vorgang, der einen Zug mit anderem Anliegen überdauert, wartete bis
    hier bis zum Fristende (zehn Minuten) — und ein beliebiges späteres „Ja …"
    führte ihn aus. Der Preis der engen Regel ist eine zweite Frage; der Preis
    der weiten eine Änderung, der niemand zugestimmt hat (``is_affirmation``).
    """

    @pytest.mark.asyncio
    async def test_ein_anderes_anliegen_verwirft_den_vorgang(self, _grenzen):
        _mcp, update, _s = _grenzen
        zustand = _zustand()
        verworfen = await discard_stale_approval(
            _SESSION, _req("Zeig mir erst Videos zu Brüchen"), zustand)
        assert verworfen is True
        assert "_pending_write" not in zustand["entities"]
        # Sofort gespeichert: nicht jeder Weg nach dem Vorlauf schreibt
        # ``entities`` zurück (Direkt-Aktionen), der Verfall muss es trotzdem.
        assert len(update.calls) == 1
        assert "_pending_write" not in update.calls[0][1]["entities"]

    @pytest.mark.asyncio
    async def test_ein_vorbehalt_verwirft_den_vorgang(self, _grenzen):
        zustand = _zustand()
        assert await discard_stale_approval(
            _SESSION, _req("ja, aber nenn es anders"), zustand) is True
        assert "_pending_write" not in zustand["entities"]

    @pytest.mark.asyncio
    async def test_eine_direktaktion_verwirft_den_vorgang(self, _grenzen):
        zustand = _zustand()
        assert await discard_stale_approval(
            _SESSION, _req("ja", action="browse_collection"), zustand) is True
        assert "_pending_write" not in zustand["entities"]

    @pytest.mark.asyncio
    async def test_eine_glatte_zustimmung_laesst_den_vorgang_stehen(self, _grenzen):
        # Den Rest entscheidet die Einlösung — oder, ohne gemerkte Argumente,
        # der Fingerabdruck-Weg im Tool-Loop. Beide brauchen den Vorgang noch.
        _mcp, update, _s = _grenzen
        zustand = _zustand()
        assert await discard_stale_approval(_SESSION, _req(), zustand) is False
        assert "_pending_write" in zustand["entities"]
        assert update.calls == []

    @pytest.mark.asyncio
    async def test_ohne_vorgang_wird_nichts_geschrieben(self, _grenzen):
        _mcp, update, _s = _grenzen
        zustand = {"persona_id": "P-AND", "entities": {}}
        assert await discard_stale_approval(
            _SESSION, _req("such mir was zu Optik"), zustand) is False
        assert update.calls == []

    @pytest.mark.asyncio
    async def test_ein_hintergrund_zug_verwirft_nur_im_speicher(self, _grenzen):
        # Befund 2026-10-08: ein stummer Kontext-Ping verwarf den Vorgang in
        # der Datenbank, und das „bestätigen“ danach traf nichts mehr an. Im
        # Zug selbst ist er weg — einlösen kann ein Ping nichts —, die Zeile
        # schreibt nur, wer etwas zeigt.
        _mcp, update, _s = _grenzen
        zustand = _zustand()
        assert await discard_stale_approval(
            _SESSION, _req("[context-open]"), zustand, hintergrund=True) is True
        assert "_pending_write" not in zustand["entities"]
        assert update.calls == []


class TestFremderAufrufer:
    """Ein offener Vorgang gehört dem Aufrufer, der ihn auslöste (Paket 4, A1).

    Der Schlüssel des MCP-Servers ist an keine Identität gebunden. Ohne diese
    Bindung löste ein „ja“ im Folgezug OHNE Anmeldung eine Vorschau ein, die
    unter Anmeldung entstand — und der Aufruf liefe mit dem Dienst-Block der
    Anlage (Gegenprüfung des externen Audits, F05).
    """

    @pytest.mark.asyncio
    async def test_ein_anderer_aufrufer_verwirft_den_vorgang(self, monkeypatch, _grenzen):
        _mcp, update, _s = _grenzen
        zustand = _zustand(caller="person-a")
        monkeypatch.setattr(wa_mod, "aufrufer_kennung", lambda: "")
        assert await discard_stale_approval(_SESSION, _req(), zustand) is True
        assert "_pending_write" not in zustand["entities"]
        assert len(update.calls) == 1

    @pytest.mark.asyncio
    async def test_derselbe_aufrufer_behaelt_den_vorgang(self, monkeypatch, _grenzen):
        zustand = _zustand(caller="person-a")
        monkeypatch.setattr(wa_mod, "aufrufer_kennung", lambda: "person-a")
        assert await discard_stale_approval(_SESSION, _req(), zustand) is False
        assert "_pending_write" in zustand["entities"]

    @pytest.mark.asyncio
    async def test_ein_vorgang_ohne_kennzeichen_gilt_als_fremd(self, monkeypatch, _grenzen):
        # Vor dem Deploy gemerkte Vorgänge tragen kein Kennzeichen.
        zustand = _zustand()
        del zustand["entities"]["_pending_write"]["caller"]
        monkeypatch.setattr(wa_mod, "aufrufer_kennung", lambda: "")
        assert await discard_stale_approval(_SESSION, _req(), zustand) is True

    @pytest.mark.asyncio
    async def test_die_einloesung_ruft_fuer_einen_fremden_vorgang_nichts(
            self, monkeypatch, _grenzen):
        # Zweite Wache am Einlöse-Weg selbst: Wer ohne den Verfall in ``setup``
        # hierher kommt, löst trotzdem nichts Fremdes ein.
        mcp, _u, _s = _grenzen
        zustand = _zustand(caller="person-a")
        monkeypatch.setattr(wa_mod, "aufrufer_kennung", lambda: "")
        assert await redeem_write_approval(_SESSION, _req(), zustand) is None
        assert mcp.calls == []

    @pytest.mark.asyncio
    async def test_derselbe_aufrufer_loest_ein(self, monkeypatch, _grenzen):
        mcp, _u, _s = _grenzen
        zustand = _zustand(caller="person-a")
        monkeypatch.setattr(wa_mod, "aufrufer_kennung", lambda: "person-a")
        assert await redeem_write_approval(_SESSION, _req(), zustand) is not None
        assert len(mcp.calls) == 1


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
    async def test_der_verbrauch_steht_in_der_db_bevor_gerufen_wird(self, monkeypatch):
        # Audit 2026-09-29, B-M3: Bricht der Zug während des MCP-Aufrufs ab
        # (Absturz, Neustart des Workers), darf der Merkposten nicht mehr in
        # der Datenbank stehen. Sonst setzte ein zweites „ja" dieselbe
        # Änderung erneut ab.
        folge: list[str] = []

        async def update(_session, _sid, **kwargs):
            offen = "_pending_write" in kwargs.get("entities", {})
            folge.append("gespeichert mit Vorgang" if offen else "gespeichert")

        async def mcp(_tool, _args):
            folge.append("aufruf")
            return _SERVERTEXT, ""

        monkeypatch.setattr(wa_mod, "update_session", update)
        monkeypatch.setattr(wa_mod, "save_message", _Spy())
        monkeypatch.setattr(wa_mod, "call_mcp_tool_status", mcp)
        monkeypatch.setattr(wa_mod, "schreiben_erlaubt", lambda: True)  # angemeldet
        await redeem_write_approval(_SESSION, _req(), _zustand())
        assert folge[:2] == ["gespeichert", "aufruf"]

    @pytest.mark.asyncio
    async def test_ein_zweites_ja_loest_nichts_erneut_aus(self, _grenzen):
        mcp, _u, _s = _grenzen
        zustand = _zustand()
        await redeem_write_approval(_SESSION, _req(), zustand)
        assert await redeem_write_approval(_SESSION, _req(), zustand) is None
        assert len(mcp.calls) == 1

    @pytest.mark.asyncio
    async def test_die_vorbereitete_anfrage_wird_mit_gespeichert(self, monkeypatch, _grenzen):
        """Review Paket 7 (MAJOR 7): reißt beim „ja“ der Strom ab, holt das Widget die
        Antwort aus dem Verlauf — die Anfrage muss dort stehen, der Vorgang ist schon
        verbraucht und ein zweites „ja“ hilft nicht."""
        from boerdi.domain.prepared_write import VERLAUF_SCHLUESSEL, PreparedWrite

        vorbereitet = PreparedWrite(method="POST", path="/edu-sharing/rest/y", body=None,
                                    done_message="Angelegt.")
        monkeypatch.setattr(wa_mod, "get_prepared_writes", lambda: [vorbereitet])
        _mcp, _u, save = _grenzen
        antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
        assert antwort is not None and antwort.prepared_write is not None
        debug = save.calls[0][1]["debug"]
        assert debug[VERLAUF_SCHLUESSEL]["path"] == "/edu-sharing/rest/y"

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


class TestFreieZustimmung:
    """Paket 10, A-6: ein „ja“ außerhalb der Erlaubnisliste prüft ein kurzer LLM-Aufruf.

    Einmal je Zug, im ersten Knoten; Vorlauf und Werkzeug-Schleife lesen das Urteil.
    """

    @pytest.fixture
    def _urteil(self, monkeypatch):
        from boerdi.services import zustimmung_pruefen as zp
        aufrufe: list[tuple[str, str]] = []
        antwort = {"wert": True}

        async def _fake(nachricht, werkzeug):
            aufrufe.append((nachricht, werkzeug))
            return antwort["wert"]

        monkeypatch.setattr(zp, "_llm_urteil", _fake)
        return aufrufe, antwort

    @pytest.mark.asyncio
    async def test_freie_zustimmung_loest_ein(self, _grenzen, _urteil):
        mcp, _u, _s = _grenzen
        aufrufe, _a = _urteil
        zustand = _zustand()
        assert await discard_stale_approval(_SESSION, _req("ja, rein damit"), zustand) is False
        assert await redeem_write_approval(_SESSION, _req("ja, rein damit"), zustand) is not None
        assert mcp.calls[0][0][0] == _WERKZEUG
        assert aufrufe == [("ja, rein damit", _WERKZEUG)]

    @pytest.mark.asyncio
    async def test_ohne_zustimmung_des_modells_faellt_der_vorgang(self, _grenzen, _urteil):
        mcp, _u, _s = _grenzen
        _aufrufe, antwort = _urteil
        antwort["wert"] = False
        zustand = _zustand()
        assert await discard_stale_approval(_SESSION, _req("ja, rein damit"), zustand) is True
        assert await redeem_write_approval(_SESSION, _req("ja, rein damit"), zustand) is None
        assert mcp.calls == []

    @pytest.mark.asyncio
    async def test_ein_veto_fragt_das_modell_nicht(self, _grenzen, _urteil):
        aufrufe, _a = _urteil
        zustand = _zustand()
        assert await discard_stale_approval(_SESSION, _req("Freigabe aufgehoben"), zustand)
        assert aufrufe == []

    @pytest.mark.asyncio
    async def test_ohne_vorgang_oder_als_aktion_fragt_niemand(self, _grenzen, _urteil):
        aufrufe, _a = _urteil
        await discard_stale_approval(_SESSION, _req("ja, rein damit"), {"entities": {}})
        await discard_stale_approval(_SESSION, _req("ja, rein", action="x"), _zustand())
        await discard_stale_approval(
            _SESSION, _req("ja, rein damit"), _zustand(), hintergrund=True)
        assert aufrufe == []

    @pytest.mark.asyncio
    async def test_freie_zustimmung_zu_fremder_vorschau_bringt_den_hinweis(
            self, monkeypatch, _grenzen, _urteil):
        from boerdi.services import abnahme_hinweis
        zustand = _zustand(caller="p:andere")
        assert await discard_stale_approval(_SESSION, _req("ja, rein damit"), zustand)
        assert zustand[abnahme_hinweis.MERKER] is True


_VORSCHAU = "Das Material „Arbeitsblatt Bruchrechnung“ wird angelegt."


def _mit_vorschau(zustand: dict) -> dict:
    """Der Merkposten trägt seit Review 19-5 (2) eine Kopie der gezeigten Vorschau."""
    zustand["entities"]["_pending_write"]["vorschau"] = _VORSCHAU
    return zustand


class TestUnklareZustimmung:
    """Paket 19, M-2: Fehlschlag ist keine Antwort. Konnte das Modell die freie Antwort nicht
    beurteilen (Frist, ausgelastet, Anbieterfehler), bleibt der Vorgang stehen; die Person
    bekommt die „ausgelastet“-Blase und den Bestätigungs-Chip. Geschrieben wird nie."""

    @pytest.fixture
    def _echtes_urteil(self, monkeypatch):
        from boerdi.services import zustimmung_pruefen as zp
        monkeypatch.setattr(zp, "_llm_urteil", _ECHTES_URTEIL)

        def modell_scheitert(fehler: BaseException) -> None:
            async def chat_completion(**_kwargs):
                raise fehler
            monkeypatch.setattr(zp.llm, "chat_completion", chat_completion)
        return modell_scheitert

    @pytest.fixture
    def _zug(self):
        from boerdi.services import llm_parallel
        llm_parallel.binde_zug()
        yield llm_parallel
        llm_parallel._zug.set(None)

    @pytest.mark.parametrize("fehler", [
        TimeoutError(),
        litellm.RateLimitError(message="429", llm_provider="openai", model="gpt-x"),
        LlmAusgelastet("voll"),
    ], ids=["frist", "anbieterfehler", "ausgelastet"])
    @pytest.mark.asyncio
    async def test_der_vorgang_bleibt_und_nichts_wird_geschrieben(
            self, _grenzen, _echtes_urteil, _zug, fehler):
        mcp, update, save = _grenzen
        _echtes_urteil(fehler)
        zustand = _mit_vorschau(_zustand())
        assert await discard_stale_approval(_SESSION, _req("ja, rein damit"),
                                            zustand) is False
        assert "_pending_write" in zustand["entities"]  # im Speicher …
        # … in der Datenbank verworfen (Review 19-5, 1): endet der Zug vor dem Vorlauf
        # (Tour, Drosselung), löst kein späteres „ok“ den alten Vorgang ein.
        assert "_pending_write" not in update.calls[-1][1]["entities"]

        antwort = await redeem_write_approval(_SESSION, _req("ja, rein damit"), zustand)
        assert antwort is not None
        assert mcp.calls == []  # unklar schreibt NIE
        assert antwort.content.startswith(bot_text("de", "error.llmBusy"))
        assert bot_text("de", "write.consentUnclear") in antwort.content
        assert antwort.quick_replies == [bot_text("de", "action.write.confirmChip")]
        # Review 19-5 (2): die Vorschau steht wieder darunter — der Chip meint genau sie.
        assert [d.kind for d in antwort.inline_documents] == ["schreib_vorschau"]
        assert _VORSCHAU in antwort.inline_documents[0].content
        assert _zug.blase_gezeigt()
        assert "_pending_write" in zustand["entities"]
        # Erst jetzt, mit gezeigtem Chip, steht der Vorgang wieder in der Datenbank.
        assert "_pending_write" in update.calls[-1][1]["entities"]
        assert len(save.calls) == 1  # die Blase steht im Verlauf

    @pytest.mark.asyncio
    async def test_der_bestaetigungs_chip_loest_danach_ein(self, _grenzen, _echtes_urteil, _zug):
        mcp, _u, _s = _grenzen
        _echtes_urteil(TimeoutError())
        zustand = _mit_vorschau(_zustand())
        await discard_stale_approval(_SESSION, _req("ja, rein damit"), zustand)
        await redeem_write_approval(_SESSION, _req("ja, rein damit"), zustand)
        # Folgezug: der Chip ist ein Listenwort — kein Modell nötig.
        folge = {"persona_id": "P-AND", "entities": dict(zustand["entities"])}
        chip = bot_text("de", "action.write.confirmChip")
        assert await discard_stale_approval(_SESSION, _req(chip), folge) is False
        assert await redeem_write_approval(_SESSION, _req(chip), folge) is not None
        assert mcp.calls[0][0][0] == _WERKZEUG

    @pytest.mark.asyncio
    async def test_ein_gedrosselter_zug_laesst_keinen_vorgang_in_der_datenbank(
            self, monkeypatch, _grenzen, _echtes_urteil):
        """Review 19-5 (1): der Vorlauf drosselt VOR der Einlösung — der Zug endet ohne Chip."""
        from types import SimpleNamespace

        from boerdi.graph.nodes import preflight as pf
        from boerdi.graph.state import TurnContext

        _mcp, update, _s = _grenzen
        _echtes_urteil(TimeoutError())

        async def gedrosselt(*_a, **_k):
            return SimpleNamespace(allowed=False, reason="session", blocked_message="Halt")

        async def kein_ereignis(*_a, **_k):
            return None

        monkeypatch.setattr(pf, "check_rate_limit", gedrosselt)
        monkeypatch.setattr(pf, "log_safety_event", kein_ereignis)
        ctx = TurnContext(req=_req("ja, rein damit"))
        ctx.session_state = _mit_vorschau(_zustand())
        await discard_stale_approval(_SESSION, ctx.req, ctx.session_state)
        await pf.preflight(ctx, _SESSION)
        assert ctx.early_response.content == "Halt"
        assert update.calls and all(
            "_pending_write" not in c[1]["entities"] for c in update.calls)

    @pytest.mark.asyncio
    async def test_ein_tour_zug_laesst_keinen_vorgang_in_der_datenbank(
            self, _grenzen, _echtes_urteil):
        """Review 19-5 (1): ein Zug, der vor dem Vorlauf endet (die Tour schreibt nur
        ``tour_state``), hinterlässt den Stand aus ``setup`` — ohne Vorgang."""
        _mcp, update, _s = _grenzen
        _echtes_urteil(TimeoutError())
        zustand = _mit_vorschau(_zustand())
        await discard_stale_approval(_SESSION, _req("ja, rein damit"), zustand)
        assert len(update.calls) == 1
        assert "_pending_write" not in update.calls[0][1]["entities"]

    @pytest.mark.asyncio
    async def test_ohne_gemerkte_vorschau_kein_chip(self, _grenzen, _echtes_urteil, _zug):
        """Review 19-5 (2): ein Chip ohne sichtbare Vorschau hieße „ja“ zu Unbekanntem — ein
        Vorgang ohne Kopie (vor diesem Stand gemerkt) fällt, die Blase bleibt."""
        mcp, update, _s = _grenzen
        _echtes_urteil(TimeoutError())
        zustand = _zustand()
        await discard_stale_approval(_SESSION, _req("ja, rein damit"), zustand)
        antwort = await redeem_write_approval(_SESSION, _req("ja, rein damit"), zustand)
        assert antwort is not None and antwort.quick_replies == []
        assert antwort.content == bot_text("de", "error.llmBusy")
        assert "_pending_write" not in zustand["entities"]
        assert "_pending_write" not in update.calls[-1][1]["entities"]
        assert mcp.calls == []

    @pytest.mark.asyncio
    async def test_ein_abgelaufener_vorgang_bekommt_keinen_chip(
            self, _grenzen, _echtes_urteil):
        """Review 19-5 (3): nach der Frist löste der Chip nichts mehr ein — der Vorgang fällt."""
        from boerdi.domain.write_confirm import TOKEN_TTL_SECONDS
        mcp, _u, _s = _grenzen
        _echtes_urteil(TimeoutError())
        zustand = _mit_vorschau(_zustand(alter=TOKEN_TTL_SECONDS + 5))
        await discard_stale_approval(_SESSION, _req("ja, rein damit"), zustand)
        assert await redeem_write_approval(_SESSION, _req("ja, rein damit"), zustand) is None
        assert "_pending_write" not in zustand["entities"]
        assert mcp.calls == []

    @pytest.mark.asyncio
    async def test_ein_dauerhafter_fehler_verwirft_wie_frueher(self, _grenzen, _echtes_urteil):
        _echtes_urteil(RuntimeError("kaputt"))
        zustand = _mit_vorschau(_zustand())
        assert await discard_stale_approval(_SESSION, _req("ja, rein damit"), zustand) is True
        assert "_pending_write" not in zustand["entities"]

    @pytest.mark.asyncio
    async def test_unklar_liest_kein_leser_als_zustimmung(self, _grenzen, _echtes_urteil):
        from boerdi.services import zustimmung_pruefen as zp
        _echtes_urteil(TimeoutError())
        zustand = _zustand()
        await discard_stale_approval(_SESSION, _req("ja, rein damit"), zustand)
        # Vorlauf und Werkzeug-Schleife lesen den Merker — unklar ist nie Zustimmung.
        assert zustand[zp.MERKER] is False
        assert not zp.zugestimmt(zustand, "ja, rein damit")

    @pytest.mark.asyncio
    async def test_eine_klare_ablehnung_verwirft_wie_bisher(self, _grenzen, monkeypatch):
        from boerdi.services import zustimmung_pruefen as zp

        async def nein(_n, _w):
            return False

        monkeypatch.setattr(zp, "_llm_urteil", nein)
        mcp, update, _s = _grenzen
        zustand = _zustand()
        assert await discard_stale_approval(_SESSION, _req("hm, eher nicht so"), zustand)
        assert "_pending_write" not in zustand["entities"]
        assert len(update.calls) == 1
        assert await redeem_write_approval(_SESSION, _req("hm, eher nicht so"), zustand) is None
        assert mcp.calls == []

    @pytest.mark.asyncio
    async def test_unklar_bei_fremdem_aufrufer_verwirft(
            self, monkeypatch, _grenzen, _echtes_urteil):
        _echtes_urteil(TimeoutError())
        zustand = _zustand(caller="p:andere")
        assert await discard_stale_approval(_SESSION, _req("ja, rein damit"), zustand)
        assert "_pending_write" not in zustand["entities"]

    @pytest.mark.asyncio
    async def test_unklar_ohne_schreibrecht_bietet_keinen_chip(
            self, monkeypatch, _grenzen, _echtes_urteil):
        mcp, _u, _s = _grenzen
        monkeypatch.setattr(wa_mod, "schreiben_erlaubt", lambda: False)
        _echtes_urteil(TimeoutError())
        zustand = _zustand()
        await discard_stale_approval(_SESSION, _req("ja, rein damit"), zustand)
        assert await redeem_write_approval(
            _SESSION, _req("ja, rein damit"), zustand) is None
        assert "_pending_write" not in zustand["entities"]
        assert mcp.calls == []
