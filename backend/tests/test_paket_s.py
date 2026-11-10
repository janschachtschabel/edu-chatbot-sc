"""Paket S (Plan 2026-11-08): schreibende Ablaufschritte mit Freigabe.

S1 — Form und Prüfung:
- Ein ``werkzeug``-Schritt darf ein schreibendes WLO-Werkzeug nur rufen, wenn es bestätigbar
  und kein Plan ist und der Schritt ``freigabe`` (den Satz über der Vorschau) trägt.
- Ein Ablauf mit schreibendem Schritt braucht die Voraussetzung ``anmeldung``.
- ``freigabe`` an einem nicht schreibenden Werkzeug ist ein Befund.
- Der Schritt wartet (Schleifen- und Längenprüfung).
- Das neue Feld ändert die Fassung bestehender Abläufe nicht (Vorgabe ``None``).
"""

from __future__ import annotations

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import treiber
from boerdi.services.ablauf.pruefung import pruefe, schreibt_mit_freigabe

W1 = "wlo_attach_fulltext"
_FREIGABE = {"de": "Diesen Volltext an den Datensatz hängen?", "en": "Attach this full text?"}


def _ablauf(schritte, voraussetzungen=("anmeldung",)):
    return AblaufArea.model_validate({"id": "probe", "titel": {"de": "Probe"},
                                      "voraussetzungen": list(voraussetzungen),
                                      "schritte": schritte})


def _schreiben(**mehr):
    return {"id": "w", "typ": "werkzeug", "werkzeug": W1,
            "argumente": {"nodeId": "n-1", "markdown": {"$teil": "volltext", "pfad": "text"},
                          "source": "manual"}, **mehr}


def _befunde(schritte, **kw):
    return pruefe(_ablauf([*schritte, {"id": "e", "typ": "ende"}], **kw))


def test_s1_schreibend_mit_freigabe_ist_erlaubt():
    befunde = _befunde([_schreiben(freigabe=_FREIGABE)])
    # nur die Befunde zum Schreiben — der Teil ``volltext`` hat hier keinen Schreiber, das meldet
    # seit AS-Db ein eigener Befund zum Datenfluss („den schreibt kein Schritt“)
    assert not [b for b in befunde if "schreibend" in b.lower() or "Freigabe" in b], befunde
    assert schreibt_mit_freigabe(_ablauf([_schreiben(freigabe=_FREIGABE)]).schritte[0])


def test_s1_ohne_freigabe_oder_ohne_deutschen_satz():
    for freigabe in (None, {"en": "only english"}, {"de": "   "}, "", {}):
        mehr = {} if freigabe is None else {"freigabe": freigabe}
        befunde = _befunde([_schreiben(**mehr)])
        assert any("braucht eine Freigabe" in b for b in befunde), freigabe


def test_s1_nur_bestaetigbare_werkzeuge_ohne_loeschen():
    # seit S4 sind Pläne erlaubt (sie laufen mit „Plan fortsetzen“ zu Ende)
    for name in ("wlo_attach_fulltexts", "wlo_create_collection_tree"):
        befunde = _befunde([{**_schreiben(freigabe=_FREIGABE), "werkzeug": name}])
        assert not any("ist schreibend" in b for b in befunde), name
    for name in ("wlo_list_suggestions", "wlo_delete_content", "wlo_delete_collection"):
        befunde = _befunde([{**_schreiben(freigabe=_FREIGABE), "werkzeug": name}])
        assert any(f"Werkzeug {name} ist schreibend" in b for b in befunde), name


def test_s1_freigabe_nur_an_schreibendem_werkzeug():
    befunde = _befunde([{"id": "w", "typ": "werkzeug", "werkzeug": "search_wlo_all",
                         "argumente": {"query": "Optik"}, "freigabe": _FREIGABE}])
    assert any("Freigabe gibt es nur an einem schreibenden" in b for b in befunde)


def test_s1_schreiben_braucht_die_anmeldung():
    befunde = _befunde([_schreiben(freigabe=_FREIGABE)], voraussetzungen=())
    assert any("Schreibende Schritte brauchen die Voraussetzung Anmeldung" in b for b in befunde)


