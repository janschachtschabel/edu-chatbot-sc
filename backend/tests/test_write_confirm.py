"""E1: der Bestätigungs-Wall vor den kuratierenden Werkzeugen.

Gemessen 2026-08-10 am echten Server: jedes schreibende Werkzeug ist
zweistufig. Ohne ``confirmToken`` schreibt es nichts, sondern liefert die
Vorschau plus einen Schlüssel; erst ein zweiter Aufruf mit diesem Schlüssel
führt aus. Der Schlüssel ist an den Fingerabdruck der Änderung gebunden, gilt
zehn Minuten und genau einmal.

Diese Bindung verhindert, dass eine genehmigte Änderung gegen eine andere
eingetauscht wird. Sie verhindert **nicht**, dass derselbe Aufrufer beide
Schritte macht — der Server nimmt an, dazwischen stehe ein Mensch. Bei einem
Chat-Client mit fünf Werkzeug-Iterationen pro Zug steht dort niemand.

Der Wall stellt den Menschen wieder hinein, und zwar an der einzigen Stelle,
an der er im Chat sicher steht: am **Zugwechsel**. Deshalb prüfen die Tests
unten zwei getrennte Dinge — die Identität eines Vorhabens (reine Domäne) und
die Zug-Regel (Naht im Tool-Loop).
"""

from __future__ import annotations

import time

from boerdi.domain.write_confirm import (
    CONFIRMABLE_TOOLS,
    CURATION_TOOLS,
    MAX_REMEMBERED_ARGS_BYTES,
    TOKEN_PLACEHOLDER,
    TOKEN_TTL_SECONDS,
    change_fingerprint,
    confirmed_args,
    extract_confirm_token,
    is_affirmation,
    is_confirmable,
    is_expired,
    preview_for_display,
    redact_confirm_token,
    remember_pending,
    strip_confirm_token,
    token_for,
)

# Der Wortlaut stammt aus ``previewReply`` (curation-shared.ts) des Servers —
# abgeschrieben statt erfunden, denn genau an diesem Text hängt die Extraktion.
_ECHTE_VORSCHAU = """Bitte prüfen — bisher wurde nichts geändert:

Sammlung anlegen: „Bruchrechnung Klasse 6"
  Titel: (neu) Bruchrechnung Klasse 6

Die Sammlung wird angelegt. Dazu denselben Aufruf mit confirmToken: \
Ax9-_QmZ2kLpWvRt7NbYcE4s wiederholen.
Der Schlüssel gilt einmalig und zehn Minuten lang."""

_TOKEN = "Ax9-_QmZ2kLpWvRt7NbYcE4s"


# ── Der Schlüssel kommt nie vom Modell ───────────────────────────────────


class TestSchluesselNieVomModell:
    def test_mitgeschickter_schluessel_wird_entfernt(self):
        # Ein Modell, das sich einen Schlüssel ausdenkt oder einen aus dem
        # Verlauf aufsammelt, darf damit nichts auslösen.
        sauber = strip_confirm_token(
            "wlo_create_collection",
            {"title": "Bruchrechnung", "confirmToken": "geraten"},
        )
        assert sauber == {"title": "Bruchrechnung"}

    def test_originalargumente_bleiben_unangetastet(self):
        # Reine Funktion: der Aufrufer im Tool-Loop arbeitet mit dem Ergebnis
        # weiter, das Eingabe-Dict gehoert ihm.
        args = {"title": "x", "confirmToken": "y"}
        strip_confirm_token("wlo_create_collection", args)
        assert args == {"title": "x", "confirmToken": "y"}

    def test_lesende_werkzeuge_bleiben_unberuehrt(self):
        # ``wlo_list_suggestions`` hat gar keinen confirmToken im Schema.
        args = {"nodeId": "abc", "status": "PENDING"}
        assert strip_confirm_token("wlo_list_suggestions", args) == args

    def test_suchwerkzeuge_bleiben_unberuehrt(self):
        args = {"query": "confirmToken"}
        assert strip_confirm_token("search_wlo_content", args) == args


# ── Der Vorschautext des Servers ─────────────────────────────────────────


class TestVorschauText:
    def test_schluessel_wird_gefunden(self):
        assert extract_confirm_token(_ECHTE_VORSCHAU) == _TOKEN

    def test_ohne_schluessel_kein_treffer(self):
        assert extract_confirm_token("Die Sammlung wurde angelegt.") is None

    def test_schluessel_verlaesst_die_nachrichtenkette_nicht(self):
        gekuerzt = redact_confirm_token(_ECHTE_VORSCHAU)
        assert _TOKEN not in gekuerzt
        assert TOKEN_PLACEHOLDER in gekuerzt

    def test_die_vorschau_selbst_bleibt_lesbar(self):
        # Der Nutzer soll sehen, WAS passieren wuerde — nur der Schluessel geht.
        gekuerzt = redact_confirm_token(_ECHTE_VORSCHAU)
        assert "Bitte prüfen" in gekuerzt
        assert "Bruchrechnung Klasse 6" in gekuerzt

    def test_text_ohne_schluessel_bleibt_wortgleich(self):
        # Kein Schluessel, keine Aenderung: Erfolgsmeldungen und Absagen des
        # Servers duerfen nicht angefasst werden.
        text = "Die Sammlung wurde angelegt (nodeId abc-123)."
        assert redact_confirm_token(text) == text


