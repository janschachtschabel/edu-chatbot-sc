"""Paket 18C/D, Phase 1 (1.3): die Zugakte — was ein Zug aufgerufen und umgeschrieben hat.

Sie ersetzt die Inhalte, die bisher nur im Log standen, und liegt im Diagnoseteil des
gespeicherten Zugs (nur Studio). Deshalb gelten Deckel (die Datenbank wächst sonst mit) und
dieselbe Schwärzung wie im Log: der Bestätigungs-Schlüssel nie, große Nutzlasten nur als Länge.
"""

from __future__ import annotations

import asyncio

from boerdi.services import zugakte as za


def test_ohne_eintrag_bleibt_die_akte_leer():
    assert za.Zugakte().als_dict() == {}


def test_ohne_gebundene_akte_gibt_es_keine():
    async def ohne():
        return za.aktuelle_zugakte()

    assert asyncio.run(ohne()) is None


def test_ein_werkzeugaufruf_mit_beiden_fassungen_der_argumente():
    akte = za.Zugakte()
    akte.werkzeug("search_wlo_content",
                  argumente_eingang={"query": "Klima", "learningResourceType": "Arbeitsblatt"},
                  argumente_gesendet={"query": "Klima", "learningResourceType": "http://x/ab"},
                  status="ok", aus_cache=False, dauer_ms=812, zeichen=4096)
    eintrag = akte.als_dict()["werkzeuge"][0]
    assert eintrag == {
        "name": "search_wlo_content",
        "argumente_eingang": {"query": "Klima", "learningResourceType": "Arbeitsblatt"},
        "argumente_gesendet": {"query": "Klima", "learningResourceType": "http://x/ab"},
        "status": "ok", "aus_cache": False, "dauer_ms": 812, "zeichen": 4096, "fehler": None,
    }


def test_der_bestaetigungs_schluessel_wird_nie_abgelegt():
    akte = za.Zugakte()
    akte.werkzeug("wlo_create_content", argumente_eingang={"confirmToken": "geheim-123"},
                  argumente_gesendet={"confirmToken": "geheim-123", "titel": "Optik"},
                  status="ok", aus_cache=False, dauer_ms=1)
    eintrag = akte.als_dict()["werkzeuge"][0]
    assert "geheim-123" not in repr(eintrag)
    assert eintrag["argumente_gesendet"]["titel"] == "Optik"


def test_grosse_nutzlasten_nur_als_laenge_und_lange_werte_gekuerzt():
    akte = za.Zugakte()
    akte.werkzeug("wlo_upload", argumente_eingang={},
                  argumente_gesendet={"fileBase64": "A" * 5000, "content": "x" * 3000,
                                      "description": "d" * 1500},
                  status="ok", aus_cache=False, dauer_ms=1)
    args = akte.als_dict()["werkzeuge"][0]["argumente_gesendet"]
    assert args["fileBase64"] == "‹5000 Zeichen›"
    assert args["content"] == "‹3000 Zeichen›"
    assert len(args["description"]) == za.MAX_WERT + 1 and args["description"].endswith("…")


def test_der_fehlertext_wird_gekuerzt():
    akte = za.Zugakte()
    akte.werkzeug("search_wlo_content", argumente_eingang={}, argumente_gesendet={},
                  status="tool", aus_cache=False, dauer_ms=3, fehler="MCP error: " + "e" * 3000)
    assert len(akte.als_dict()["werkzeuge"][0]["fehler"]) == za.MAX_WERT + 1


def test_hoechstens_fuenfzig_werkzeugaufrufe_der_rest_wird_gezaehlt():
    akte = za.Zugakte()
    for i in range(za.MAX_WERKZEUGE + 7):
        akte.werkzeug(f"w{i}", argumente_eingang={}, argumente_gesendet={}, status="ok",
                      aus_cache=True, dauer_ms=0)
    d = akte.als_dict()
    assert len(d["werkzeuge"]) == za.MAX_WERKZEUGE
    assert d["werkzeuge_ausgelassen"] == 7