def test_s1_der_schritt_wartet():
    # ein Kreis über den Freigabe-Schritt hält an ihm an — keine Schleife ohne Halt
    ablauf = _ablauf([_schreiben(freigabe=_FREIGABE, weiter="n"),
                      {"id": "n", "typ": "nachricht", "text": {"de": "noch einmal"}, "weiter": "w"},
                      {"id": "e", "typ": "ende"}])
    assert not any("Schleife ohne wartenden Schritt" in b for b in pruefe(ablauf))


def test_s1_das_feld_aendert_die_fassung_nicht():
    ohne = _ablauf([{"id": "w", "typ": "werkzeug", "werkzeug": "search_wlo_all"},
                    {"id": "e", "typ": "ende"}])
    leer = _ablauf([{"id": "w", "typ": "werkzeug", "werkzeug": "search_wlo_all", "freigabe": ""},
                    {"id": "e", "typ": "ende"}])
    assert leer.schritte[0].freigabe is None
    assert treiber.fassung(ohne) == treiber.fassung(leer)


# ── Review S1 ─────────────────────────────────────────────────────────────────────────────────

def test_s1_review_kein_fest_eingetragener_schluessel():
    for argumente in ({"nodeId": "n", "confirmToken": "abc"},
                      {"nodeId": "n", "confirmToken": {"$teil": "tok"}},
                      {"nodeId": "n", "continuationToken": "x", "batchToken": "y"}):
        befunde = _befunde([{**_schreiben(freigabe=_FREIGABE), "argumente": argumente}])
        assert any("dürfen keinen Schlüssel tragen" in b for b in befunde), argumente


def test_s1_review_ein_unbekanntes_werkzeug_heisst_unbekannt():
    for name in ("wlo_attach_fulltex", "x__wlo_update_content", ""):
        befunde = _befunde([{**_schreiben(freigabe=_FREIGABE), "werkzeug": name}])
        assert any("unbekannt" in b for b in befunde), (name, befunde)
        assert not any("Freigabe gibt es nur" in b for b in befunde), name


def test_s1_review_freigabe_nur_am_werkzeug_schritt_und_leere_saetze():
    befunde = _befunde([{"id": "n", "typ": "nachricht", "text": {"de": "x"},
                         "freigabe": _FREIGABE}])
    assert any("freigabe gibt es nur an einem werkzeug-Schritt" in b for b in befunde)
    leer = _ablauf([{"id": "w", "typ": "werkzeug", "werkzeug": "search_wlo_all",
                     "freigabe": {"de": " ", "en": ""}}, {"id": "e", "typ": "ende"}])
    assert leer.schritte[0].freigabe is None
    assert not any("Freigabe" in b for b in pruefe(leer))


def test_s1_review_agent_schreibt_nie_und_anmeldung_auch_ohne_freigabe():
    agent = {"id": "a", "typ": "agent", "agent": {"werkzeuge": [W1]}}
    assert any("ist schreibend" in b for b in _befunde([agent]))
    befunde = _befunde([_schreiben()], voraussetzungen=())
    assert any("Voraussetzung Anmeldung" in b for b in befunde)
    englisch = pruefe(_ablauf([_schreiben(), {"id": "e", "typ": "ende"}], voraussetzungen=()),
                      "en")
    assert any("needs an approval" in b for b in englisch)
    assert any("Writing steps need the requirement sign-in" in b for b in englisch)


def test_s1_review_der_halt_zaehlt_fuer_die_laenge():
    from boerdi.services.ablauf.pruefung import RECHENSCHRITTE

    # mehr als RECHENSCHRITTE Nachrichten — aber mit dem Freigabe-Schritt dazwischen kein Befund
    vorher = [{"id": f"n{i}", "typ": "nachricht", "text": {"de": "x"}} for i in range(20)]
    nachher = [{"id": f"m{i}", "typ": "nachricht", "text": {"de": "x"}} for i in range(20)]
    assert len(vorher) + len(nachher) > RECHENSCHRITTE
    befunde = _befunde([*vorher, _schreiben(freigabe=_FREIGABE), *nachher])
    assert not any("ohne Halt" in b for b in befunde), befunde