# ── Identität eines Vorhabens (reine Domäne) ─────────────────────────────
# Die ZUG-Regel steht nicht hier, sondern in der Naht: diese Funktionen
# beantworten nur „ist das dasselbe Vorhaben?".


class TestVorhabenIdentitaet:
    def test_gleiche_argumente_gleicher_fingerabdruck(self):
        a = change_fingerprint("wlo_rename_collection", {"nodeId": "n1", "title": "Neu"})
        b = change_fingerprint("wlo_rename_collection", {"title": "Neu", "nodeId": "n1"})
        assert a == b, "Die Reihenfolge der Argumente ist keine Eigenschaft des Vorhabens"

    def test_anderer_wert_anderer_fingerabdruck(self):
        a = change_fingerprint("wlo_rename_collection", {"nodeId": "n1", "title": "Neu"})
        b = change_fingerprint("wlo_rename_collection", {"nodeId": "n1", "title": "Anders"})
        assert a != b

    def test_anderes_werkzeug_anderer_fingerabdruck(self):
        a = change_fingerprint("wlo_delete_collection", {"nodeId": "n1"})
        b = change_fingerprint("wlo_delete_content", {"nodeId": "n1"})
        assert a != b

    def test_schluessel_zaehlt_nicht_zur_identitaet(self):
        # Sonst wuerde der Bestaetigungsaufruf nie zu seiner eigenen Vorschau
        # passen — er traegt den Schluessel, die Vorschau trug ihn nicht.
        ohne = change_fingerprint("wlo_delete_content", {"nodeId": "n1"})
        mit = change_fingerprint("wlo_delete_content", {"nodeId": "n1", "confirmToken": "x"})
        assert ohne == mit

    def test_schluessel_nur_fuer_dasselbe_vorhaben(self):
        # Feste Uhrzeit, und Ablesen im selben Augenblick: hier geht es um die
        # Identitaet eines Vorhabens, nicht um die Frist (die steht in
        # ``TestFrist``). Ein ``time.time()`` machte den Test von etwas
        # abhaengig, worueber er nichts sagt.
        offen = remember_pending(
            "wlo_rename_collection", {"nodeId": "n1", "title": "Neu"}, _TOKEN, now=1000.0)
        assert token_for(offen, "wlo_rename_collection",
                         {"nodeId": "n1", "title": "Neu"}, now=1000.0) == _TOKEN
        assert token_for(offen, "wlo_rename_collection",
                         {"nodeId": "n1", "title": "X"}, now=1000.0) is None
        assert token_for(offen, "wlo_delete_collection",
                         {"nodeId": "n1"}, now=1000.0) is None

    def test_ohne_offenes_vorhaben_kein_schluessel(self):
        assert token_for(None, "wlo_delete_content", {"nodeId": "n1"}, now=1000.0) is None


# ── Wächter der Gegenrichtung ────────────────────────────────────────────
# Jedes kuratierende Werkzeug der Registry muss hier eingeordnet sein. Ein neu
# aufgenommenes faellt damit auf, statt still ohne Wall zu laufen.


def test_jedes_kurationswerkzeug_der_registry_ist_eingeordnet():
    from pathlib import Path

    import yaml

    # Seed-Pfad wie im Testbestand (``test_config_seed_tree.py``).
    pfad = Path(__file__).resolve().parents[1] / "seeds" / "05-knowledge" / "mcp-servers.yaml"
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    registry = {t for s in daten["servers"] for t in s.get("tools", [])}
    # ``wlo_health_check``/``wlo_auth_status`` sind Betriebs-Sonden, keine
    # Kuration — sie stehen bewusst nicht in CURATION_TOOLS.
    betrieb = {"wlo_health_check", "wlo_auth_status"}
    kuratierend = {t for t in registry if t.startswith("wlo_")} - betrieb
    assert kuratierend == set(CURATION_TOOLS), (
        "Registry und Wall sind auseinandergelaufen. Fehlend im Wall: "
        f"{sorted(kuratierend - set(CURATION_TOOLS))}; nur im Wall: "
        f"{sorted(set(CURATION_TOOLS) - kuratierend)}"
    )