def test_umschreibung_und_schnellweg():
    akte = za.Zugakte()
    akte.umschreibung("typ_fokus", original="o" * 1200, ersatz="Für Videos …", grund="typ")
    akte.schnellweg("canvas", thema="Optik")
    d = akte.als_dict()
    assert d["umschreibungen"] == [{"art": "typ_fokus", "original": "o" * za.MAX_WERT + "…",
                                    "ersatz": "Für Videos …", "grund": "typ"}]
    assert d["schnellwege"] == [{"art": "canvas", "thema": "Optik"}]


def test_gebunden_teilen_alle_tasks_des_zugs_dieselbe_akte():
    # LangGraph-Knoten laufen als eigene Tasks (Paket 10): die Akte ist EIN geteiltes Objekt,
    # das ein Knoten nur ergänzt — nie per ``ContextVar.set`` in einer Task neu bindet.
    async def zug():
        akte = za.binde_zugakte()

        async def knoten():
            za.aktuelle_zugakte().schnellweg("lernpfad", thema="Brüche")

        await asyncio.gather(asyncio.create_task(knoten()), asyncio.create_task(knoten()))
        return akte.als_dict()

    assert asyncio.run(zug())["schnellwege"] == [{"art": "lernpfad", "thema": "Brüche"}] * 2


# ── Review Phase 1: Größe und fremde Typen ──────────────────────────────────

def test_lange_listen_werden_gedeckelt_der_rest_gezaehlt():
    # ``excludeNodeIds`` trägt bei „zeig mehr“ bis zu 200 Kennungen.
    akte = za.Zugakte()
    akte.werkzeug("search_wlo_content", argumente_eingang={"excludeNodeIds": list(range(200))},
                  argumente_gesendet={}, status="ok", aus_cache=False, dauer_ms=1)
    liste = akte.als_dict()["werkzeuge"][0]["argumente_eingang"]["excludeNodeIds"]
    assert liste == [*range(za.MAX_EINTRAEGE), f"‹{200 - za.MAX_EINTRAEGE} weitere›"]


def test_nutzlasten_nur_als_laenge_auch_wenn_sie_kein_text_sind():
    akte = za.Zugakte()
    akte.werkzeug("wlo_upload", argumente_eingang={"content": ["geheimer", "Text"]},
                  argumente_gesendet={"fileBase64": None}, status="ok", aus_cache=False,
                  dauer_ms=1)
    eintrag = akte.als_dict()["werkzeuge"][0]
    assert "geheimer" not in repr(eintrag)
    assert eintrag["argumente_eingang"]["content"].endswith(" Zeichen›")
    assert eintrag["argumente_gesendet"]["fileBase64"] is None


def test_was_jsonb_nicht_nimmt_wird_text():
    # Sonst scheiterte das Speichern der Antwort am Diagnoseteil.
    import json
    import uuid

    akte = za.Zugakte()
    akte.werkzeug("w", argumente_eingang={"ids": {1, 2}, "u": uuid.UUID(int=1),
                                          "x": float("inf"), "n": 3, "b": True},
                  argumente_gesendet={}, status="ok", aus_cache=False, dauer_ms=1)
    args = akte.als_dict()["werkzeuge"][0]["argumente_eingang"]
    json.dumps(args, allow_nan=False)
    assert (args["n"], args["b"], args["x"]) == (3, True, "inf")


def test_ein_schwerer_zug_bleibt_klein():
    """Plan R8: zehn Suchen mit 200 ausgeschlossenen Kennungen, Filtern und langem Fehlertext."""
    import json

    akte = za.Zugakte()
    ids = [f"{i:08d}-aaaa-bbbb-cccc-dddddddddddd" for i in range(200)]
    args = {"query": "Optik Brechung Linsen", "excludeNodeIds": ids,
            "educationalContext": "Sekundarstufe I", "discipline": "Physik"}
    for _ in range(10):
        akte.werkzeug("search_wlo_content", argumente_eingang=args,
                      argumente_gesendet={**args, "outputFormat": "json"}, status="tool",
                      aus_cache=False, dauer_ms=900, fehler="MCP error: " + "e" * 2000)
    assert len(json.dumps(akte.als_dict(), ensure_ascii=False)) < 32_000


def test_der_umfang_zaehlt_jeden_eintrag():
    akte = za.Zugakte()
    assert akte.umfang == 0
    akte.schnellweg("canvas", thema="Optik")
    akte.umschreibung("waechter", original="o", ersatz="e")
    assert akte.umfang == 2