def test_nur_das_lesende_werkzeug_ist_nicht_bestaetigungspflichtig():
    # Live gemessen: 13 der 14 fuehren einen ``confirmToken``; allein
    # ``wlo_list_suggestions`` nicht, weil es nichts aendert.
    assert set(CURATION_TOOLS) - set(CONFIRMABLE_TOOLS) == {"wlo_list_suggestions"}
    assert is_confirmable("wlo_delete_content")
    assert not is_confirmable("wlo_list_suggestions")
    assert not is_confirmable("search_wlo_content")


# ── S2: derselbe Text, aber für Augen ────────────────────────────────────


class TestVorschauFuerDenNutzer:
    def test_der_maschinen_schwanz_faellt_weg(self):
        gezeigt = preview_for_display(redact_confirm_token(_ECHTE_VORSCHAU))
        assert "confirmToken" not in gezeigt, "Maschinen-Anweisung, kein Nutzertext"
        assert "einmalig und zehn Minuten" not in gezeigt
        assert TOKEN_PLACEHOLDER not in gezeigt

    def test_alles_andere_bleibt_wortgleich(self):
        gezeigt = preview_for_display(redact_confirm_token(_ECHTE_VORSCHAU))
        assert gezeigt.startswith("Bitte prüfen — bisher wurde nichts geändert:")
        assert "Bruchrechnung Klasse 6" in gezeigt
        assert "Die Sammlung wird angelegt." in gezeigt, (
            "Was passieren wuerde, steht VOR der Maschinen-Anweisung im selben Satz "
            "— es darf nicht mit abgeschnitten werden"
        )

    def test_text_ohne_schwanz_bleibt_unveraendert(self):
        # Absagen und Ausfuehrungsmeldungen tragen den Schwanz nicht. Sie
        # duerfen die Funktion unveraendert passieren.
        for roh in ("Die Sammlung wurde angelegt.",
                    "Keine Änderung — die gewünschten Werte stehen bereits so im Datensatz.",
                    ""):
            assert preview_for_display(roh) == roh

    def test_unbekannter_wortlaut_verstuemmelt_nichts(self):
        # Aendert der Server seinen Schwanz, findet die Funktion ihn nicht mehr.
        # Die Folge muss „etwas zu viel gezeigt" sein und nicht „etwas zu wenig":
        # ein verstuemmelter Unterschied waere eine Abnahme ueber unvollstaendiger
        # Grundlage — genau das, was die Box verhindern soll.
        fremd = "Bitte prüfen:\nTitel: (leer) → „X“\nBestätige mit dem Schlüssel unten."
        assert preview_for_display(fremd) == fremd


# ── Die Naht: hier steht die Zug-Regel ───────────────────────────────────
# Der Loop-Harness liegt in ``tests/test_tool_loop.py`` (``tests`` ist ein
# Paket, vgl. ``tests.eval_fakes``); ihn nachzubauen waere eine zweite Kopie
# derselben Attrappen.

_WERKZEUG = "wlo_create_collection"
_ARGS = '{"title": "Bruchrechnung Klasse 6"}'


def _lauf(monkeypatch, aufrufe, *, session_state=None, ergebnis=_ECHTE_VORSCHAU,
          nachricht=None, werkzeug=_WERKZEUG):
    from tests.test_tool_loop import _OutcomeFake, _resp_text, _resp_tools, _run_loop

    outcome = _OutcomeFake({werkzeug: ergebnis})
    antworten = [_resp_tools([a]) for a in aufrufe] + [_resp_text("fertig")]
    extra = {}
    if nachricht is not None:
        # Ohne ``nachricht`` bleibt der Harness-Standard (nur ``system``) —
        # dann gibt es keine Zustimmung, und die Alt-Tests messen weiter genau
        # den Fingerabdruck-Weg, den sie messen wollen.
        extra["messages"] = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": nachricht},
        ]
    _fake, _result, st = _run_loop(
        monkeypatch,
        antworten,
        outcome=outcome,
        active_tools=[{"type": "function", "function": {"name": werkzeug}}],
        session_state=session_state if session_state is not None else {},
        **extra,
    )
    return outcome, st


class TestNaht:
    def test_vorschau_schluessel_erreicht_das_modell_nicht(self, monkeypatch):
        outcome, st = _lauf(monkeypatch, [("tc1", _WERKZEUG, _ARGS)])
        gesehen = [m for m in st["messages"] if m.get("role") == "tool"][0]["content"]
        assert _TOKEN not in gesehen, "Der Schlüssel steht in der Nachrichtenkette"
        assert TOKEN_PLACEHOLDER in gesehen
        assert "Bruchrechnung Klasse 6" in gesehen, "Die Vorschau selbst muss lesbar bleiben"

    def test_vorschau_legt_den_vorgang_ab(self, monkeypatch):
        _outcome, st = _lauf(monkeypatch, [("tc1", _WERKZEUG, _ARGS)])
        offen = st["session_state"]["entities"]["_pending_write"]
        assert offen["token"] == _TOKEN
        assert offen["tool"] == _WERKZEUG

    def test_offener_vorgang_liegt_im_gespeicherten_teil(self, monkeypatch):
        # DER Befund (2026-08-11). ``session_state`` wird jeden Zug NEU aus
        # fuenf Spalten gebaut (``graph/nodes/setup.py``), und
        # ``update_session`` schreibt genau diese fuenf — darunter ``entities``,
        # aber KEINEN Sammeltopf fuer die oberste Ebene. Ein Merkposten dort
        # stirbt mit der Anfrage: ``_pending_at_turn_start`` waere im Betrieb
        # immer ``None`` und keine Bestaetigung je einloesbar.
        #
        # Die uebrigen zugueberdauernden Merker liegen deshalb alle in
        # ``entities`` (``_last_pattern``, ``_frame``, ``_canvas_material_type``),
        # und der Debug-Auszug streicht ``_``-Schluessel wieder heraus — der
        # Schluessel bleibt also gespeichert UND unsichtbar.
        _outcome, st = _lauf(monkeypatch, [("tc1", _WERKZEUG, _ARGS)])
        assert "_pending_write" in st["session_state"]["entities"]
        assert "_pending_write" not in st["session_state"], (
            "Oberste Ebene wird nicht gespeichert — dort ist der Merkposten wertlos"
        )

    def test_vorschautext_steht_fuer_die_antwort_bereit(self, monkeypatch):
        # S1: Der Server schreibt die Abnahme bereits als fertigen deutschen
        # Unterschied — bisher endete sie in der Nachrichtenkette des Modells.
        # Damit sie den Nutzer erreichen kann, muss sie den Zug ueberleben.
        # Abgelegt wird die REDIGIERTE Fassung: was hier liegt, geht in die
        # sichtbare Antwort, und der Schluessel darf da nie hin.
        _outcome, st = _lauf(monkeypatch, [("tc1", _WERKZEUG, _ARGS)])
        vorschau = st["session_state"]["_write_preview"]
        assert "Bruchrechnung Klasse 6" in vorschau
        assert _TOKEN not in vorschau, "Der Schluessel darf nicht mitreisen"
        assert TOKEN_PLACEHOLDER in vorschau

    def test_eine_ausfuehrung_erzeugt_keine_vorschau(self, monkeypatch):
        # Gegenprobe: nach dem Ja steht kein Vorschautext mehr bereit. Sonst
        # zeigte die Antwort auf die AUSGEFUEHRTE Aenderung noch einmal den
        # Kasten „bisher wurde nichts geaendert" — die Unwahrheit im
        # unguenstigsten Moment.
        vorher = {"entities": {"_pending_write": remember_pending(
            _WERKZEUG, {"title": "Bruchrechnung Klasse 6"}, _TOKEN, now=time.time())}}
        _outcome, st = _lauf(
            monkeypatch, [("tc1", _WERKZEUG, _ARGS)],
            session_state=vorher, ergebnis="Die Sammlung wurde angelegt.",
        )
        assert not st["session_state"].get("_write_preview")

    def test_kein_schluessel_im_selben_zug(self, monkeypatch):
        # DER WALL. Zwei Aufrufe in EINEM Zug: der zweite darf keine
        # Ausfuehrung werden, sonst haette das Modell allein bestaetigt.
        outcome, _st = _lauf(
            monkeypatch,
            [("tc1", _WERKZEUG, _ARGS), ("tc2", _WERKZEUG, _ARGS)],
        )
        assert len(outcome.calls) == 2
        assert all("confirmToken" not in args for _n, args in outcome.calls)

    def test_bestaetigung_im_spaeteren_zug(self, monkeypatch):
        # Der Vorgang stammt aus einem frueheren Zug — dazwischen lag ein
        # Mensch, der die Vorschau gelesen hat.
        #
        # Eingespeist wird in ``entities`` und nicht auf oberster Ebene: nur
        # so kommt ein frueherer Zug hier ueberhaupt an. Bis 2026-08-11 stand
        # es hier oben — der Test war gruen und der Betrieb kaputt, weil die
        # Attrappe die Annahme des Codes teilte statt die Wirklichkeit.
        vorher = {"entities": {"_pending_write": remember_pending(
            _WERKZEUG, {"title": "Bruchrechnung Klasse 6"}, _TOKEN, now=time.time())}}
        outcome, st = _lauf(
            monkeypatch, [("tc1", _WERKZEUG, _ARGS)],
            session_state=vorher, ergebnis="Die Sammlung wurde angelegt.",
        )
        assert outcome.calls[0][1].get("confirmToken") == _TOKEN
        assert st["session_state"]["entities"].get("_pending_write") is None, (
            "Ein verbrauchter Vorgang muss weg — sonst laesst er sich erneut ausloesen"
        )

    def test_anderes_vorhaben_bekommt_keinen_schluessel(self, monkeypatch):
        vorher = {"entities": {"_pending_write": remember_pending(
            _WERKZEUG, {"title": "Etwas ganz anderes"}, _TOKEN, now=time.time())}}
        outcome, _st = _lauf(
            monkeypatch, [("tc1", _WERKZEUG, _ARGS)], session_state=vorher)
        assert "confirmToken" not in outcome.calls[0][1]

    def test_nicht_bestaetigter_vorgang_hinterlaesst_eine_spur(self, monkeypatch, caplog):
        # S0: Ein offener Vorgang DESSELBEN Werkzeugs, aber mit anderen
        # Argumenten. Der Wall haelt richtig — nur faellt die Bestaetigung
        # damit still auf eine NEUE Vorschau zurueck. Aus Sicht des Nutzers
        # kann das zweierlei heissen, und von hier aus sind beide nicht zu
        # unterscheiden:
        #   * er hat angepasst („nenn sie doch anders") — der Normalfall des
        #     zweiten Auftragsteils, kein Fehler;
        #   * das Modell hat im Bestaetigungszug ein Feld mehr oder weniger
        #     genannt — dann sagt der Nutzer „ja" und wird erneut gefragt.
        # Deshalb INFO und kein WARNING: aufgezeichnet, nicht angeklagt.
        vorher = {"entities": {"_pending_write": remember_pending(
            _WERKZEUG, {"title": "Bruchrechnung Klasse 6", "description": "Kurz"},
            _TOKEN, now=time.time())}}
        with caplog.at_level("INFO"):
            outcome, _st = _lauf(
                monkeypatch, [("tc1", _WERKZEUG, _ARGS)], session_state=vorher)
        assert "confirmToken" not in outcome.calls[0][1]
        assert _WERKZEUG in caplog.text, (
            "Ohne diese Zeile ist der Rueckfall auf eine neue Vorschau unsichtbar"
        )
        assert _TOKEN not in caplog.text, "Der Schluessel gehoert nie ins Protokoll"

    def test_ein_anderes_werkzeug_ist_kein_rueckfall(self, monkeypatch, caplog):
        # Gegenprobe zur Zeile oben: wer nach einer Vorschau etwas voellig
        # anderes tut, hat den Vorgang schlicht liegen lassen. Das ist der
        # Alltag und darf nichts melden — sonst steht die Zeile in jedem
        # zweiten Protokoll und sagt nichts mehr aus.
        vorher = {"entities": {"_pending_write": remember_pending(
            "wlo_delete_content", {"nodeId": "abc"}, _TOKEN, now=time.time())}}
        with caplog.at_level("INFO"):
            _outcome, _st = _lauf(
                monkeypatch, [("tc1", _WERKZEUG, _ARGS)], session_state=vorher)
        assert "wlo_delete_content" not in caplog.text

    def test_selbst_erfundener_schluessel_wird_entfernt(self, monkeypatch):
        outcome, _st = _lauf(
            monkeypatch,
            [("tc1", _WERKZEUG, '{"title": "X", "confirmToken": "ausgedacht"}')],
        )
        assert "confirmToken" not in outcome.calls[0][1]

    def test_absagen_des_servers_sind_keine_verdorbene_vorschau(self, monkeypatch, caplog):
        # Die drei Absagen (abgelaufen / andere Änderung / unbekannt) nennen
        # ``confirmToken`` ebenfalls — aber ohne Doppelpunkt („bitte den Aufruf
        # OHNE confirmToken wiederholen"). Sie duerfen weder eine Warnung
        # ausloesen noch veraendert werden.
        absage = (
            "Der Bestätigungsschlüssel ist abgelaufen (zehn Minuten). Bitte den "
            "Aufruf ohne confirmToken wiederholen, die Vorschau erneut prüfen "
            "und mit dem neuen Schlüssel bestätigen."
        )
        with caplog.at_level("WARNING"):
            _outcome, st = _lauf(
                monkeypatch, [("tc1", _WERKZEUG, _ARGS)], ergebnis=absage)
        gesehen = [m for m in st["messages"] if m.get("role") == "tool"][0]["content"]
        assert gesehen == absage, "Die Absage muss den Nutzer wortgleich erreichen"
        assert "confirmToken" not in caplog.text

    def test_veraenderter_vorschautext_faellt_auf(self, monkeypatch, caplog):
        # Gegenprobe: kuendigt der Server einen Schluessel an, den wir nicht
        # lesen koennen, ist das ein Ausfall — und er soll nicht still sein.
        with caplog.at_level("WARNING"):
            _outcome, st = _lauf(
                monkeypatch, [("tc1", _WERKZEUG, _ARGS)],
                ergebnis="Bitte mit confirmToken: {{neues-format}} wiederholen.")
        assert "confirmToken" in caplog.text
        assert st["session_state"].get("_pending_write") is None

    def test_suchwerkzeug_bleibt_unberuehrt(self, monkeypatch):
        from tests.test_tool_loop import _OutcomeFake, _resp_text, _resp_tools, _run_loop

        outcome = _OutcomeFake({"search_wlo_content": "treffer"})
        _f, _r, st = _run_loop(
            monkeypatch,
            [_resp_tools([("tc1", "search_wlo_content", '{"query": "x"}')]),
             _resp_text("fertig")],
            outcome=outcome,
            active_tools=[{"type": "function", "function": {"name": "search_wlo_content"}}],
        )
        assert [m for m in st["messages"] if m.get("role") == "tool"][0]["content"] == "treffer"
        assert "_pending_write" not in st["session_state"]


# ── E4: ein liegen gelassener Vorgang verfällt ───────────────────────────
#
# Der Merkposten überdauert bis zum Sitzungsende; entfernt wird er nur auf dem
# Bestätigungspfad oder durch eine neue Vorschau desselben Werkzeugs. Fragt
# jemand Stunden später zufällig EXAKT dasselbe erneut an, wurde bisher der
# alte Schlüssel eingesetzt — der Server lehnt ihn ab (er gilt zehn Minuten)
# und antwortet mit einer neuen Vorschau. Kein Loch, aber ein überflüssiger
# Werkzeugaufruf. Seit E4 steht die Frist auch auf unserer Seite.
#
# Die Uhr reicht der Aufrufer herein: ``domain/`` ist rein und hat keine.

class TestFrist:
    def _offen(self, now):
        return remember_pending(_WERKZEUG, {"title": "Bruchrechnung"}, _TOKEN, now=now)

    def test_der_merkposten_haelt_seinen_zeitpunkt_fest(self):
        assert self._offen(1000.0)["minted_at"] == 1000.0

    def test_innerhalb_der_frist_kommt_der_schluessel(self):
        offen = self._offen(1000.0)
        assert token_for(offen, _WERKZEUG, {"title": "Bruchrechnung"},
                         now=1000.0 + TOKEN_TTL_SECONDS - 1) == _TOKEN

    def test_nach_der_frist_kommt_keiner(self):
        offen = self._offen(1000.0)
        assert token_for(offen, _WERKZEUG, {"title": "Bruchrechnung"},
                         now=1000.0 + TOKEN_TTL_SECONDS) is None

    def test_ein_merkposten_ohne_zeitpunkt_gilt_als_abgelaufen(self):
        """Aufwärtspfad: was vor E4 abgelegt wurde, trägt keinen Zeitstempel.

        Nicht beweisbar frisch heisst nicht absetzen. Der Preis ist genau der
        eine überflüssige Aufruf, den E4 sonst spart, und nur für Merkposten
        aus der Sitzung, die beim Deploy gerade lief — die nächste Vorschau
        legt einen vollständigen ab.
        """
        alt = {"tool": _WERKZEUG, "token": _TOKEN,
               "fingerprint": change_fingerprint(_WERKZEUG, {"title": "Bruchrechnung"})}
        assert token_for(alt, _WERKZEUG, {"title": "Bruchrechnung"}, now=1000.0) is None
        assert is_expired(alt, now=1000.0) is True

    def test_die_frist_ist_die_des_servers(self):
        # ``services/write/confirm.ts``: zehn Minuten. Läuft unsere Frist
        # länger, setzen wir tote Schlüssel ab; läuft sie kürzer, verwerfen
        # wir gültige.
        assert TOKEN_TTL_SECONDS == 600


# ── S4: eine Abnahme MIT Nutzlast ist einlösbar ──────────────────────────
#
# Der Befund (Nutzer, 2026-08-14): Anmeldung bestätigt, Entwurf fertig, Upload
# bestätigt — und es ging nicht weiter. Jedes „ja" beantwortete der Bot mit
# derselben Vorschau.
#
# Die Ursache steht in ``schemas_mcp_curation._ContentFields``: die Nutzlast
# ist ein gewöhnliches Argument (``content`` / ``fileBase64``). Für die
# Bestätigung verlangte ``token_for`` denselben Fingerabdruck über ALLE
# Argumente — das Modell hätte 4612 Byte Markdown zeichengleich wiederholen
# müssen. Es traf daneben, der Zweig „Argumente weichen ab" griff, und es
# folgte eine neue Vorschau. Der Kommentar an jener Stelle sagte den Fall
# wörtlich voraus.
#
# Die Zustimmung steht deshalb dort, wo sie hingehört: in der Nachricht des
# Menschen. Ausgeführt wird, was in der Abnahme-Box stand.

_INHALT = "# Quiz: Gera\n\n## Lernziele\n" + ("Frage.\n" * 700)
_CONTENT_WERKZEUG = "wlo_create_content"


class TestZustimmung:
    def test_eine_klare_zusage_zaehlt(self):
        for satz in ("ja", "Ja, so ausführen", "ich bestätige es",
                     "ok", "einverstanden", "Yes, go ahead", "confirm"):
            assert is_affirmation(satz), satz

    def test_ein_vorbehalt_zaehlt_nicht(self):
        # „ja, aber …" ist der Auftrag zu einer NEUEN Vorschau. Würde er als
        # Abnahme gelten, ginge die alte Nutzlast raus — die Änderung, der
        # niemand zugestimmt hat.
        for satz in ("nein", "ja, aber ändere den Titel", "warte",
                     "nicht ausführen", "abbrechen", "erst noch ändern"):
            assert not is_affirmation(satz), satz

    def test_ein_langer_satz_ist_keine_abnahme(self):
        # Ein beiläufiges „ja" mitten in einer Bitte ist keine Zustimmung.
        assert not is_affirmation(
            "ja genau das Thema meinte ich und jetzt suche mir bitte noch "
            "Material zur Bruchrechnung")

    def test_leer_ist_keine_zustimmung(self):
        assert not is_affirmation("")
        assert not is_affirmation("   ")

    def test_die_knopfbeschriftungen_gelten(self):
        # Der Knopf aus ``turn_persist`` ist der Normalweg. Dieses Modul kennt
        # keine Sprachen — es erkennt die beiden Beschriftungen über ihre
        # Stämme. Wer den Knopf umbenennt, ohne einen Stamm zu treffen, bekommt
        # hier einen roten Test statt einer stillen Schleife im Betrieb.
        from boerdi.i18n.bot_text import bot_text
        for lang in ("de", "en"):
            assert is_affirmation(bot_text(lang, "action.write.confirmChip"))


class TestGemerkteArgumente:
    def test_der_merkposten_traegt_die_abgenommenen_argumente(self):
        offen = remember_pending(
            _CONTENT_WERKZEUG, {"title": "Quiz: Gera", "content": _INHALT},
            _TOKEN, now=1000.0)
        assert offen["args"] == {"title": "Quiz: Gera", "content": _INHALT}

    def test_ein_mitgeschickter_schluessel_wird_nicht_mitgemerkt(self):
        offen = remember_pending(
            _CONTENT_WERKZEUG, {"title": "X", "confirmToken": "ausgedacht"},
            _TOKEN, now=1000.0)
        assert "confirmToken" not in offen["args"]

    def test_zu_grosse_argumente_werden_nicht_gemerkt(self):
        # Der Merkposten liegt als JSONB in ``entities`` und wird je Zug
        # geschrieben. Ein Riesen-Upload gehört dort nicht hinein; dann bleibt
        # es beim Fingerabdruck-Weg statt einer aufgeblähten Sitzungszeile.
        riese = "x" * (MAX_REMEMBERED_ARGS_BYTES + 1)
        offen = remember_pending(
            _CONTENT_WERKZEUG, {"content": riese}, _TOKEN, now=1000.0)
        assert "args" not in offen
        assert confirmed_args(offen, _CONTENT_WERKZEUG, now=1000.0) is None

    def test_die_gemerkten_argumente_kommen_mit_schluessel_zurueck(self):
        offen = remember_pending(
            _CONTENT_WERKZEUG, {"title": "Quiz: Gera"}, _TOKEN, now=1000.0)
        assert confirmed_args(offen, _CONTENT_WERKZEUG, now=1000.0) == {
            "title": "Quiz: Gera", "confirmToken": _TOKEN}

    def test_ein_anderes_werkzeug_bekommt_nichts(self):
        offen = remember_pending(
            _CONTENT_WERKZEUG, {"title": "X"}, _TOKEN, now=1000.0)
        assert confirmed_args(offen, "wlo_delete_content", now=1000.0) is None

    def test_die_frist_gilt_auch_hier(self):
        offen = remember_pending(
            _CONTENT_WERKZEUG, {"title": "X"}, _TOKEN, now=1000.0)
        assert confirmed_args(
            offen, _CONTENT_WERKZEUG, now=1000.0 + TOKEN_TTL_SECONDS) is None


class TestAbnahmeMitNutzlast:
    def _offen(self):
        return {"entities": {"_pending_write": remember_pending(
            _CONTENT_WERKZEUG,
            {"title": "Quiz: Gera", "content": _INHALT},
            _TOKEN, now=time.time())}}

    # Das Modell trifft die Bytes im Bestätigungszug NICHT — genau das ist der
    # Fall aus dem Betrieb, und genau daran scheiterte es bisher.
    _MODELL_RUFT = ('{"title": "Quiz: Gera", "content": "# Quiz: Gera\\n(neu '
                    'formuliert, weil das Modell den Text nicht wiederholen kann)"}')

    def test_das_ja_loest_die_abnahme_ein(self, monkeypatch):
        outcome, st = _lauf(
            monkeypatch, [("tc1", _CONTENT_WERKZEUG, self._MODELL_RUFT)],
            session_state=self._offen(), werkzeug=_CONTENT_WERKZEUG,
            nachricht="ich bestätige es",
            ergebnis="Der Datensatz wurde angelegt.",
        )
        args = outcome.calls[0][1]
        assert args.get("confirmToken") == _TOKEN, (
            "Ohne Schlüssel bleibt es bei der Vorschau — die Schleife")
        assert args["content"] == _INHALT, (
            "Ausgeführt gehört, was in der Abnahme-Box stand, nicht die "
            "Neufassung des Modells")
        assert st["session_state"]["entities"].get("_pending_write") is None

    def test_ohne_zustimmung_bleibt_es_bei_der_vorschau(self, monkeypatch):
        # Gegenprobe: dieselbe Lage, aber der Mensch sagt etwas anderes.
        outcome, _st = _lauf(
            monkeypatch, [("tc1", _CONTENT_WERKZEUG, self._MODELL_RUFT)],
            session_state=self._offen(), werkzeug=_CONTENT_WERKZEUG,
            nachricht="leg bitte noch eine Sammlung dazu an",
        )
        assert "confirmToken" not in outcome.calls[0][1]

    def test_ein_vorbehalt_fuehrt_die_alte_nutzlast_nicht_aus(self, monkeypatch):
        # Der gefährliche Fall: „ja, aber …" darf NICHT die abgenommene Datei
        # hochladen, denn der Mensch will ja gerade etwas anderes.
        outcome, _st = _lauf(
            monkeypatch, [("tc1", _CONTENT_WERKZEUG, self._MODELL_RUFT)],
            session_state=self._offen(), werkzeug=_CONTENT_WERKZEUG,
            nachricht="ja, aber ändere den Titel",
        )
        args = outcome.calls[0][1]
        assert "confirmToken" not in args
        assert args["content"] != _INHALT

    def test_zustimmung_ohne_offenen_vorgang_bestaetigt_nichts(self, monkeypatch):
        # Ein „ja" ins Leere darf keinen Schlüssel erfinden.
        outcome, _st = _lauf(
            monkeypatch, [("tc1", _CONTENT_WERKZEUG, self._MODELL_RUFT)],
            werkzeug=_CONTENT_WERKZEUG, nachricht="ja",
        )
        assert "confirmToken" not in outcome.calls[0][1]

    def test_die_zustimmung_traegt_nicht_im_selben_zug(self, monkeypatch):
        # Der Wall bleibt: entsteht die Vorschau in DIESEM Zug, ist sie hier
        # nicht bestätigbar — auch nicht mit einem „ja" in der Nachricht, das
        # ja einer FRÜHEREN Vorschau galt.
        outcome, _st = _lauf(
            monkeypatch,
            [("tc1", _CONTENT_WERKZEUG, self._MODELL_RUFT),
             ("tc2", _CONTENT_WERKZEUG, self._MODELL_RUFT)],
            werkzeug=_CONTENT_WERKZEUG, nachricht="ja",
        )
        assert len(outcome.calls) == 2
        assert all("confirmToken" not in args for _n, args in outcome.calls)


class TestNahtFrist:
    def test_abgelaufener_vorgang_wird_nicht_bestaetigt(self, monkeypatch):
        vorher = {"entities": {"_pending_write": remember_pending(
            _WERKZEUG, {"title": "Bruchrechnung Klasse 6"}, _TOKEN,
            now=time.time() - 3600)}}
        outcome, _st = _lauf(
            monkeypatch, [("tc1", _WERKZEUG, _ARGS)], session_state=vorher)
        assert "confirmToken" not in outcome.calls[0][1]

    def test_abgelaufen_meldet_etwas_anderes_als_abweichende_argumente(
            self, monkeypatch, caplog):
        """Die Spur muss den Fall benennen, sonst behauptet sie einen Grund,
        den es nicht gibt: die Argumente stimmen hier überein."""
        vorher = {"entities": {"_pending_write": remember_pending(
            _WERKZEUG, {"title": "Bruchrechnung Klasse 6"}, _TOKEN,
            now=time.time() - 3600)}}
        with caplog.at_level("INFO"):
            _outcome, _st = _lauf(
                monkeypatch, [("tc1", _WERKZEUG, _ARGS)], session_state=vorher)
        assert "abgelaufen" in caplog.text
        assert "Argumente weichen" not in caplog.text
        assert _TOKEN not in caplog.text, "Der Schlüssel gehört nie ins Protokoll"
